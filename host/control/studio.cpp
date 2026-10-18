// Letki Studio: native GTK4 client. All device access belongs to letkid.
#include "demos.hpp"
#include "ipc.hpp"
#include <adwaita.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <deque>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <json-c/json.h>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

namespace {
using Json = std::shared_ptr<json_object>;
Json own(json_object *p) { return Json(p, json_object_put); }
Json parse(const std::string &s) {
  auto parser = json_tokener_new();
  json_tokener_set_flags(parser,
                         JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
  auto result = own(json_tokener_parse_ex(parser, s.data(), int(s.size())));
  size_t end = json_tokener_get_parse_end(parser);
  bool valid = json_tokener_get_error(parser) == json_tokener_success;
  while (end < s.size() && g_ascii_isspace(s[end]))
    ++end;
  json_tokener_free(parser);
  return valid && end == s.size() ? result : Json{};
}
Json object() { return own(json_object_new_object()); }
json_object *get(json_object *j, const char *k) {
  json_object *v = nullptr;
  if (j)
    json_object_object_get_ex(j, k, &v);
  return v;
}
std::string str(json_object *j, const char *key, const std::string &d = {}) {
  auto v = get(j, key);
  return v && json_object_is_type(v, json_type_string)
             ? json_object_get_string(v)
             : d;
}
int num(json_object *j, const char *key, int d = 0) {
  auto v = get(j, key);
  return v ? json_object_get_int(v) : d;
}
bool flag(json_object *j, const char *key, bool d = false) {
  auto v = get(j, key);
  return v ? json_object_get_boolean(v) : d;
}
void put(json_object *j, const char *k, const std::string &v) {
  json_object_object_add(j, k, json_object_new_string(v.c_str()));
}
void put(json_object *j, const char *k, int v) {
  json_object_object_add(j, k, json_object_new_int(v));
}
void put(json_object *j, const char *k, bool v) {
  json_object_object_add(j, k, json_object_new_boolean(v));
}
std::string dump(json_object *j) {
  return json_object_to_json_string_ext(j, JSON_C_TO_STRING_PLAIN);
}
Json clone(json_object *j) { return parse(dump(j)); }
Json request(const char *op) {
  auto j = object();
  put(j.get(), "v", 1);
  put(j.get(), "op", std::string(op));
  return j;
}
const char *fonts[] = {"compact", "large", "bold"};
const char *motions[] = {"scroll", "bounce", "fall", "still"};
const char *mods[] = {"steady", "breathe", "blink"};
struct Options {
  bool simulate = false, autoconnect = true, smoke = false, check = false;
  std::string socket, port, library = "build/control/studio-library.json";
  std::string initialPage = "compose";
};
struct Task {
  std::string kind, body;
  unsigned revision = 0;
};

// A single bounded worker serializes IPC. Preview requests are replaced by the
// newest draft; actions are never silently replaced by edits or status polling.
class Worker {
  std::mutex mutex;
  std::condition_variable wake;
  std::deque<Task> actions;
  std::optional<Task> preview, status, demoFrame;
  bool stopping = false;
  std::thread thread;

public:
  std::function<void(Task, Json)> receive;
  Worker() = default;
  void start(Options options) {
    thread = std::thread([this, options] {
      std::string ownedLease;
      auto releaseDemo = [&]() {
        auto result = object();
        put(result.get(), "ok", true);
        if (ownedLease.empty())
          return result;
        auto end = request("stream_end");
        put(end.get(), "lease", ownedLease);
        const auto until = g_get_monotonic_time() + 2000000;
        try {
          do {
            result =
                parse(control::ipc::call(dump(end.get()), options.socket, 500));
            if (result && flag(result.get(), "ok")) {
              // Wait for draining to complete before another queued action.
              while (g_get_monotonic_time() < until) {
                auto s = parse(control::ipc::call("{\"v\":1,\"op\":\"status\"}",
                                                  options.socket, 500));
                if (!s || !flag(s.get(), "busy"))
                  break;
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
              }
              break;
            }
            if (!result ||
                str(result.get(), "error").find("busy") == std::string::npos)
              break;
            std::this_thread::sleep_for(std::chrono::milliseconds(25));
          } while (g_get_monotonic_time() < until);
        } catch (const std::exception &e) {
          result = object();
          put(result.get(), "ok", false);
          put(result.get(), "error", std::string(e.what()));
        }
        ownedLease.clear();
        return result;
      };
      try {
        control::ipc::ensure_service(options.socket, options.simulate,
                                     options.autoconnect, options.port);
      } catch (const std::exception &e) {
        auto r = object();
        put(r.get(), "ok", false);
        put(r.get(), "error", std::string(e.what()));
        receive({"startup", "", 0}, r);
      }
      for (;;) {
        Task task;
        {
          std::unique_lock lock(mutex);
          wake.wait(lock, [&] {
            return stopping || !actions.empty() || preview || status ||
                   demoFrame;
          });
          if (stopping)
            break;
          if (!actions.empty()) {
            task = actions.front();
            actions.pop_front();
          } else if (demoFrame) {
            task = *demoFrame;
            demoFrame.reset();
          } else if (preview) {
            task = *preview;
            preview.reset();
          } else {
            task = *status;
            status.reset();
          }
        }
        Json result;
        try {
          result =
              task.kind == "demo_stop"
                  ? releaseDemo()
                  : parse(control::ipc::call(task.body, options.socket, 3000));
          if (!result)
            throw std::runtime_error("Service returned invalid JSON");
          if (task.kind == "demo_start" && flag(result.get(), "ok"))
            ownedLease = str(result.get(), "lease");
        } catch (const std::exception &e) {
          result = object();
          put(result.get(), "ok", false);
          put(result.get(), "error", std::string(e.what()));
        }
        receive(task, result);
      }
      releaseDemo(); // Closing Studio releases only its own stream.
    });
  }
  bool submit(Task t) {
    std::lock_guard lock(mutex);
    if (stopping)
      return false;
    if (t.kind == "demo_frame")
      demoFrame = std::move(t);
    else if (t.kind == "preview")
      preview = std::move(t);
    else if (t.kind == "status")
      status = std::move(t);
    else {
      if (actions.size() >= 8)
        return false;
      actions.push_back(std::move(t));
      if (actions.back().kind == "demo_stop")
        demoFrame.reset();
    }
    wake.notify_one();
    return true;
  }
  void stop() {
    {
      std::lock_guard lock(mutex);
      stopping = true;
      wake.notify_one();
    }
    if (thread.joinable())
      thread.join();
  }
  ~Worker() { stop(); }
};
struct Preset {
  std::string name, kind;
  Json data;
};
struct Studio : std::enable_shared_from_this<Studio> {
  Options options;
  AdwApplication *app = nullptr;
  GtkWidget *window = nullptr, *stack = nullptr, *previewArea = nullptr,
            *paintArea = nullptr;
  GtkWidget *message = nullptr, *font = nullptr, *motion = nullptr,
            *modulation = nullptr, *speed = nullptr, *peak = nullptr,
            *minimum = nullptr, *pulses = nullptr, *loop = nullptr;
  GtkWidget *badge = nullptr, *resource = nullptr, *feedback = nullptr,
            *apply = nullptr, *statusDetails = nullptr, *presetName = nullptr,
            *presetList = nullptr, *port = nullptr, *simulation = nullptr,
            *brush = nullptr;
  GtkWidget *connectButton = nullptr, *disconnectButton = nullptr;
  GtkWidget *demoScene = nullptr, *demoSpeed = nullptr, *demoLevel = nullptr,
            *demoPlay = nullptr, *demoStop = nullptr, *demoInfo = nullptr,
            *songSimulation = nullptr, *songStop = nullptr, *songInfo = nullptr,
            *songList = nullptr;
  std::vector<GtkWidget *> songButtons;
  std::vector<bool> songAvailable;
  std::vector<std::string> songCatalog;
  std::array<int, 320> demoPixels{};
  std::string demoLease, demoOwner, serviceOwner;
  bool demoStarting = false, demoStopping = false, demoFramePending = false,
       musicActive = false;
  bool catalogPending = false;
  gint64 demoStarted = g_get_monotonic_time(), lastDemoFrame = 0,
         lastCatalog = 0;
  unsigned demoFrames = 0;
  std::vector<GtkWidget *> playback;
  std::array<int, 320> previewPixels{}, paintPixels{};
  std::vector<Preset> presets;
  Worker worker;
  Json restoredDraft;
  bool closing = false, loading = false, connected = false, busy = false,
       valid = false, fits = false, previewPending = false,
       statusPending = false;
  unsigned revision = 1;
  gint64 started = g_get_monotonic_time(), lastPreview = 0, lastStatus = 0,
         lastSave = 0;
  guint timer = 0;
  int stroke = -1;
  bool smokeVerified = false;
  bool smokePassed = false;
  bool smokeDeleted = false;
  bool libraryWritable = true;
  std::string libraryWarning;
  unsigned smokeSteps = 0;
  explicit Studio(Options o) : options(std::move(o)) {
    auto id = g_uuid_string_random();
    demoOwner = "Letki Studio Demo " + std::string(id, 8);
    g_free(id);
  }
  static GtkWidget *label(const char *s, const char *css = nullptr) {
    auto w = gtk_label_new(s);
    gtk_label_set_xalign(GTK_LABEL(w), 0);
    if (css)
      gtk_widget_add_css_class(w, css);
    return w;
  }
  static GtkWidget *box(GtkOrientation orientation = GTK_ORIENTATION_VERTICAL,
                        int spacing = 12) {
    return gtk_box_new(orientation, spacing);
  }
  static void margins(GtkWidget *w, int n = 20) {
    gtk_widget_set_margin_start(w, n);
    gtk_widget_set_margin_end(w, n);
    gtk_widget_set_margin_top(w, n);
    gtk_widget_set_margin_bottom(w, n);
  }
  static GtkWidget *combo(const std::vector<const char *> &items) {
    std::vector<const char *> v = items;
    v.push_back(nullptr);
    return gtk_drop_down_new_from_strings(v.data());
  }
  static GtkWidget *spin(double a, double b, double value) {
    auto w = gtk_spin_button_new_with_range(a, b, 1);
    gtk_spin_button_set_value(GTK_SPIN_BUTTON(w), value);
    return w;
  }
  static void add(GtkWidget *parent, GtkWidget *child) {
    gtk_box_append(GTK_BOX(parent), child);
  }
  static std::string text(GtkWidget *entry) {
    return gtk_editable_get_text(GTK_EDITABLE(entry));
  }
  GtkWidget *button(const char *title, std::function<void()> fn,
                    const char *css = nullptr) {
    auto w = gtk_button_new_with_label(title);
    if (css)
      gtk_widget_add_css_class(w, css);
    auto cb = new std::function<void()>(std::move(fn));
    g_signal_connect_data(
        w, "clicked", G_CALLBACK(+[](GtkButton *, gpointer data) {
          // Library actions can destroy the button that owns this callback.
          auto callback = *static_cast<std::function<void()> *>(data);
          callback();
        }),
        cb,
        +[](gpointer data, GClosure *) {
          delete static_cast<std::function<void()> *>(data);
        },
        GConnectFlags(0));
    return w;
  }
  void note(const std::string &s) {
    gtk_label_set_text(GTK_LABEL(feedback), s.c_str());
  }
  std::string page() {
    auto s = gtk_stack_get_visible_child_name(GTK_STACK(stack));
    return s ? s : "compose";
  }
  Json draft() {
    auto j = object();
    GtkTextIter a, b;
    auto buffer = gtk_text_view_get_buffer(GTK_TEXT_VIEW(message));
    gtk_text_buffer_get_bounds(buffer, &a, &b);
    auto s = gtk_text_buffer_get_text(buffer, &a, &b, false);
    put(j.get(), "text", std::string(s));
    g_free(s);
    put(j.get(), "font",
        std::string(fonts[std::min(
            2u, gtk_drop_down_get_selected(GTK_DROP_DOWN(font)))]));
    put(j.get(), "motion",
        std::string(motions[std::min(
            3u, gtk_drop_down_get_selected(GTK_DROP_DOWN(motion)))]));
    put(j.get(), "modulation",
        std::string(mods[std::min(
            2u, gtk_drop_down_get_selected(GTK_DROP_DOWN(modulation)))]));
    for (auto p : {std::pair{"speed", speed}, std::pair{"brightness", peak},
                   std::pair{"minimum", minimum}, std::pair{"pulses", pulses}})
      put(j.get(), p.first,
          gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(p.second)));
    put(j.get(), "loop",
        gtk_check_button_get_active(GTK_CHECK_BUTTON(loop)) != 0);
    return j;
  }
  static Json pixels(const std::array<int, 320> &values) {
    auto j = own(json_object_new_array());
    for (int v : values)
      json_object_array_add(j.get(), json_object_new_int(v));
    return j;
  }
  static void readPixels(json_object *j, std::array<int, 320> &out) {
    if (!j || json_object_get_type(j) != json_type_array ||
        json_object_array_length(j) != 320)
      return;
    for (unsigned i = 0; i < 320; i++)
      out[i] = std::clamp(json_object_get_int(json_object_array_get_idx(j, i)),
                          0, 100);
  }
  void setDraft(json_object *d) {
    loading = true;
    gtk_text_buffer_set_text(gtk_text_view_get_buffer(GTK_TEXT_VIEW(message)),
                             str(d, "text", "CZEŚĆ ADAŚ  LETKI DZIAŁA").c_str(),
                             -1);
    auto select = [&](GtkWidget *widget, const char *key, const char **names,
                      unsigned count) {
      unsigned i = 0;
      auto v = str(d, key, names[0]);
      for (unsigned k = 0; k < count; k++)
        if (v == names[k])
          i = k;
      gtk_drop_down_set_selected(GTK_DROP_DOWN(widget), i);
    };
    select(font, "font", fonts, 3);
    select(motion, "motion", motions, 4);
    select(modulation, "modulation", mods, 3);
    for (auto p :
         {std::tuple{"speed", speed, 75}, std::tuple{"brightness", peak, 75},
          std::tuple{"minimum", minimum, 5}, std::tuple{"pulses", pulses, 2}})
      gtk_spin_button_set_value(GTK_SPIN_BUTTON(std::get<1>(p)),
                                num(d, std::get<0>(p), std::get<2>(p)));
    gtk_check_button_set_active(GTK_CHECK_BUTTON(loop), flag(d, "loop", true));
    loading = false;
    edited();
  }
  void load() {
    std::ifstream file(options.library);
    std::string source;
    if (file) {
      source.resize(1024 * 1024 + 1);
      file.read(source.data(), std::streamsize(source.size()));
      source.resize(size_t(file.gcount()));
    }
    auto j = parse(source);
    bool exists = std::filesystem::exists(options.library);
    if (exists && (source.size() > 1024 * 1024 || !j ||
                   !json_object_is_type(j.get(), json_type_object) ||
                   num(j.get(), "version") != 1)) {
      libraryWritable = false;
      libraryWarning =
          "The saved library is unreadable or invalid; it has been preserved. "
          "Rename it to start a new library: " +
          options.library;
      return;
    }
    if (j) {
      restoredDraft = clone(get(j.get(), "draft"));
      readPixels(get(j.get(), "pixels"), paintPixels);
      auto p = get(j.get(), "presets");
      if (p && json_object_get_type(p) == json_type_array)
        for (unsigned i = 0; i < json_object_array_length(p) && i < 200; i++) {
          auto v = json_object_array_get_idx(p, i);
          auto data = get(v, "data");
          if (data)
            presets.push_back({str(v, "name", "Untitled"),
                               str(v, "kind", "text"), clone(data)});
        }
      return;
    }
    if (options.smoke || options.check)
      return;
    auto key = g_key_file_new();
    if (g_key_file_load_from_file(key, "build/control/draft.ini",
                                  G_KEY_FILE_NONE, nullptr)) {
      restoredDraft = object();
      auto t = g_key_file_get_string(key, "General", "text", nullptr);
      if (t) {
        put(restoredDraft.get(), "text", std::string(t));
        g_free(t);
      }
      for (auto name : {"speed", "brightness", "minimum", "pulses"})
        if (g_key_file_has_key(key, "General", name, nullptr))
          put(restoredDraft.get(), name,
              g_key_file_get_integer(key, "General", name, nullptr));
      int f = std::clamp(
              g_key_file_get_integer(key, "General", "font", nullptr), 0, 2),
          m = std::clamp(
              g_key_file_get_integer(key, "General", "mode", nullptr), 0, 3),
          m2 = std::clamp(
              g_key_file_get_integer(key, "General", "modulation", nullptr), 0,
              2);
      put(restoredDraft.get(), "font", std::string(fonts[f]));
      put(restoredDraft.get(), "motion", std::string(motions[m]));
      put(restoredDraft.get(), "modulation", std::string(mods[m2]));
      put(restoredDraft.get(), "loop",
          g_key_file_get_boolean(key, "General", "loop", nullptr) != 0);
    }
    g_key_file_unref(key);
  }
  void save() {
    if (!message)
      return;
    if (!libraryWritable) {
      note(libraryWarning);
      return;
    }
    auto j = object();
    put(j.get(), "version", 1);
    auto d = draft();
    json_object_object_add(j.get(), "draft", json_object_get(d.get()));
    auto p = pixels(paintPixels);
    json_object_object_add(j.get(), "pixels", json_object_get(p.get()));
    auto list = json_object_new_array();
    for (const auto &v : presets) {
      auto o = json_object_new_object();
      put(o, "name", v.name);
      put(o, "kind", v.kind);
      json_object_object_add(o, "data", json_object_get(v.data.get()));
      json_object_array_add(list, o);
    }
    json_object_object_add(j.get(), "presets", list);
    try {
      auto path = std::filesystem::path(options.library);
      if (!path.parent_path().empty())
        std::filesystem::create_directories(path.parent_path());
      auto temp = options.library + ".tmp";
      {
        std::ofstream out(temp);
        out << json_object_to_json_string_ext(j.get(), JSON_C_TO_STRING_PRETTY)
            << '\n';
        if (!out)
          throw std::runtime_error("Could not save local draft");
      }
      std::filesystem::rename(temp, options.library);
      lastSave = 0;
    } catch (const std::exception &e) {
      note(e.what());
    }
  }
  void edited() {
    if (loading || closing)
      return;
    revision++;
    valid = false;
    fits = false;
    previewPending = false;
    started = g_get_monotonic_time();
    lastPreview = 0;
    lastSave = g_get_monotonic_time();
    int highest = gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(peak));
    gtk_spin_button_set_range(GTK_SPIN_BUTTON(minimum), 0, highest);
    bool mod = gtk_drop_down_get_selected(GTK_DROP_DOWN(modulation)) != 0;
    gtk_widget_set_sensitive(minimum, mod);
    gtk_widget_set_sensitive(pulses, mod);
    updateButtons();
  }
  void updateButtons() {
    bool pixel = page() == "pixels";
    bool demo = page() == "demo";
    gtk_button_set_label(GTK_BUTTON(apply), demo    ? "Play on display"
                                            : pixel ? "Apply pixels"
                                                    : "Apply text");
    gtk_widget_set_sensitive(
        apply, connected && !busy && !musicActive && !demoStarting &&
                   !demoStopping &&
                   (demo ? demoLease.empty() && serviceOwner.empty()
                         : pixel || (valid && fits)));
    for (unsigned i = 0; i < playback.size(); i++) {
      gtk_widget_set_visible(playback[i], !demo || i == 3);
      gtk_widget_set_sensitive(playback[i], connected && !busy && !musicActive);
    }
    if (demoPlay)
      gtk_widget_set_sensitive(demoPlay, connected && !busy && !musicActive &&
                                             !demoStarting && !demoStopping &&
                                             demoLease.empty() &&
                                             serviceOwner.empty());
    if (demoStop)
      gtk_widget_set_sensitive(demoStop, !demoLease.empty() && !demoStopping);
    if (songStop)
      gtk_widget_set_sensitive(songStop, musicActive);
    for (unsigned i = 0; i < songButtons.size(); i++)
      gtk_widget_set_sensitive(
          songButtons[i],
          songAvailable[i] && !musicActive && !busy && !demoStarting &&
              !demoStopping && (serviceOwner.empty() || !demoLease.empty()) &&
              (connected ||
               gtk_check_button_get_active(GTK_CHECK_BUTTON(songSimulation))));
    gtk_widget_set_sensitive(connectButton,
                             !connected && !busy && !musicActive);
    gtk_widget_set_sensitive(disconnectButton, !busy && !musicActive);
    gtk_widget_set_sensitive(port, !connected && !busy);
    gtk_widget_set_sensitive(simulation, !connected && !busy);
  }
  void action(const char *op) {
    if (!demoLease.empty())
      stopDemo();
    auto j = request(op);
    put(j.get(), "client", std::string("Letki Studio"));
    send("action", j);
  }
  void send(const std::string &kind, const Json &j) {
    if (!worker.submit({kind, dump(j.get()), revision}))
      note("The service request queue is full. Try again shortly.");
  }
  void applyDraft() {
    if (page() == "demo") {
      startDemo();
      return;
    }
    if (!demoLease.empty())
      stopDemo();
    auto j = request(page() == "pixels" ? "pixels" : "text");
    put(j.get(), "client", std::string("Letki Studio"));
    auto d = page() == "pixels" ? pixels(paintPixels) : draft();
    json_object_object_add(j.get(), page() == "pixels" ? "pixels" : "draft",
                           json_object_get(d.get()));
    send("action", j);
    note("Applying captured draft… New edits remain local.");
  }
  void startDemo() {
    if (demoStarting || demoStopping || !demoLease.empty() || musicActive)
      return;
    demoStarting = true;
    auto j = request("stream_begin");
    put(j.get(), "owner", demoOwner);
    put(j.get(), "format", 2);
    put(j.get(), "ttl_ms", 3000);
    send("demo_start", j);
    note("Starting the previewed demo on all five tiles…");
    updateButtons();
  }
  void stopDemo() {
    if (demoLease.empty() || demoStopping)
      return;
    demoStopping = true;
    demoFramePending = false;
    send("demo_stop", request("stream_end"));
    updateButtons();
  }
  void playSong(const std::string &id) {
    if (id.empty() || musicActive)
      return;
    if (!demoLease.empty())
      stopDemo();
    auto j = request("music_start");
    put(j.get(), "id", id);
    put(j.get(), "simulate",
        gtk_check_button_get_active(GTK_CHECK_BUTTON(songSimulation)) != 0);
    if (auto value = g_getenv("WAYLAND_DISPLAY"))
      put(j.get(), "wayland_display", std::string(value));
    if (auto value = g_getenv("DISPLAY"))
      put(j.get(), "display", std::string(value));
    send("song_start", j);
    musicActive = true;
    updateButtons();
    note("Opening music, video and synchronized LED animation in the player…");
  }
  void response(const Task &task, const Json &j) {
    if (closing)
      return;
    if (task.kind == "song_start" && !flag(j.get(), "ok"))
      musicActive = false;
    if (task.kind == "demo_start") {
      demoStarting = false;
      if (flag(j.get(), "ok"))
        demoLease = str(j.get(), "lease");
      else
        note(str(j.get(), "error", "Could not start demo"));
      if (!demoLease.empty() && page() != "demo")
        stopDemo();
      lastStatus = 0;
      updateButtons();
      return;
    }
    if (task.kind == "demo_stop") {
      demoLease.clear();
      demoStopping = false;
      demoFramePending = false;
      note(flag(j.get(), "ok") ? "Demo stopped. The last frame stays "
                                 "displayed; Resume returns to the loaded show."
                               : str(j.get(), "error"));
      lastStatus = 0;
      updateButtons();
      return;
    }
    if (task.kind == "demo_frame") {
      demoFramePending = false;
      if (flag(j.get(), "ok"))
        demoFrames++;
      else if (str(j.get(), "error").find("busy") != std::string::npos)
        // Retry with fresh pixels on the next UI tick. Waiting a whole frame
        // interval nearly halves throughput if UART finishes just too late.
        lastDemoFrame = 0;
      else {
        note(str(j.get(), "error"));
        stopDemo();
      }
      return;
    }
    if (task.kind == "catalog") {
      catalogPending = false;
      auto songs = get(j.get(), "songs");
      if (songs && json_object_is_type(songs, json_type_array)) {
        std::vector<std::string> catalog;
        for (unsigned i = 0; i < json_object_array_length(songs); ++i) {
          auto song = json_object_array_get_idx(songs, i);
          catalog.push_back(str(song, "id"));
          catalog.push_back(str(song, "title"));
          catalog.push_back(str(song, "description"));
        }
        // Keep existing widgets/focus during ordinary availability polling.
        // Rebuild only when entries, ordering or displayed metadata change.
        if (catalog != songCatalog) {
          songButtons.clear();
          songAvailable.clear();
          while (auto child = gtk_widget_get_first_child(songList))
            gtk_box_remove(GTK_BOX(songList), child);
          songCatalog = catalog;
          for (unsigned i = 0; i < catalog.size(); i += 3) {
            auto row = box(GTK_ORIENTATION_HORIZONTAL, 12);
            auto title = box(GTK_ORIENTATION_VERTICAL, 4);
            gtk_widget_set_hexpand(title, true);
            add(title, label(catalog[i + 1].c_str()));
            auto description = label(catalog[i + 2].c_str(), "muted");
            gtk_label_set_wrap(GTK_LABEL(description), true);
            add(title, description);
            add(row, title);
            auto id = catalog[i];
            auto play = button("Play music + video", [this, id] { playSong(id); });
            songButtons.push_back(play);
            songAvailable.push_back(false);
            add(row, play);
            add(songList, row);
          }
        }
        std::string missing;
        for (unsigned i = 0; i < songButtons.size(); ++i) {
          auto song = json_object_array_get_idx(songs, i);
          songAvailable[i] = flag(song, "available");
          if (!songAvailable[i])
            missing += str(song, "title") + ": " + str(song, "reason") + "\n";
        }
        if (songButtons.empty()) missing = "No music demos are listed by the service.";
        gtk_label_set_text(GTK_LABEL(songInfo),
                           missing.empty()
                               ? "Audio and normal video play on the PC beside "
                                 "the simulator. Video never drives LED pixels."
                               : missing.c_str());
      }
      updateButtons();
      return;
    }
    if (task.kind == "preview") {
      if (task.revision != revision)
        return;
      previewPending = false;
      valid = flag(j.get(), "ok");
      fits = flag(j.get(), "fits");
      if (valid) {
        readPixels(get(j.get(), "pixels"), previewPixels);
        char s[160];
        std::snprintf(s, sizeof s,
                      "%d / %d bytes per tile  ·  %.1f s cycle  ·  %d tracks",
                      num(j.get(), "bytes"), num(j.get(), "capacity", 752),
                      num(j.get(), "duration_ms") / 1000.,
                      num(j.get(), "tracks"));
        if (page() != "demo")
          gtk_label_set_text(GTK_LABEL(resource), s);
        if (!fits)
          note("This draft exceeds tile RAM. Use a smaller font, shorter text "
               "or fewer pulses.");
        else if (!connected)
          note("Preview is ready. Connect to apply this draft.");
      } else {
        previewPixels = {};
        if (page() != "demo")
          gtk_label_set_text(
              GTK_LABEL(resource),
              str(j.get(), "error", "Preview unavailable").c_str());
      }
      gtk_widget_queue_draw(previewArea);
      updateButtons();
      return;
    }
    if (task.kind == "status")
      statusPending = false;
    if (!flag(j.get(), "ok")) {
      note(str(j.get(), "error", "The service did not accept this request."));
      if (task.kind == "status") {
        connected = false;
        busy = false;
        gtk_label_set_text(GTK_LABEL(badge), "Service unavailable");
        updateButtons();
      }
      return;
    }
    if (task.kind == "status") {
      connected = flag(j.get(), "connected");
      busy = flag(j.get(), "busy");
      musicActive = flag(j.get(), "music_active");
      serviceOwner = str(j.get(), "stream_owner");
      if (!demoLease.empty() && !demoStopping && !busy &&
          (serviceOwner != demoOwner || !flag(j.get(), "streaming"))) {
        demoLease.clear();
        demoFramePending = false;
      }
      bool simulated = flag(j.get(), "simulated");
      // --simulate is an explicit boundary: it must never apply to a live
      // chain.
      if (options.simulate && connected && !simulated) {
        connected = false;
        note("A hardware service is already running. Disconnect it explicitly "
             "before connecting simulation.");
      }
      std::string title = busy        ? "Working…"
                          : connected ? (simulated ? "Simulation · 5 tiles"
                                                   : "Connected · 5 tiles")
                                      : "Disconnected";
      if (flag(j.get(), "streaming"))
        title += " · Streaming";
      if (musicActive)
        title = "Music · " + str(j.get(), "music_title");
      gtk_label_set_text(GTK_LABEL(badge), title.c_str());
      std::string details =
          "Service socket\n" +
          (options.socket.empty() ? control::ipc::default_socket()
                                  : options.socket) +
          "\n\nConnection\n" + str(j.get(), "port", "Automatic adapter") +
          "\n" + str(j.get(), "message") + "\n\n";
      if (connected) {
        char timing[240];
        std::snprintf(timing, sizeof timing,
                      "UART %d baud · %.1f frames/s\n"
                      "Last frame %d ms · retries %d · invalid packets %d\n"
                      "Late transfers %d · dropped frames %d\n\n",
                      num(j.get(), "baud"),
                      json_object_get_double(get(j.get(), "stream_fps")),
                      num(j.get(), "frame_transfer_ms"),
                      num(j.get(), "transport_retries"),
                      num(j.get(), "transport_invalid"),
                      num(j.get(), "stream_late"),
                      num(j.get(), "stream_dropped"));
        details += timing;
      }
      auto nodes = get(j.get(), "nodes");
      if (nodes && json_object_get_type(nodes) == json_type_array)
        for (unsigned i = 0; i < json_object_array_length(nodes); i++) {
          auto n = json_object_array_get_idx(nodes, i);
          details += "Tile " + std::to_string(num(n, "index", i) + 1) + "   " +
                     str(n, "id", "Unknown ID") + "\n" +
                     std::to_string(num(n, "bytes")) + " / " +
                     std::to_string(num(n, "arena")) + " bytes · " +
                     std::to_string(num(n, "slots")) +
                     " frame slots · errors " +
                     std::to_string(num(n, "errors")) + " · drops " +
                     std::to_string(num(n, "drops")) + " · late " +
                     std::to_string(num(n, "late")) + "\n\n";
        }
      if (flag(j.get(), "streaming"))
        details += "Stream owner: " + str(j.get(), "stream_owner") + "\n";
      if (musicActive)
        details += "Music player: " + str(j.get(), "music_title") + " · " +
                   str(j.get(), "music_state") + "\n";
      gtk_label_set_text(GTK_LABEL(statusDetails), details.c_str());
      if (musicActive)
        note("Music player: " + str(j.get(), "music_title") + " · " +
             str(j.get(), "music_state") +
             ". Stop here or press Escape in the player.");
      else if (!str(j.get(), "music_error").empty())
        note(str(j.get(), "music_error"));
      else if (connected && !str(j.get(), "message").empty())
        note(str(j.get(), "message"));
      updateButtons();
      if (connected && simulated)
        smokeVerified = true;
    } else {
      note(str(j.get(), "message", "Request accepted by display service."));
      lastStatus = 0;
    }
  }
  static void rounded(cairo_t *cr, double x, double y, double w, double h,
                      double r) {
    cairo_new_sub_path(cr);
    cairo_arc(cr, x + w - r, y + r, r, -G_PI_2, 0);
    cairo_arc(cr, x + w - r, y + h - r, r, 0, G_PI_2);
    cairo_arc(cr, x + r, y + h - r, r, G_PI_2, G_PI);
    cairo_arc(cr, x + r, y + r, r, G_PI, 3 * G_PI_2);
    cairo_close_path(cr);
  }
  static void draw(GtkDrawingArea *, cairo_t *cr, int width, int height,
                   gpointer data) {
    auto pair = static_cast<std::pair<Studio *, bool> *>(data);
    auto self = pair->first;
    bool paint = pair->second;
    auto &values = paint ? self->paintPixels
                   : self->page() == "demo"
                       ? self->demoPixels
                       : (self->page() == "pixels" ? self->paintPixels
                                                   : self->previewPixels);
    double cell =
               std::max(2., std::min((width - 28.) / 42., (height - 30.) / 8.)),
           left = (width - cell * 42) / 2., top = (height - 28 - cell * 8) / 2.;
    for (int x = 0; x < 40; x++)
      for (int y = 0; y < 8; y++) {
        double v = std::sqrt(values[y * 40 + x] / 100.);
        cairo_set_source_rgb(cr, (22 + 233 * v) / 255., (31 + 145 * v) / 255.,
                             (44 + 26 * v) / 255.);
        double gap = std::max(1., cell * .10);
        rounded(cr, left + (x + (x / 8) * .5) * cell + gap,
                top + y * cell + gap, cell - 2 * gap, cell - 2 * gap,
                std::min(3., cell * .15));
        cairo_fill(cr);
      }
    cairo_set_font_size(cr, 10);
    cairo_set_source_rgb(cr, .55, .62, .72);
    for (int n = 0; n < 5; n++) {
      std::string s = std::to_string(n + 1);
      cairo_move_to(cr, left + (n * 8.5 + 3.8) * cell, top + 8 * cell + 18);
      cairo_show_text(cr, s.c_str());
    }
  }
  void paint(double x, double y, bool initial) {
    int width = gtk_widget_get_width(paintArea),
        height = gtk_widget_get_height(paintArea);
    double cell =
               std::max(2., std::min((width - 28.) / 42., (height - 30.) / 8.)),
           left = (width - cell * 42) / 2., top = (height - 28 - cell * 8) / 2.;
    int row = std::floor((y - top) / cell);
    double gx = (x - left) / cell;
    if (row < 0 || row >= 8 || gx < 0 || gx >= 42)
      return;
    int tile = std::min(4, int(gx / 8.5));
    double tx = gx - tile * 8.5;
    if (tx >= 8)
      return;
    int column = tile * 8 + int(tx);
    if (column < 0 || column >= 40)
      return;
    int index = row * 40 + column;
    if (initial)
      stroke = paintPixels[index]
                   ? 0
                   : gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(brush));
    if (stroke < 0)
      return;
    paintPixels[index] = stroke;
    gtk_widget_queue_draw(paintArea);
    gtk_widget_queue_draw(previewArea);
    lastSave = g_get_monotonic_time();
  }
  GtkWidget *canvas(bool paint) {
    auto w = gtk_drawing_area_new();
    gtk_widget_set_hexpand(w, true);
    gtk_drawing_area_set_content_height(GTK_DRAWING_AREA(w), paint ? 230 : 190);
    auto data = new std::pair{this, paint};
    gtk_drawing_area_set_draw_func(
        GTK_DRAWING_AREA(w), draw, data, +[](gpointer p) {
          delete static_cast<std::pair<Studio *, bool> *>(p);
        });
    if (paint) {
      auto click = gtk_gesture_click_new();
      gtk_gesture_single_set_button(GTK_GESTURE_SINGLE(click),
                                    GDK_BUTTON_PRIMARY);
      g_signal_connect(click, "pressed",
                       G_CALLBACK(+[](GtkGestureClick *, int, double x,
                                      double y, gpointer p) {
                         static_cast<Studio *>(p)->paint(x, y, true);
                       }),
                       this);
      g_signal_connect(
          click, "released",
          G_CALLBACK(+[](GtkGestureClick *, int, double, double, gpointer p) {
            static_cast<Studio *>(p)->stroke = -1;
          }),
          this);
      gtk_widget_add_controller(w, GTK_EVENT_CONTROLLER(click));
      auto move = gtk_event_controller_motion_new();
      g_signal_connect(move, "motion",
                       G_CALLBACK(+[](GtkEventControllerMotion *, double x,
                                      double y, gpointer p) {
                         auto s = static_cast<Studio *>(p);
                         if (s->stroke >= 0)
                           s->paint(x, y, false);
                       }),
                       this);
      g_signal_connect(move, "leave",
                       G_CALLBACK(+[](GtkEventControllerMotion *, gpointer p) {
                         static_cast<Studio *>(p)->stroke = -1;
                       }),
                       this);
      gtk_widget_add_controller(w, move);
    }
    return w;
  }
  GtkWidget *field(const char *title, GtkWidget *control) {
    auto b = box(GTK_ORIENTATION_VERTICAL, 6);
    add(b, label(title, "field-label"));
    add(b, control);
    gtk_widget_set_hexpand(b, true);
    return b;
  }
  GtkWidget *scrolled(GtkWidget *child) {
    auto w = gtk_scrolled_window_new();
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(w), GTK_POLICY_NEVER,
                                   GTK_POLICY_AUTOMATIC);
    gtk_scrolled_window_set_child(GTK_SCROLLED_WINDOW(w), child);
    gtk_widget_set_vexpand(w, true);
    return w;
  }
  void libraryRows() {
    while (auto w = gtk_widget_get_first_child(presetList))
      gtk_list_box_remove(GTK_LIST_BOX(presetList), w);
    if (presets.empty()) {
      gtk_list_box_append(
          GTK_LIST_BOX(presetList),
          label("No presets yet. Save your current text or pixels below.",
                "muted"));
      return;
    }
    for (unsigned i = 0; i < presets.size(); i++) {
      auto row = box(GTK_ORIENTATION_HORIZONTAL, 10);
      margins(row, 10);
      auto name = label(presets[i].name.c_str());
      gtk_widget_set_hexpand(name, true);
      add(row, name);
      add(row, label(presets[i].kind == "text" ? "Text" : "Pixels", "muted"));
      add(row, button("Load", [this, i] {
            if (i >= presets.size())
              return;
            if (presets[i].kind == "text") {
              setDraft(presets[i].data.get());
              gtk_stack_set_visible_child_name(GTK_STACK(stack), "compose");
            } else {
              readPixels(presets[i].data.get(), paintPixels);
              gtk_stack_set_visible_child_name(GTK_STACK(stack), "pixels");
              gtk_widget_queue_draw(paintArea);
              gtk_widget_queue_draw(previewArea);
              lastSave = g_get_monotonic_time();
            }
            note("Preset loaded locally. Apply when ready.");
          }));
      add(row, button("Delete", [this, i] {
            if (i < presets.size()) {
              presets.erase(presets.begin() + i);
              libraryRows();
              save();
            }
          }));
      gtk_list_box_append(GTK_LIST_BOX(presetList), row);
    }
  }
  static GtkWidget *findButton(GtkWidget *root, const char *title) {
    if (GTK_IS_BUTTON(root)) {
      auto name = gtk_button_get_label(GTK_BUTTON(root));
      if (name && std::string(name) == title)
        return root;
    }
    for (auto child = gtk_widget_get_first_child(root); child;
         child = gtk_widget_get_next_sibling(child))
      if (auto found = findButton(child, title))
        return found;
    return nullptr;
  }
  void savePreset(bool pixel) {
    auto name = text(presetName);
    if (name.empty()) {
      note("Give the preset a name before saving.");
      return;
    }
    if (presets.size() >= 200) {
      note("Library is full. Delete a preset first.");
      return;
    }
    presets.push_back({name, pixel ? "pixels" : "text",
                       pixel ? pixels(paintPixels) : draft()});
    libraryRows();
    save();
    note("Preset saved locally.");
  }
  void build() {
    load();
    adw_style_manager_set_color_scheme(adw_style_manager_get_default(),
                                       ADW_COLOR_SCHEME_FORCE_DARK);
    auto css = gtk_css_provider_new();
    gtk_css_provider_load_from_string(css, R"CSS(
window { background: #101722; } .studio-title { font-size: 21px; font-weight: 750; } .muted { color: #97a6b9; } .field-label { color: #b8c5d6; font-size: 12px; font-weight: 600; } .status-chip { color: #ffc075; background: #26303e; border-radius: 18px; padding: 6px 14px; font-size: 12px; } .preview { background: #0b121b; border-radius: 14px; } .suggested-action { background: #f7ad53; color: #171a20; font-weight: 700; } .resource { color: #c4a177; font-size: 12px; } textview { font-size: 18px; background: #182231; padding: 10px; border-radius: 10px; } .diagnostics { font-family: monospace; font-size: 12px; } .library-list { background: #151f2d; border-radius: 10px; } stackswitcher button:checked { color: #ffc075; } .footer { background: #151f2b; } .nav { background: #101722; } button { min-height: 28px; } entry,spinbutton,dropdown { min-height: 32px; }
)CSS");
    gtk_style_context_add_provider_for_display(
        gdk_display_get_default(), GTK_STYLE_PROVIDER(css),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(css);
    window = adw_application_window_new(GTK_APPLICATION(app));
    gtk_window_set_title(GTK_WINDOW(window), "Letki Studio");
    gtk_window_set_default_size(GTK_WINDOW(window), 1120, 850);
    gtk_widget_set_size_request(window, 780, 620);
    auto shell = box(GTK_ORIENTATION_VERTICAL, 0);
    adw_application_window_set_content(ADW_APPLICATION_WINDOW(window), shell);
    auto header = adw_header_bar_new();
    adw_header_bar_set_title_widget(ADW_HEADER_BAR(header),
                                    label("Letki Studio", "studio-title"));
    badge = label("Starting service…", "status-chip");
    adw_header_bar_pack_end(ADW_HEADER_BAR(header), badge);
    add(shell, header);
    auto top = box(GTK_ORIENTATION_VERTICAL, 6);
    margins(top, 18);
    auto previewHead = box(GTK_ORIENTATION_HORIZONTAL, 10);
    add(previewHead, label("DRAFT PREVIEW", "field-label"));
    resource = label("Waiting for display service…", "resource");
    gtk_widget_set_hexpand(resource, true);
    gtk_label_set_xalign(GTK_LABEL(resource), 1);
    add(previewHead, resource);
    add(top, previewHead);
    previewArea = canvas(false);
    gtk_widget_add_css_class(previewArea, "preview");
    add(top, previewArea);
    add(top,
        label(
            "Edits stay local until Apply. Preview uses the firmware renderer.",
            "muted"));
    add(shell, top);
    auto center = box(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_widget_set_vexpand(center, true);
    stack = gtk_stack_new();
    gtk_stack_set_transition_type(GTK_STACK(stack),
                                  GTK_STACK_TRANSITION_TYPE_CROSSFADE);
    gtk_widget_set_hexpand(stack, true);
    gtk_widget_set_vexpand(stack, true);
    auto sidebar = gtk_stack_sidebar_new();
    gtk_stack_sidebar_set_stack(GTK_STACK_SIDEBAR(sidebar), GTK_STACK(stack));
    gtk_widget_set_size_request(sidebar, 145, -1);
    gtk_widget_add_css_class(sidebar, "nav");
    add(center, sidebar);
    add(center, stack);
    add(shell, center);
    auto compose = box();
    margins(compose, 18);
    message = gtk_text_view_new();
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(message), GTK_WRAP_WORD_CHAR);
    gtk_widget_set_size_request(message, -1, 95);
    add(compose, field("Your message", message));
    font = combo({"Compact · 3 × 7", "Large · 8 × 8", "Bold · 9 × 8"});
    motion = combo({"Scroll across chain", "Bounce left and right",
                    "Fall downward", "Still / centered"});
    modulation =
        combo({"Steady light", "Breathe · gradual", "Blink · alternating"});
    speed = spin(10, 500, 75);
    peak = spin(0, 100, 75);
    minimum = spin(0, 100, 5);
    pulses = spin(1, 6, 2);
    loop = gtk_check_button_new_with_label("Loop message");
    auto grid = gtk_grid_new();
    gtk_grid_set_column_homogeneous(GTK_GRID(grid), true);
    gtk_grid_set_column_spacing(GTK_GRID(grid), 16);
    gtk_grid_set_row_spacing(GTK_GRID(grid), 12);
    std::vector<std::pair<const char *, GtkWidget *>> fields = {
        {"Font", font},
        {"Motion", motion},
        {"Speed · ms / pixel", speed},
        {"Brightness modulation", modulation},
        {"Peak brightness · %", peak},
        {"Minimum brightness · %", minimum},
        {"Pulses / text cycle", pulses}};
    for (unsigned i = 0; i < fields.size(); i++)
      gtk_grid_attach(GTK_GRID(grid), field(fields[i].first, fields[i].second),
                      i % 3, i / 3, 1, 1);
    gtk_grid_attach(GTK_GRID(grid), loop, 1, 2, 2, 1);
    add(compose, grid);
    auto info = label("Larger fonts use more RAM. Brightness and motion "
                      "continue on the boards after Studio closes.",
                      "muted");
    gtk_label_set_wrap(GTK_LABEL(info), true);
    add(compose, info);
    gtk_stack_add_titled(GTK_STACK(stack), scrolled(compose), "compose",
                         "Compose");
    auto pixelPage = box();
    margins(pixelPage, 18);
    add(pixelPage, label("Paint with light", "studio-title"));
    auto pinfo = label("Click to paint or erase. Drag to draw with the same "
                       "level. Nothing is sent until Apply.",
                       "muted");
    gtk_label_set_wrap(GTK_LABEL(pinfo), true);
    add(pixelPage, pinfo);
    paintArea = canvas(true);
    gtk_widget_add_css_class(paintArea, "preview");
    add(pixelPage, paintArea);
    auto tools = box(GTK_ORIENTATION_HORIZONTAL, 12);
    brush = spin(0, 100, 100);
    add(tools, field("Brush brightness · %", brush));
    add(tools, button("Clear", [this] {
          paintPixels = {};
          gtk_widget_queue_draw(paintArea);
          gtk_widget_queue_draw(previewArea);
          lastSave = g_get_monotonic_time();
        }));
    add(tools, button("Invert", [this] {
          for (auto &v : paintPixels)
            v = 100 - v;
          gtk_widget_queue_draw(paintArea);
          gtk_widget_queue_draw(previewArea);
          lastSave = g_get_monotonic_time();
        }));
    add(pixelPage, tools);
    gtk_stack_add_titled(GTK_STACK(stack), scrolled(pixelPage), "pixels",
                         "Pixel canvas");
    auto demoPage = box();
    margins(demoPage, 18);
    add(demoPage, label("PWM playground", "studio-title"));
    auto demoDescription =
        label("The original six scenes, across all five tiles. Preview is "
              "local; Play on display streams through the service.",
              "muted");
    gtk_label_set_wrap(GTK_LABEL(demoDescription), true);
    add(demoPage, demoDescription);
    demoScene =
        combo({"Full PWM showcase", "Silk ribbon", "Ripple garden",
               "Ember trails", "Five lanterns", "Light ladder", "Daisy chain"});
    demoSpeed = spin(25, 200, 100);
    demoLevel = spin(0, 100, 100);
    auto demoOptions = gtk_grid_new();
    gtk_grid_set_column_spacing(GTK_GRID(demoOptions), 14);
    gtk_grid_set_column_homogeneous(GTK_GRID(demoOptions), true);
    gtk_grid_attach(GTK_GRID(demoOptions), field("Scene", demoScene), 0, 0, 1,
                    1);
    gtk_grid_attach(GTK_GRID(demoOptions), field("Speed · %", demoSpeed), 1, 0,
                    1, 1);
    gtk_grid_attach(GTK_GRID(demoOptions), field("Brightness · %", demoLevel),
                    2, 0, 1, 1);
    add(demoPage, demoOptions);
    demoInfo = label("Preview only · no display changes", "resource");
    add(demoPage, demoInfo);
    auto demoActions = box(GTK_ORIENTATION_HORIZONTAL, 10);
    demoPlay =
        button("Play on display", [this] { startDemo(); }, "suggested-action");
    demoStop = button("Stop demo", [this] { stopDemo(); });
    add(demoActions, demoPlay);
    add(demoActions, demoStop);
    add(demoActions, button("Restart preview",
                            [this] { demoStarted = g_get_monotonic_time(); }));
    add(demoPage, demoActions);
    auto demoHint =
        label("Visual demos run while this tab stays open. Stop or leaving the "
              "tab holds the last frame; Resume returns to your loaded show. "
              "Fine PWM steps are preserved with LEVEL8 streaming (160 spare "
              "RAM bytes needed).",
              "muted");
    gtk_label_set_wrap(GTK_LABEL(demoHint), true);
    add(demoPage, demoHint);
    add(demoPage, gtk_separator_new(GTK_ORIENTATION_HORIZONTAL));
    add(demoPage, label("Music + video", "studio-title"));
    songInfo = label("Checking local recordings…", "muted");
    gtk_label_set_wrap(GTK_LABEL(songInfo), true);
    add(demoPage, songInfo);
    songList = box(GTK_ORIENTATION_VERTICAL, 12);
    add(demoPage, songList);
    auto musicOptions = box(GTK_ORIENTATION_HORIZONTAL, 12);
    songSimulation =
        gtk_check_button_new_with_label("PC only · no physical display");
    gtk_check_button_set_active(GTK_CHECK_BUTTON(songSimulation),
                                options.simulate);
    g_signal_connect(songSimulation, "toggled",
                     G_CALLBACK(+[](GtkCheckButton *, gpointer p) {
                       static_cast<Studio *>(p)->updateButtons();
                     }),
                     this);
    add(musicOptions, songSimulation);
    songStop =
        button("Stop music", [this] { send("action", request("music_stop")); });
    add(musicOptions, songStop);
    add(demoPage, musicOptions);
    auto musicHint =
        label("Music opens in the existing player, with video above the "
              "simulator. The service hands over UART and reconnects after "
              "playback. Space pauses; arrows seek; Escape exits. Music can "
              "continue after Studio closes.",
              "muted");
    gtk_label_set_wrap(GTK_LABEL(musicHint), true);
    add(demoPage, musicHint);
    gtk_stack_add_titled(GTK_STACK(stack), scrolled(demoPage), "demo", "Demo");
    g_signal_connect(demoScene, "notify::selected",
                     G_CALLBACK(+[](GObject *, GParamSpec *, gpointer p) {
                       static_cast<Studio *>(p)->demoStarted =
                           g_get_monotonic_time();
                     }),
                     this);
    auto library = box();
    margins(library, 18);
    add(library, label("Your library", "studio-title"));
    if (!libraryWarning.empty()) {
      auto warning = label(libraryWarning.c_str(), "error");
      gtk_label_set_wrap(GTK_LABEL(warning), true);
      add(library, warning);
    }
    add(library,
        label("Load a preset, adjust it, then Apply when ready.", "muted"));
    presetList = gtk_list_box_new();
    gtk_list_box_set_selection_mode(GTK_LIST_BOX(presetList),
                                    GTK_SELECTION_NONE);
    gtk_widget_add_css_class(presetList, "library-list");
    add(library, presetList);
    auto saveRow = box(GTK_ORIENTATION_HORIZONTAL, 10);
    presetName = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(presetName), "Preset name");
    gtk_widget_set_hexpand(presetName, true);
    add(saveRow, presetName);
    add(saveRow, button("Save text", [this] { savePreset(false); }));
    add(saveRow, button("Save pixels", [this] { savePreset(true); }));
    add(library, saveRow);
    gtk_stack_add_titled(GTK_STACK(stack), scrolled(library), "library",
                         "Library");
    libraryRows();
    auto diagnostics = box();
    margins(diagnostics, 18);
    add(diagnostics, label("Display service", "studio-title"));
    auto description =
        label("The local service owns UART. Studio and other apps share its "
              "versioned API without competing for the serial port.",
              "muted");
    gtk_label_set_wrap(GTK_LABEL(description), true);
    add(diagnostics, description);
    auto conn = box(GTK_ORIENTATION_HORIZONTAL, 10);
    port = gtk_entry_new();
    gtk_entry_set_placeholder_text(GTK_ENTRY(port),
                                   "Automatic WCH-Link adapter");
    gtk_editable_set_text(GTK_EDITABLE(port), options.port.c_str());
    gtk_widget_set_hexpand(port, true);
    simulation = gtk_check_button_new_with_label("Simulation");
    gtk_check_button_set_active(GTK_CHECK_BUTTON(simulation), options.simulate);
    add(conn, port);
    add(conn, simulation);
    connectButton = button("Connect", [this] {
      auto j = request("connect");
      put(j.get(), "simulate",
          gtk_check_button_get_active(GTK_CHECK_BUTTON(simulation)) != 0);
      if (!text(port).empty())
        put(j.get(), "port", text(port));
      send("action", j);
    });
    disconnectButton = button("Disconnect", [this] { action("disconnect"); });
    add(conn, connectButton);
    add(conn, disconnectButton);
    add(diagnostics, conn);
    statusDetails = label("Waiting for service status…", "diagnostics");
    gtk_label_set_selectable(GTK_LABEL(statusDetails), true);
    gtk_label_set_wrap(GTK_LABEL(statusDetails), true);
    add(diagnostics, statusDetails);
    gtk_stack_add_titled(GTK_STACK(stack), scrolled(diagnostics), "diagnostics",
                         "Diagnostics");
    auto footer = box(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_add_css_class(footer, "footer");
    margins(footer, 14);
    auto controls = box(GTK_ORIENTATION_HORIZONTAL, 8);
    for (auto p :
         {std::pair{"Pause", "pause"}, std::pair{"Resume", "resume"},
          std::pair{"Restart", "restart"}, std::pair{"Blank", "blank"}}) {
      auto w = button(p.first, [this, op = p.second] { action(op); });
      playback.push_back(w);
      add(controls, w);
    }
    auto spacer = box();
    gtk_widget_set_hexpand(spacer, true);
    add(controls, spacer);
    apply = button("Apply text", [this] { applyDraft(); }, "suggested-action");
    add(controls, apply);
    add(footer, controls);
    feedback = label("Your display stays unchanged until you Apply or use "
                     "playback controls.",
                     "muted");
    gtk_label_set_wrap(GTK_LABEL(feedback), true);
    gtk_label_set_lines(GTK_LABEL(feedback), 2);
    add(footer, feedback);
    add(shell, footer);
    g_signal_connect(gtk_text_view_get_buffer(GTK_TEXT_VIEW(message)),
                     "changed", G_CALLBACK(+[](GtkTextBuffer *, gpointer p) {
                       static_cast<Studio *>(p)->edited();
                     }),
                     this);
    for (auto w : {font, motion, modulation})
      g_signal_connect(w, "notify::selected",
                       G_CALLBACK(+[](GObject *, GParamSpec *, gpointer p) {
                         static_cast<Studio *>(p)->edited();
                       }),
                       this);
    for (auto w : {speed, peak, minimum, pulses})
      g_signal_connect(w, "value-changed",
                       G_CALLBACK(+[](GtkSpinButton *, gpointer p) {
                         static_cast<Studio *>(p)->edited();
                       }),
                       this);
    g_signal_connect(loop, "toggled",
                     G_CALLBACK(+[](GtkCheckButton *, gpointer p) {
                       static_cast<Studio *>(p)->edited();
                     }),
                     this);
    g_signal_connect(stack, "notify::visible-child-name",
                     G_CALLBACK(+[](GObject *, GParamSpec *, gpointer p) {
                       auto s = static_cast<Studio *>(p);
                       if (s->page() != "demo" && !s->demoLease.empty())
                         s->stopDemo();
                       s->updateButtons();
                       gtk_widget_queue_draw(s->previewArea);
                     }),
                     this);
    auto keys = gtk_event_controller_key_new();
    g_signal_connect(
        keys, "key-pressed",
        G_CALLBACK(+[](GtkEventControllerKey *, guint key, guint,
                       GdkModifierType mods, gpointer p) -> gboolean {
          auto s = static_cast<Studio *>(p);
          if ((mods & GDK_CONTROL_MASK) &&
              (key == GDK_KEY_Return || key == GDK_KEY_KP_Enter) &&
              gtk_widget_get_sensitive(s->apply)) {
            s->applyDraft();
            return true;
          }
          return false;
        }),
        this);
    gtk_widget_add_controller(window, keys);
    g_signal_connect(window, "close-request",
                     G_CALLBACK(+[](GtkWindow *, gpointer p) -> gboolean {
                       auto s = static_cast<Studio *>(p);
                       s->save();
                       s->closing = true;
                       if (s->timer) {
                         g_source_remove(s->timer);
                         s->timer = 0;
                       }
                       return false;
                     }),
                     this);
    setDraft(restoredDraft.get());
    gtk_stack_set_visible_child_name(GTK_STACK(stack),
                                     options.initialPage.c_str());
    updateButtons();
    gtk_window_present(GTK_WINDOW(window));
    if (options.check) {
      save();
      closing = true;
      g_idle_add(
          +[](gpointer p) -> gboolean {
            g_application_quit(G_APPLICATION(static_cast<Studio *>(p)->app));
            return G_SOURCE_REMOVE;
          },
          this);
      return;
    }
    auto weak = weak_from_this();
    worker.receive = [weak](Task task, Json result) {
      auto fn = new std::function<void()>(
          [weak, task = std::move(task), result = std::move(result)] {
            if (auto s = weak.lock())
              s->response(task, result);
          });
      g_main_context_invoke(
          nullptr,
          +[](gpointer p) -> gboolean {
            std::unique_ptr<std::function<void()>> f(
                static_cast<std::function<void()> *>(p));
            (*f)();
            return G_SOURCE_REMOVE;
          },
          fn);
    };
    worker.start(options);
    timer = g_timeout_add(
        16,
        +[](gpointer p) -> gboolean {
          return static_cast<Studio *>(p)->tick();
        },
        this);
  }
  gboolean tick() {
    if (closing)
      return G_SOURCE_REMOVE;
    auto now = g_get_monotonic_time();
    if (!statusPending && now - lastStatus > 600000) {
      statusPending = true;
      lastStatus = now;
      send("status", request("status"));
    }
    if (page() == "demo") {
      auto choice =
          int(gtk_drop_down_get_selected(GTK_DROP_DOWN(demoScene))) - 1;
      auto elapsed = uint64_t((now - demoStarted) / 1000);
      auto rate = unsigned(
          gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(demoSpeed)));
      auto level = unsigned(
          gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(demoLevel)));
      demoPixels = control::render_demo(elapsed, choice, rate, level);
      std::string name = control::demo_name(choice);
      gtk_label_set_text(GTK_LABEL(resource),
                         (name + " · full 0–100% PWM").c_str());
      gtk_label_set_text(GTK_LABEL(demoInfo),
                         demoLease.empty() ? "Preview only · no display changes"
                         : demoStopping
                             ? "Stopping display playback…"
                             : "Playing on all five tiles · LEVEL8 precision");
      gtk_widget_queue_draw(previewArea);
      if (!demoLease.empty() && !demoStopping && !demoFramePending &&
          now - lastDemoFrame >= 55556) {
        auto frame = request("stream_frame");
        put(frame.get(), "lease", demoLease);
        json_object_object_add(frame.get(), "deadline_ms",
                               json_object_new_int64(now / 1000 + 250));
        // Render the scheduled instant, so the board and live preview have the
        // same phase instead of delaying the animation by the UART lookahead.
        auto values = pixels(control::render_demo(elapsed + 250, choice, rate,
                                                  level));
        json_object_object_add(frame.get(), "pixels",
                               json_object_get(values.get()));
        demoFramePending = true;
        lastDemoFrame = now - lastDemoFrame > 111112
                            ? now
                            : lastDemoFrame + 55556;
        send("demo_frame", frame);
      }
    }
    if (!catalogPending && now - lastCatalog > 5000000) {
      catalogPending = true;
      lastCatalog = now;
      send("catalog", request("music_catalog"));
    }
    if (page() != "demo" && !previewPending && now - lastPreview > 90000) {
      previewPending = true;
      lastPreview = now;
      auto j = request("preview");
      auto d = draft();
      json_object_object_add(j.get(), "draft", json_object_get(d.get()));
      put(j.get(), "position_ms", int((now - started) / 1000));
      send("preview", j);
    }
    if (lastSave && now - lastSave > 700000)
      save();
    if (options.smoke) {
      smokeSteps++;
      if (smokeSteps == 5) {
        gtk_drop_down_set_selected(GTK_DROP_DOWN(font), 1);
        gtk_drop_down_set_selected(GTK_DROP_DOWN(modulation), 1);
        gtk_spin_button_set_value(GTK_SPIN_BUTTON(pulses), 2);
        paintPixels[0] = 100;
        paintPixels[319] = 25;
        gtk_editable_set_text(GTK_EDITABLE(presetName), "Studio smoke preset");
        savePreset(true);
        gtk_stack_set_visible_child_name(GTK_STACK(stack), "pixels");
      }
      if (smokeSteps == 8) {
        gtk_editable_set_text(GTK_EDITABLE(presetName),
                              "Temporary text preset");
        savePreset(false);
      }
      if (smokeSteps == 10) {
        auto before = presets.size();
        if (auto remove = findButton(presetList, "Delete")) {
          g_signal_emit_by_name(remove, "clicked");
          smokeDeleted = presets.size() + 1 == before;
        }
        if (auto load = findButton(presetList, "Load"))
          g_signal_emit_by_name(load, "clicked");
        gtk_stack_set_visible_child_name(GTK_STACK(stack), "pixels");
      }
      if (smokeSteps == 45) {
        gtk_stack_set_visible_child_name(GTK_STACK(stack), "demo");
        gtk_drop_down_set_selected(GTK_DROP_DOWN(demoScene), 5);
      }
      if (smokeSteps == 52 && connected && !busy)
        startDemo();
      if (smokeSteps == 68 && demoFrames > 0)
        stopDemo();
      if (smokeSteps >= 100) {
        smokePassed = smokeVerified && smokeDeleted && valid && fits &&
                      presets.size() > 0 && paintPixels[0] == 100 &&
                      paintPixels[319] == 25 && demoFrames > 0 &&
                      demoLease.empty() && !demoStopping;
        std::cout << (smokePassed ? "Studio smoke test passed"
                                  : "Studio smoke test failed")
                  << "\n";
        save();
        closing = true;
        timer = 0;
        g_application_quit(G_APPLICATION(app));
        return G_SOURCE_REMOVE;
      }
    }
    return G_SOURCE_CONTINUE;
  }
};
} // namespace
int main(int argc, char **argv) {
  Options options;
  bool librarySelected = false;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--simulate")
      options.simulate = true;
    else if (a == "--no-connect")
      options.autoconnect = false;
    else if (a == "--demo")
      options.initialPage = "demo";
    else if (a == "--smoke-test" || a == "--self-test") {
      options.smoke = true;
      options.simulate = true;
    } else if (a == "--check")
      options.check = true;
    else if ((a == "--port" || a == "--socket" || a == "--library") &&
             i + 1 < argc) {
      auto v = std::string(argv[++i]);
      if (a == "--port")
        options.port = v;
      else if (a == "--socket")
        options.socket = v;
      else {
        options.library = v;
        librarySelected = true;
      }
    } else if (a == "--help") {
      std::cout << "letki-control [--demo] [--simulate] [--no-connect] [--port PATH] "
                   "[--socket PATH]\nLetki Studio: text, PWM, pixel canvas and "
                   "presets. UART belongs to letkid.\n";
      return 0;
    } else {
      std::cerr << "Unknown or incomplete option: " << a << "\n";
      return 1;
    }
  }
  if (options.check || options.smoke) {
    options.simulate = true;
    if (options.check)
      options.autoconnect = false;
    GError *error = nullptr;
    auto directory = g_dir_make_tmp("letki-studio-test-XXXXXX", &error);
    if (!directory) {
      std::cerr << (error ? error->message : "Cannot create test directory")
                << '\n';
      g_clear_error(&error);
      return 1;
    }
    if (options.socket.empty())
      options.socket = std::string(directory) + "/display.sock";
    if (!librarySelected)
      options.library = std::string(directory) + "/library.json";
    g_free(directory);
  }
  if (options.simulate && !options.port.empty()) {
    std::cerr << "Simulation cannot be combined with a serial port.\n";
    return 1;
  }
  if (!std::filesystem::exists("host/control")) {
    std::error_code ec;
    auto executable = std::filesystem::read_symlink("/proc/self/exe", ec);
    auto root = executable.parent_path().parent_path().parent_path();
    if (std::filesystem::exists(root / "host/control"))
      std::filesystem::current_path(root);
  }
  auto studio = std::make_shared<Studio>(options);
  auto app =
      adw_application_new("io.github.letki.Studio", G_APPLICATION_NON_UNIQUE);
  studio->app = app;
  g_signal_connect(app, "activate",
                   G_CALLBACK(+[](GtkApplication *, gpointer p) {
                     static_cast<Studio *>(p)->build();
                   }),
                   studio.get());
  char *args[] = {argv[0], nullptr};
  int code = g_application_run(G_APPLICATION(app), 1, args);
  studio->closing = true;
  if (studio->timer)
    g_source_remove(studio->timer);
  studio->worker.stop();
  bool smokePass = studio->smokePassed;
  g_object_unref(app);
  return options.smoke && !smokePass ? 1 : code;
}
