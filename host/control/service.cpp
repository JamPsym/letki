#include "controller.hpp"
#include "ipc.hpp"
#include "music_demo.hpp"
#include <algorithm>
#include <cerrno>
#include <condition_variable>
#include <csignal>
#include <cstring>
#include <deque>
#include <fcntl.h>
#include <filesystem>
#include <glib.h>
#include <iostream>
#include <json-c/json.h>
#include <mutex>
#include <poll.h>
#include <set>
#include <sys/file.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>
namespace {
volatile sig_atomic_t stopping = 0;
void stop(int) { stopping = 1; }
struct Drop {
  void operator()(json_object *p) const {
    if (p)
      json_object_put(p);
  }
};
using Json = std::unique_ptr<json_object, Drop>;
Json object() { return Json(json_object_new_object()); }
json_object *field(json_object *j, const char *key) {
  json_object *v = nullptr;
  json_object_object_get_ex(j, key, &v);
  return v;
}
void add(json_object *j, const char *key, const std::string &v) {
  json_object_object_add(j, key,
                         json_object_new_string_len(v.data(), int(v.size())));
}
void add(json_object *j, const char *key, uint64_t v) {
  json_object_object_add(j, key, json_object_new_int64(int64_t(v)));
}
void flag(json_object *j, const char *key, bool v) {
  json_object_object_add(j, key, json_object_new_boolean(v));
}
std::string str(json_object *j, const char *key,
                const std::string &fallback = {}) {
  auto *v = field(j, key);
  if (!v)
    return fallback;
  if (!json_object_is_type(v, json_type_string))
    throw std::runtime_error(std::string(key) + " must be a string");
  std::string out(json_object_get_string(v),
                  size_t(json_object_get_string_len(v)));
  if (out.find('\0') != std::string::npos ||
      !g_utf8_validate(out.c_str(), out.size(), nullptr))
    throw std::runtime_error(std::string(key) +
                             " must be valid UTF-8 without NUL");
  return out;
}
unsigned number(json_object *j, const char *key, unsigned fallback, unsigned lo,
                unsigned hi) {
  auto *v = field(j, key);
  if (!v)
    return fallback;
  if (!json_object_is_type(v, json_type_int))
    throw std::runtime_error(std::string(key) + " must be an integer");
  int64_t n = json_object_get_int64(v);
  if (n < lo || n > hi)
    throw std::runtime_error(std::string(key) + " is out of range");
  return unsigned(n);
}
bool boolean(json_object *j, const char *key, bool fallback) {
  auto *v = field(j, key);
  if (!v)
    return fallback;
  if (!json_object_is_type(v, json_type_boolean))
    throw std::runtime_error(std::string(key) + " must be a boolean");
  return json_object_get_boolean(v);
}
Json parse(const std::string &line) {
  json_tokener *t = json_tokener_new();
  json_tokener_set_flags(t, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
  Json j(json_tokener_parse_ex(t, line.data(), int(line.size())));
  bool valid = json_tokener_get_error(t) == json_tokener_success;
  size_t end = json_tokener_get_parse_end(t);
  json_tokener_free(t);
  if (!valid || end != line.size() || !j ||
      !json_object_is_type(j.get(), json_type_object))
    throw std::runtime_error("Expected one valid UTF-8 JSON object");
  return j;
}
std::string dump(json_object *j) {
  return json_object_to_json_string_ext(j, JSON_C_TO_STRING_PLAIN);
}
Json ok() {
  auto j = object();
  add(j.get(), "v", uint64_t(1));
  flag(j.get(), "ok", true);
  return j;
}
Json error(const std::string &message) {
  auto j = object();
  add(j.get(), "v", uint64_t(1));
  flag(j.get(), "ok", false);
  add(j.get(), "error", message);
  return j;
}
unsigned choice(const std::string &value,
                std::initializer_list<const char *> values) {
  unsigned n = 0;
  for (auto v : values) {
    if (value == v)
      return n;
    ++n;
  }
  throw std::runtime_error("Unknown option: " + value);
}
control::TextProgram text(json_object *request) {
  auto *d = field(request, "draft");
  if (!d || !json_object_is_type(d, json_type_object))
    throw std::runtime_error("draft must be an object");
  control::Style style;
  style.font = control::Font(
      choice(str(d, "font", "compact"), {"compact", "large", "bold"}));
  style.modulation = control::Modulation(
      choice(str(d, "modulation", "steady"), {"steady", "breathe", "blink"}));
  style.minimum = number(d, "minimum", 5, 0, 100);
  style.pulses = number(d, "pulses", 2, 1, 6);
  return control::compile(
      str(d, "text"),
      control::Mode(choice(str(d, "motion", "scroll"),
                           {"scroll", "bounce", "fall", "still"})),
      number(d, "speed", 75, 10, 500), number(d, "brightness", 75, 0, 100),
      boolean(d, "loop", true), style);
}
letki::Frame pixels(json_object *request) {
  auto *a = field(request, "pixels");
  if (!a || !json_object_is_type(a, json_type_array) ||
      json_object_array_length(a) != 320)
    throw std::runtime_error(
        "pixels must contain exactly 320 row-major integer levels (0–100)");
  letki::Frame f{};
  for (unsigned i = 0; i < 320; i++) {
    auto *v = json_object_array_get_idx(a, i);
    if (!json_object_is_type(v, json_type_int) || json_object_get_int(v) < 0 ||
        json_object_get_int64(v) > 100)
      throw std::runtime_error("Every pixel must be an integer from 0 to 100");
    unsigned x = i % 40, y = i / 40;
    f[x / 8][y * 8 + x % 8] = uint8_t(json_object_get_int(v));
  }
  return f;
}
control::TextProgram picture(const letki::Frame &f) {
  // LEVEL8 bitmap: exact 0–100 levels, one shared global 40×8 asset.
  control::TextProgram p;
  p.width = 40;
  p.duration = 1000;
  auto &b = p.bytes;
  b = {'L', 'G', 'S', '1'};
  letki::put16(b, 368);
  b.insert(b.end(), {1, 1});
  letki::put32(b, 1000);
  letki::put32(b, 0);
  b.insert(b.end(), {2, 2, 0, 0});
  letki::put32(b, 0);
  letki::put32(b, 1000);
  letki::put32(b, 0);
  letki::put16(b, 48);
  letki::put16(b, 40);
  b.insert(b.end(), {8, 0});
  for (unsigned i = 0; i < 4; i++)
    letki::put16(b, 0);
  b.insert(b.end(), {100, 100});
  for (unsigned y = 0; y < 8; y++)
    for (unsigned x = 0; x < 40; x++)
      b.push_back(f[x / 8][y * 8 + x % 8]);
  return p;
}
class Service {
  control::Controller controller;
  std::mutex mutex;
  std::string lease, owner, port;
  unsigned ttl = 3000;
  uint64_t expires = 0, lastAttempt = 0, since = letki::monotonic_ms();
  bool retry, simulate;
  std::deque<std::string> events;
  std::multiset<uint64_t> pendingFrames;
  control::MusicDemo music;
  control::SongLaunch songLaunch;
  std::string songPhase, songError, songTitle;
  bool songHandoff = false, songReconnect = false, songRestoreSubmitted = false;
  bool songPreviousRetry = false;
  void restore_music() {
    if (songHandoff && songReconnect) {
      songPhase = "reconnecting";
      songRestoreSubmitted = false;
    } else {
      songPhase.clear();
      retry = songPreviousRetry;
    }
  }
  void event(const std::string &s) {
    events.push_back(s);
    if (events.size() > 30)
      events.pop_front();
    std::cerr << "letkid: " << s << '\n';
  }
  void tick_locked() {
    auto state = controller.snapshot();
    auto now = letki::monotonic_ms();
    if (songPhase == "preparing" && !state.busy) {
      try {
        music.start(songLaunch);
        songPhase = "playing";
        event("Music demo started: " + songTitle);
      } catch (const std::exception &e) {
        songError = e.what();
        restore_music();
      }
    }
    if (songPhase == "playing" || songPhase == "stopping") {
      if (!music.running()) {
        if (music.exit_code() != 0 && songPhase != "stopping")
          songError = "The music player exited with status " +
                      std::to_string(music.exit_code()) +
                      "; see build/control/music-demo.log";
        event("Music demo finished: " + songTitle);
        restore_music();
      }
    }
    if (songPhase == "reconnecting") {
      if (!songRestoreSubmitted && !state.busy) {
        songRestoreSubmitted = controller.submit(control::Action::Connect, {},
                                                 songLaunch.port, false);
        lastAttempt = now;
      } else if (songRestoreSubmitted && !state.busy) {
        if (!state.connected)
          songError = "Music ended; display reconnect failed: " + state.error;
        retry = songPreviousRetry;
        songPhase.clear();
      }
    }
    if (!lease.empty() &&
        (now >= expires || (!state.busy && !state.connected))) {
      if (state.busy)
        return;
      if (state.connected && state.streaming &&
          !controller.submit(control::Action::StreamEnd))
        return;
      event("Streaming lease released: " + owner);
      lease.clear();
      owner.clear();
      expires = 0;
      pendingFrames.clear();
    }
    if (retry && songPhase.empty() && lease.empty() && !state.connected &&
        !state.busy && now - lastAttempt >= 5000) {
      controller.submit(control::Action::Connect, {}, port, simulate);
      lastAttempt = now;
    }
  }
  Json accept(control::Action action, const control::TextProgram &p = {}) {
    auto s = controller.snapshot();
    if (action != control::Action::Connect &&
        action != control::Action::Disconnect && !s.connected)
      throw std::runtime_error("Connect the display first");
    if (!controller.submit(action, p))
      throw std::runtime_error(
          "Display is busy; retry after status.busy is false");
    auto j = ok();
    flag(j.get(), "accepted", true);
    add(j.get(), "job", controller.snapshot().revision);
    return j;
  }

public:
  Service(bool sim, bool connect, const std::string &selected)
      : port(selected), retry(connect), simulate(sim) {
    if (connect) {
      controller.submit(control::Action::Connect, {}, port, simulate);
      lastAttempt = letki::monotonic_ms();
    }
  }
  void tick() {
    std::lock_guard<std::mutex> guard(mutex);
    tick_locked();
  }
  Json route(json_object *r) {
    std::lock_guard<std::mutex> guard(mutex);
    tick_locked();
    if (number(r, "v", 0, 1, 1) != 1)
      throw std::runtime_error("Only API version 1 is supported");
    std::string op = str(r, "op");
    auto s = controller.snapshot();
    if (op == "status") {
      auto j = ok();
      flag(j.get(), "connected", s.connected);
      flag(j.get(), "busy", s.busy);
      flag(j.get(), "simulated", s.simulated);
      flag(j.get(), "streaming", s.streaming);
      add(j.get(), "streamed", s.streamed);
      add(j.get(), "baud", uint64_t(s.baud));
      add(j.get(), "transport_retries", s.retries);
      add(j.get(), "transport_invalid", s.invalid);
      add(j.get(), "frame_transfer_ms", s.frame_transfer_ms);
      add(j.get(), "stream_late", s.stream_late);
      add(j.get(), "stream_dropped", s.stream_dropped);
      json_object_object_add(j.get(), "stream_fps",
                             json_object_new_double(s.stream_fps));
      auto now = letki::monotonic_ms();
      add(j.get(), "stream_owner", owner);
      add(j.get(), "lease_remaining_ms", expires > now ? expires - now : 0);
      add(j.get(), "port", s.port);
      add(j.get(), "message", s.message);
      add(j.get(), "last_error", s.error);
      flag(j.get(), "music_active", !songPhase.empty());
      add(j.get(), "music_state", songPhase);
      add(j.get(), "music_title", songTitle);
      add(j.get(), "music_error", songError);
      add(j.get(), "revision", s.revision);
      add(j.get(), "applied", s.applied);
      add(j.get(), "program_bytes", s.applied_program.size());
      add(j.get(), "uptime_ms", letki::monotonic_ms() - since);
      auto *nodes = json_object_new_array();
      for (unsigned n = 0; n < 5 && s.connected; n++) {
        auto *o = json_object_new_object();
        auto &i = s.nodes[n];
        add(o, "index", uint64_t(n));
        add(o, "id", i.uid);
        add(o, "arena", uint64_t(i.arena));
        add(o, "bytes", uint64_t(i.length));
        add(o, "storage", uint64_t(i.storage));
        add(o, "slots", uint64_t(i.slots));
        add(o, "errors", uint64_t(i.errors));
        add(o, "drops", uint64_t(i.drops));
        add(o, "late", uint64_t(i.late));
        if (i.raw.size() > 32) {
          flag(o, "paused", (i.raw[20] & 1) != 0);
          add(o, "brightness", uint64_t(i.raw[32]));
        }
        json_object_array_add(nodes, o);
      }
      json_object_object_add(j.get(), "nodes", nodes);
      if (s.simulated) {
        auto *a = json_object_new_array_ext(320);
        for (unsigned y = 0; y < 8; y++)
          for (unsigned x = 0; x < 40; x++)
            json_object_array_add(
                a, json_object_new_int(s.pixels[x / 8][y * 8 + x % 8]));
        json_object_object_add(j.get(), "simulation_pixels", a);
      }
      auto *history = json_object_new_array();
      for (auto &e : events)
        json_object_array_add(history, json_object_new_string(e.c_str()));
      json_object_object_add(j.get(), "events", history);
      return j;
    }
    if (op == "music_catalog") {
      auto j = ok();
      auto *list = json_object_new_array();
      for (const auto &song : control::song_demos()) {
        auto *o = json_object_new_object();
        add(o, "id", song.id);
        add(o, "title", song.title);
        add(o, "description", song.description);
        auto missing = control::MusicDemo::unavailable(song);
        flag(o, "available", missing.empty());
        add(o, "reason", missing);
        json_object_array_add(list, o);
      }
      json_object_object_add(j.get(), "songs", list);
      return j;
    }
    if (op == "music_stop") {
      if (songPhase == "preparing")
        restore_music();
      else if (songPhase == "playing") {
        music.stop();
        songPhase = "stopping";
      }
      auto j = ok();
      flag(j.get(), "accepted", true);
      return j;
    }
    if (op == "preview") {
      auto p = text(r);
      control::Preview preview;
      preview.set(p);
      auto f = preview.frame(number(r, "position_ms", 0, 0, 2147483647));
      auto j = ok();
      unsigned capacity = 752;
      if (s.connected)
        for (auto &n : s.nodes)
          capacity = std::min(capacity, n.arena);
      add(j.get(), "width", uint64_t(p.width));
      add(j.get(), "bytes", p.bytes.size());
      add(j.get(), "duration_ms", uint64_t(p.duration));
      add(j.get(), "tracks", uint64_t(p.bytes[6]));
      add(j.get(), "capacity", uint64_t(capacity));
      flag(j.get(), "fits", p.bytes.size() <= capacity);
      add(j.get(), "canonical_text", p.text);
      auto *a = json_object_new_array_ext(320);
      for (unsigned y = 0; y < 8; y++)
        for (unsigned x = 0; x < 40; x++)
          json_object_array_add(a,
                                json_object_new_int(f[x / 8][y * 8 + x % 8]));
      json_object_object_add(j.get(), "pixels", a);
      return j;
    }
    if (!songPhase.empty())
      throw std::runtime_error("A music demo owns the display; stop it first");
    if (op == "music_start") {
      auto id = str(r, "id");
      const control::SongDemo *selected = nullptr;
      for (const auto &song : control::song_demos())
        if (song.id == id)
          selected = &song;
      if (!selected)
        throw std::runtime_error("Unknown music demo");
      auto missing = control::MusicDemo::unavailable(*selected);
      if (!missing.empty())
        throw std::runtime_error(missing);
      if (!lease.empty())
        throw std::runtime_error("Display is leased by " + owner);
      if (s.busy)
        throw std::runtime_error("Display is busy");
      control::SongLaunch launch;
      launch.id = id;
      launch.simulate = boolean(r, "simulate", false);
      launch.silent = boolean(r, "silent", false);
      launch.headless = boolean(r, "headless", false);
      launch.duration_ms = number(r, "duration_ms", 0, 0, 3600000);
      launch.wayland = str(r, "wayland_display");
      launch.display = str(r, "display");
      if (launch.wayland.size() > 128 || launch.display.size() > 128)
        throw std::runtime_error("Invalid desktop display address");
      bool handoff = !launch.simulate;
      if (handoff) {
        if (!s.connected || s.simulated)
          throw std::runtime_error(
              "Connect the physical chain first, or choose PC only");
        for (const auto &n : s.nodes) {
          unsigned used = n.storage == 0 ? n.length : 0;
          if (used > n.arena || n.arena - used < 160)
            throw std::runtime_error("Music needs 160 spare RAM bytes; apply a "
                                     "shorter message first");
        }
        launch.port = s.port;
        if (!controller.submit(control::Action::Disconnect))
          throw std::runtime_error("Display is busy");
      }
      songLaunch = launch;
      songTitle = selected->title;
      songError.clear();
      songHandoff = handoff;
      songReconnect = handoff && s.connected;
      songPreviousRetry = retry;
      songPhase = "preparing";
      retry = false;
      auto j = ok();
      flag(j.get(), "accepted", true);
      return j;
    }
    if (op == "stream_frame" || op == "stream_end") {
      if (lease.empty() || str(r, "lease") != lease ||
          letki::monotonic_ms() >= expires)
        throw std::runtime_error("A valid streaming lease is required");
      if (op == "stream_end") {
        auto j = accept(control::Action::StreamEnd);
        lease.clear();
        owner.clear();
        expires = 0;
        pendingFrames.clear();
        return j;
      }
      auto frame = pixels(r);
      uint64_t deadline = 0;
      if (auto *v = field(r, "deadline_ms")) {
        if (!json_object_is_type(v, json_type_int) ||
            json_object_get_int64(v) < 0)
          throw std::runtime_error(
              "deadline_ms must be a monotonic millisecond timestamp");
        deadline = uint64_t(json_object_get_int64(v));
        auto now = letki::monotonic_ms();
        if (deadline < now + 40 || deadline > now + 1000)
          throw std::runtime_error(
              "Frame deadline must be 40–1000ms ahead of CLOCK_MONOTONIC");
      }
      if (!s.streaming)
        throw std::runtime_error(s.busy ? "Display is busy starting stream"
                                        : "Stream is not active");
      auto now = letki::monotonic_ms();
      while (!pendingFrames.empty() && *pendingFrames.begin() <= now)
        pendingFrames.erase(pendingFrames.begin());
      unsigned slots = 16;
      for (const auto &n : s.nodes)
        slots = std::min(slots, n.slots);
      if (pendingFrames.size() >= slots)
        throw std::runtime_error("Display is busy presenting queued frames; "
                                 "retry with backpressure");
      if (!deadline)
        deadline = now + 120;
      if (!controller.submitFrame(frame, deadline))
        throw std::runtime_error("Display is busy; retry frame");
      pendingFrames.insert(deadline +
                           30); // Presentation + scan boundary margin.
      expires = letki::monotonic_ms() + ttl;
      auto j = ok();
      flag(j.get(), "accepted", true);
      return j;
    }
    if (!lease.empty() && op != "blank")
      throw std::runtime_error("Display is leased by " + owner);
    if (op == "stream_begin") {
      auto name = str(r, "owner", "external app");
      if (name.empty() || name.size() > 80)
        throw std::runtime_error("owner must contain 1–80 UTF-8 bytes");
      auto duration = number(r, "ttl_ms", 3000, 500, 10000);
      auto format = number(r, "format", 1, 1, 2);
      if (!s.connected)
        throw std::runtime_error("Connect the display first");
      const unsigned required = format == 2 ? 160 : 96;
      for (const auto &node : s.nodes) {
        const unsigned used = node.storage == 0 ? node.length : 0;
        if (used > node.arena || node.arena - used < required)
          throw std::runtime_error(
              "Streaming needs " + std::to_string(required) +
              " spare RAM bytes; apply a shorter message first");
      }
      if (!controller.submit(control::Action::StreamBegin, {}, {}, false,
                             format))
        throw std::runtime_error(
            "Display is busy; retry after status.busy is false");
      auto j = ok();
      flag(j.get(), "accepted", true);
      add(j.get(), "format", uint64_t(format));
      gchar *token = g_uuid_string_random();
      lease = token;
      g_free(token);
      owner = name;
      ttl = duration;
      expires = letki::monotonic_ms() + ttl;
      pendingFrames.clear();
      add(j.get(), "lease", lease);
      add(j.get(), "ttl_ms", uint64_t(ttl));
      event("Streaming lease granted: " + owner);
      return j;
    }
    if (op == "connect") {
      simulate = boolean(r, "simulate", false);
      port = str(r, "port");
      if (s.busy)
        throw std::runtime_error("Display is busy");
      if (!controller.submit(control::Action::Connect, {}, port, simulate))
        throw std::runtime_error("Display is busy");
      retry = true;
      lastAttempt = letki::monotonic_ms();
      auto j = ok();
      flag(j.get(), "accepted", true);
      return j;
    }
    if (op == "disconnect") {
      auto j = accept(control::Action::Disconnect);
      retry = false;
      event("UART released to other applications");
      return j;
    }
    if (op == "text" || op == "pixels") {
      auto p = op == "text" ? text(r) : picture(pixels(r));
      if (!s.connected)
        throw std::runtime_error("Connect the display first");
      for (auto &n : s.nodes)
        if (p.bytes.size() > n.arena)
          throw std::runtime_error("Program exceeds tile RAM; shorten text, "
                                   "select a smaller font or reduce pulses");
      auto j = accept(control::Action::Apply, p);
      add(j.get(), "bytes", p.bytes.size());
      event("RAM program accepted: " + std::to_string(p.bytes.size()) +
            " bytes/tile");
      return j;
    }
    for (auto item : {std::pair{"pause", control::Action::Pause},
                      {"resume", control::Action::Resume},
                      {"restart", control::Action::Restart},
                      {"blank", control::Action::Blank}})
      if (op == item.first) {
        auto j = accept(item.second);
        if (op == "blank") {
          lease.clear();
          owner.clear();
          expires = 0;
          pendingFrames.clear();
        }
        return j;
      }
    throw std::runtime_error("Unknown operation: " + op);
  }
};
} // namespace
int main(int argc, char **argv) {
  try {
    bool sim = false, autoconnect = true;
    std::string path = control::ipc::default_socket(), port;
    for (int i = 1; i < argc; i++) {
      std::string a = argv[i];
      if (a == "--simulate")
        sim = true;
      else if (a == "--no-connect")
        autoconnect = false;
      else if ((a == "--socket" || a == "--port") && i + 1 < argc) {
        if (a == "--socket")
          path = argv[++i];
        else
          port = argv[++i];
      } else if (a == "--help") {
        std::cout << "letkid [--simulate] [--no-connect] [--socket PATH] "
                     "[--port PATH]\n";
        return 0;
      } else
        throw std::runtime_error("Unknown/incomplete option: " + a);
    }
    if (sim && !port.empty())
      throw std::runtime_error("--simulate and --port are mutually exclusive");
    // Locate real C preview relative to the installed-in-checkout executable.
    char exe[4096];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n > 0) {
      exe[n] = 0;
      auto root =
          std::filesystem::path(exe).parent_path().parent_path().parent_path();
      if (std::filesystem::exists(root / "build/general/libletki-general.so"))
        std::filesystem::current_path(root);
    }
    umask(0077);
    auto directory = std::filesystem::path(path).parent_path();
    std::filesystem::create_directories(directory);
    struct stat st{};
    if (lstat(directory.c_str(), &st) || !S_ISDIR(st.st_mode) ||
        st.st_uid != getuid() || (st.st_mode & 0077))
      throw std::runtime_error(
          "Socket directory must be owned by you with mode0700: " +
          directory.string());
    umask(0077);
    int lock = open((path + ".lock").c_str(),
                    O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB))
      throw std::runtime_error("Another display service owns this socket");
    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    if (path.size() >= sizeof(address.sun_path))
      throw std::runtime_error("Socket path is too long");
    std::memcpy(address.sun_path, path.c_str(), path.size() + 1);
    if (!lstat(path.c_str(), &st)) {
      if (!S_ISSOCK(st.st_mode) || st.st_uid != getuid())
        throw std::runtime_error("Refusing to replace non-service socket path");
      int probe =
          socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
      int result = connect(probe, reinterpret_cast<sockaddr *>(&address),
                           sizeof(address));
      int connectError = errno;
      if (probe >= 0)
        close(probe);
      if (result == 0 || connectError != ECONNREFUSED)
        throw std::runtime_error(
            "Another process is listening on this socket path");
      unlink(path.c_str());
    }
    int server = socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
    if (server < 0 ||
        bind(server, reinterpret_cast<sockaddr *>(&address), sizeof(address)) ||
        listen(server, 16))
      throw std::runtime_error("Cannot listen on display socket: " +
                               std::string(strerror(errno)));
    chmod(path.c_str(), 0600);
    signal(SIGTERM, stop);
    signal(SIGINT, stop);
    signal(SIGPIPE, SIG_IGN);
    Service service(sim, autoconnect, port);
    std::mutex activeMutex;
    std::condition_variable finished;
    unsigned active = 0;
    std::cerr << "letkid: listening on " << path << '\n';
    while (!stopping) {
      service.tick();
      pollfd ready{server, POLLIN, 0};
      int result = poll(&ready, 1, 100);
      if (result <= 0)
        continue;
      int client =
          accept4(server, nullptr, nullptr, SOCK_CLOEXEC | SOCK_NONBLOCK);
      if (client < 0)
        continue;
      {
        std::lock_guard<std::mutex> guard(activeMutex);
        if (active >= 16) {
          close(client);
          continue;
        }
        ++active;
      }
      std::thread([&, client] {
        const auto until = letki::monotonic_ms() + 2000;
        auto ready = [&](short events) {
          while (!stopping && letki::monotonic_ms() < until) {
            pollfd p{client, events, 0};
            int result = poll(
                &p, 1,
                int(std::min(uint64_t(100), until - letki::monotonic_ms())));
            if (result > 0 && (p.revents & (events | POLLHUP)))
              return true;
            if (result < 0 && errno != EINTR)
              return false;
          }
          return false;
        };
        std::string line;
        Json response;
        try {
          char bytes[2048];
          bool done = false;
          while (!done) {
            if (!ready(POLLIN))
              throw std::runtime_error("Incomplete or timed-out JSON request");
            ssize_t got = recv(client, bytes, sizeof(bytes), 0);
            if (got < 0 && (errno == EINTR || errno == EAGAIN))
              continue;
            if (got <= 0)
              throw std::runtime_error("Incomplete or timed-out JSON request");
            line.append(bytes, size_t(got));
            if (line.size() > 65536)
              throw std::runtime_error("Request exceeds 64KiB limit");
            auto end = line.find('\n');
            if (end != std::string::npos) {
              line.resize(end);
              done = true;
            }
          }
          auto request = parse(line);
          response = service.route(request.get());
        } catch (const std::exception &e) {
          response = error(e.what());
        }
        auto wire = dump(response.get()) + '\n';
        size_t at = 0;
        while (at < wire.size() && ready(POLLOUT)) {
          ssize_t sent =
              send(client, wire.data() + at, wire.size() - at, MSG_NOSIGNAL);
          if (sent < 0 && (errno == EINTR || errno == EAGAIN))
            continue;
          if (sent <= 0)
            break;
          at += size_t(sent);
        }
        close(client);
        {
          std::lock_guard<std::mutex> guard(activeMutex);
          --active;
        }
        finished.notify_one();
      }).detach();
    }
    close(server);
    unlink(path.c_str());
    {
      std::unique_lock<std::mutex> guard(activeMutex);
      finished.wait(guard, [&] { return active == 0; });
    }
    close(lock);
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "letkid: " << e.what() << '\n';
    return 1;
  }
}
