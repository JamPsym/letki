#include "player.hpp"
#include <SDL.h>
#include <algorithm>
#include <cmath>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <future>
#include <iomanip>
#include <iostream>
#include <json-c/json.h>
#include <stdexcept>
#include <thread>
namespace {
volatile sig_atomic_t interrupted = 0;
void signal_stop(int) { interrupted = 1; }
struct Options {
  std::string show = "config/player/my-cyganie-full.json", audio, video, frames,
              format = "level8", port, report = "build/player/last-run.json";
  bool silent = false, headless = false, check = false, inspect = false,
       analysis = false, simulate = false, auto_selected = false;
  unsigned baud = 230400, fps = 12;
  double limit = 0, seek = 0;
};
Options options(int argc, char **argv) {
  Options o;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    auto value = [&]() {
      if (++i >= argc)
        throw std::runtime_error("Missing argument for " + a);
      return std::string(argv[i]);
    };
    if (a == "--show")
      o.show = value();
    else if (a == "--audio")
      o.audio = value();
    else if (a == "--video")
      o.video = value();
    else if (a == "--frames")
      o.frames = value();
    else if (a == "--port")
      o.port = value();
    else if (a == "--report")
      o.report = value();
    else if (a == "--baud")
      o.baud = std::stoul(value());
    else if (a == "--format")
      o.format = value();
    else if (a == "--fps")
      o.fps = std::stoul(value());
    else if (a == "--seconds")
      o.limit = std::stod(value());
    else if (a == "--seek")
      o.seek = std::stod(value());
    else if (a == "--simulate")
      o.simulate = true;
    else if (a == "--silent")
      o.silent = true;
    else if (a == "--headless")
      o.headless = true;
    else if (a == "--check")
      o.check = true;
    else if (a == "--analyze")
      o.analysis = true;
    else if (a == "--inspect")
      o.inspect = true;
    else if (a == "--help") {
      std::cout
          << "letki-player [--show FILE] [--audio FILE] [--port TTY] [--baud "
             "115200|230400]\n             [--fps 1..25] [--seek SECONDS] "
             "[--seconds SECONDS] [--silent]\n             [--video FILE] "
             "(PC preview only)\n             "
             "[--headless] [--simulate] "
             "[--check] [--frames FILE] [--inspect] [--analyze] [--report "
             "FILE]\nDefault: "
             "five-tile "
             "auto-connect to the WCH-Link chain, or PC simulation if absent.\n"
             "--simulate forces PC simulation; --port PATH selects an "
             "adapter.\n--check: "
             "accelerated real firmware simulation, without audio or "
             "hardware.\nSpace: pause/resume. Left/right: seek 5 seconds. "
             "Home: restart. V: PC video toggle. N: next instrument. Esc: "
             "exit.\n";
      exit(0);
    } else
      throw std::runtime_error("Unknown option: " + a);
  }
  if (o.fps < 1 || o.fps > 25 || (o.baud != 115200 && o.baud != 230400) ||
      !std::isfinite(o.seek) || o.seek < 0 || !std::isfinite(o.limit) ||
      o.limit < 0)
    throw std::runtime_error("Invalid fps, baud, seek or duration");
  if (o.format != "gray4" && o.format != "level8")
    throw std::runtime_error("Format must be gray4 or level8");
  if (!o.frames.empty() && !o.check)
    throw std::runtime_error("--frames requires offline --check");
  if (o.check && (!o.port.empty() || o.inspect))
    throw std::runtime_error("--check cannot access hardware");
  if (o.analysis && !o.port.empty())
    throw std::runtime_error("--analyze cannot access hardware");
  if (o.simulate && !o.port.empty())
    throw std::runtime_error("--simulate cannot be combined with --port");
  return o;
}
struct Window {
  SDL_Window *window = nullptr;
  SDL_Renderer *renderer = nullptr;
  SDL_Texture *texture = nullptr;
  int tw = 0, th = 0;
  explicit Window(bool movie) {
    if (SDL_Init(SDL_INIT_VIDEO))
      throw std::runtime_error(SDL_GetError());
    window = SDL_CreateWindow("Letki music engine", SDL_WINDOWPOS_CENTERED,
                              SDL_WINDOWPOS_CENTERED, 1060, movie ? 780 : 300,
                              SDL_WINDOW_RESIZABLE);
    if (window)
      renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
    if (!window || !renderer) {
      if (window)
        SDL_DestroyWindow(window);
      SDL_Quit();
      throw std::runtime_error(SDL_GetError());
    }
  }
  ~Window() {
    SDL_DestroyTexture(texture);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
  }
  void draw(const letki::Frame &f, const std::string &label,
            const letki::VideoImage *movie) {
    SDL_SetWindowTitle(window, label.c_str());
    int w, h;
    SDL_GetRendererOutputSize(renderer, &w, &h);
    SDL_SetRenderDrawColor(renderer, 10, 13, 20, 255);
    SDL_RenderClear(renderer);
    int panel = movie ? std::max(140, h / 3) : h, video_height = h - panel;
    if (movie) {
      if (!texture || tw != movie->width || th != movie->height) {
        SDL_DestroyTexture(texture);
        tw = movie->width;
        th = movie->height;
        texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGB24,
                                    SDL_TEXTUREACCESS_STREAMING, tw, th);
        if (!texture)
          throw std::runtime_error(SDL_GetError());
      }
      if (SDL_UpdateTexture(texture, nullptr, movie->rgb.data(), movie->stride))
        throw std::runtime_error(SDL_GetError());
      double scale = std::min(std::max(1, w - 32) / double(tw),
                              std::max(1, video_height - 24) / double(th));
      SDL_Rect destination{
          int((w - tw * scale) / 2), int((video_height - th * scale) / 2),
          std::max(1, int(tw * scale)), std::max(1, int(th * scale))};
      SDL_RenderCopy(renderer, texture, nullptr, &destination);
    }
    double cell = std::max(1., std::min((w - 50) / 42., (panel - 32) / 8.));
    int left = int((w - cell * 42) / 2),
        top = video_height + int((panel - cell * 8) / 2);
    for (unsigned t = 0; t < 5; t++)
      for (unsigned y = 0; y < 8; y++)
        for (unsigned x = 0; x < 8; x++) {
          double v = std::sqrt(f[t][y * 8 + x] / 100.);
          SDL_SetRenderDrawColor(renderer, Uint8(30 + 225 * v),
                                 Uint8(21 + 138 * v), Uint8(13 + 36 * v), 255);
          SDL_Rect r{left + int((t * 8 + t * .5 + x) * cell),
                     top + int(y * cell), std::max(1, int(cell) - 4),
                     std::max(1, int(cell) - 4)};
          SDL_RenderFillRect(renderer, &r);
        }
    SDL_RenderPresent(renderer);
  }
};

void report(const Options &o, const letki::Show &s, uint64_t sent,
            uint64_t skipped, uint64_t late, uint64_t warnings,
            uint64_t retries, uint64_t invalid, bool retained, double seconds,
            const std::string &status, uint64_t draws = 0, uint64_t draw_gap = 0) {
  auto j = json_object_new_object();
  auto add = [&](const char *k, json_object *v) {
    json_object_object_add(j, k, v);
  };
  add("show", json_object_new_string(s.name.c_str()));
  add("status", json_object_new_string(status.c_str()));
  add("hardware", json_object_new_boolean(!o.port.empty()));
  add("serial_port", json_object_new_string(o.port.c_str()));
  add("connection", json_object_new_string(o.port.empty()    ? "simulation"
                                           : o.auto_selected ? "automatic"
                                                             : "explicit"));
  add("audio_clock", json_object_new_string(
                         o.check    ? "accelerated firmware simulation"
                         : o.silent ? "steady clock (silent)"
                                    : "PortAudio DAC presentation timestamp"));
  add("frames", json_object_new_int64(sent));
  add("preview_draws", json_object_new_int64(draws));
  add("preview_max_gap_ms", json_object_new_int64(draw_gap));
  add("preview_fps", json_object_new_double(seconds > 0 ? draws / seconds : 0));
  add("skipped", json_object_new_int64(skipped));
  add("late_uploads", json_object_new_int64(late));
  add("audio_warnings", json_object_new_int64(warnings));
  add("retries", json_object_new_int64(retries));
  add("invalid_replies", json_object_new_int64(invalid));
  add("flash_programs_retained", json_object_new_boolean(retained));
  add("elapsed_seconds", json_object_new_double(seconds));
  add("fps", json_object_new_int(o.fps));
  add("seek_seconds", json_object_new_double(o.seek));
  add("wall_limit_seconds", json_object_new_double(o.limit));
  add("pixel_format", json_object_new_string(o.format.c_str()));
  add("fft_bands", json_object_new_int(24));
  add("analysis_hz", json_object_new_int(50));
  add("video", json_object_new_string(s.video.c_str()));
  add("video_target", json_object_new_string("PC preview only"));
  add("video_on_leds", json_object_new_boolean(false));
  add("optical_timing_measured", json_object_new_boolean(false));
  if (!std::filesystem::path(o.report).parent_path().empty())
    std::filesystem::create_directories(
        std::filesystem::path(o.report).parent_path());
  int result =
      json_object_to_file_ext(o.report.c_str(), j, JSON_C_TO_STRING_PRETTY);
  json_object_put(j);
  if (result)
    throw std::runtime_error("Cannot write playback report");
}
} // namespace
int main(int argc, char **argv) {
  try {
    auto o = options(argc, argv);
    std::signal(SIGINT, signal_stop);
    std::signal(SIGTERM, signal_stop);
    // Offline preparation bypasses discovery entirely, even with attached
    // boards.
    bool offline = o.check || o.analysis || o.simulate;
    if (!offline && o.port.empty()) {
      o.port = letki::discover_serial();
      o.auto_selected = !o.port.empty();
      if (o.port.empty() && o.inspect)
        throw std::runtime_error(
            "No WCH-Link serial adapter found; connect it or use --port PATH");
      if (o.port.empty())
        std::cout << "No WCH-Link detected; using PC simulation.\n"
                  << std::flush;
    }
    std::unique_ptr<letki::Chain> chain;
    if (o.port.empty()) {
      chain = std::make_unique<letki::Chain>(letki::simulation());
    } else {
      std::cout << "Connecting to " << o.port << "...\n" << std::flush;
      try {
        chain = std::make_unique<letki::Chain>(letki::serial(o.port));
      } catch (const letki::ReplyTimeout &) {
        std::cout
            << "UART not responding; waiting for the interrupted session's "
               "10-second baud lease to expire...\n"
            << std::flush;
        auto until = letki::monotonic_ms() + 10500;
        while (letki::monotonic_ms() < until) {
          if (interrupted)
            throw std::runtime_error("Connection cancelled");
          std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        chain = std::make_unique<letki::Chain>(letki::serial(o.port));
      }
      std::cout << "Connected to all five Letki boards"
                << (o.auto_selected ? " (auto-detected)" : "") << ".\n"
                << std::flush;
    }
    chain->format = o.format == "level8" ? 2 : 1;
    if (o.inspect) {
      chain->inspect();
      for (unsigned i = 0; i < 5; i++)
        std::cout << i << " " << chain->info[i].uid
                  << " program=" << chain->info[i].length
                  << " storage=" << chain->info[i].storage
                  << " uart_errors=" << chain->info[i].errors
                  << " drops=" << chain->info[i].drops << "\n";
      return 0;
    }
    auto show = letki::Show::load(o.show);
    if (!o.audio.empty())
      show.audio = o.audio;
    if (show.audio.empty())
      throw std::runtime_error(
          "Provide --audio /path/to/recording.flac for this show");
    std::cout << "Analyzing " << show.audio << " ...\n" << std::flush;
    letki::Media media(show.audio);
    if (o.analysis) {
      auto object = json_object_new_object();
      auto bass = json_object_new_array(), treble = json_object_new_array();
      unsigned low = 0, high = 0;
      for (size_t i = 0; i < media.features.size(); i++) {
        auto &f = media.features[i];
        double time = double(i * std::max(1, media.rate / 50)) / media.rate;
        auto event = [&](float strength) {
          auto e = json_object_new_object();
          json_object_object_add(e, "at", json_object_new_double(time));
          json_object_object_add(e, "strength",
                                 json_object_new_double(strength));
          return e;
        };
        if (f.bass_count != low) {
          low = f.bass_count;
          json_object_array_add(bass, event(f.bass_hit));
        }
        if (f.treble_count != high) {
          high = f.treble_count;
          json_object_array_add(treble, event(f.treble_hit));
        }
      }
      json_object_object_add(object, "audio",
                             json_object_new_string(media.path.c_str()));
      json_object_object_add(object, "duration",
                             json_object_new_double(media.duration()));
      json_object_object_add(object, "fft_bands", json_object_new_int(24));
      json_object_object_add(object, "bass_events", bass);
      json_object_object_add(object, "treble_events", treble);
      if (!std::filesystem::path(o.report).parent_path().empty())
        std::filesystem::create_directories(
            std::filesystem::path(o.report).parent_path());
      int error = json_object_to_file_ext(o.report.c_str(), object,
                                          JSON_C_TO_STRING_PRETTY);
      json_object_put(object);
      if (error)
        throw std::runtime_error("Cannot write analysis");
      std::cout << low << " bass attacks, " << high << " treble attacks -> "
                << o.report << "\n";
      return 0;
    }
    if (!o.video.empty())
      show.video = o.video;
    std::unique_ptr<letki::Video> video;
    if (!o.check && !o.headless && !show.video.empty())
      video = std::make_unique<letki::Video>(show.video);
    bool video_enabled = true;
    auto draw_frame = [&](double t) { return letki::render(show, media, t); };
    double total = show.intro + media.duration();
    if (o.seek >= total)
      throw std::runtime_error("Seek is beyond the show");
    if (video)
      video->image(std::max(0., o.seek - show.intro));
    std::cout << show.name << ": " << std::fixed << std::setprecision(2)
              << media.duration() << "s audio, " << show.intro
              << "s introduction, " << o.fps << " fps\n";
    if (o.check) {
      uint64_t sent = 0;
      std::ofstream frames;
      if (!o.frames.empty()) {
        auto parent = std::filesystem::path(o.frames).parent_path();
        if (!parent.empty())
          std::filesystem::create_directories(parent);
        frames.open(o.frames, std::ios::binary);
        if (!frames)
          throw std::runtime_error("Cannot open offline frame export");
        frames << "LETKI-FRAMES 1 40 8 " << o.fps << " "
               << std::setprecision(17) << o.seek << "\n";
      }
      double end = o.limit ? std::min(total, o.seek + o.limit) : total;
      // The actual C nodes validate/queue/commit each frame; verify their
      // presented pixels after advancing to its deadline. No serial or audio
      // device is opened.
      chain->prepare();
      uint64_t base = letki::monotonic_ms() + 2000;
      for (double t = o.seek; t < end; t += 1. / o.fps) {
        auto f = draw_frame(t);
        if (frames.is_open()) {
          static_assert(sizeof(f) == 320, "Offline frame layout");
          frames.write(reinterpret_cast<const char *>(f.data()), sizeof(f));
          if (!frames)
            throw std::runtime_error("Offline frame export failed");
        }
        chain->frame(f, base);
        auto actual = chain->pixels(base);
        for (unsigned n = 0; n < 5; n++)
          for (unsigned p = 0; p < 64; p++) {
            unsigned q = (f[n][p] * 15 + 50) / 100;
            unsigned expected = o.format == "level8" ? f[n][p] : q * 100 / 15;
            if (actual[n][p] != expected)
              throw std::runtime_error("Firmware simulation pixel mismatch");
          }
        base += uint64_t(std::llround(1000. / o.fps));
        sent++;
      }
      report(o, show, sent, 0, 0, 0, chain->retries, chain->invalid, false,
             end - o.seek, "checked");
      std::cout << "Checked " << sent
                << " frames against the real C firmware.\n";
      return 0;
    }
    // Decode and validate before changing physical display state.
    if (o.baud != 115200)
      chain->set_baud(o.baud);
    chain->prepare();
    unsigned capacity_fps = std::max(1U, (chain->slots - 1) * 4);
    if (o.fps > capacity_fps) {
      o.fps = capacity_fps;
      std::cout << "Queue capacity limits this run to " << o.fps << " fps\n";
    }
    std::unique_ptr<Window> window;
    if (!o.headless)
      window = std::make_unique<Window>(bool(video));
    std::unique_ptr<letki::Audio> audio;
    if (!o.silent)
      audio = std::make_unique<letki::Audio>(media, show.intro, show.gain);
    double silent_base = o.seek;
    double position = o.seek;
    uint64_t origin = letki::monotonic_ms() + 500;
    bool paused = false, quit = false;
    uint64_t next = 0, skipped = 0, late = 0, last_sync = letki::monotonic_ms(),
             start = letki::monotonic_ms(), last_draw = 0;
    double next_position = position;
    // Exactly one transport job owns Chain at a time. Video/audio presentation
    // stays on the main thread while acknowledgements or clock sync wait.
    std::future<unsigned> transport;
    uint64_t draws = 0, draw_gap = 0;
    auto finish_transport = [&]() {
      unsigned result = transport.valid() ? transport.get() : 0;
      late += result & 1U;
      return (result & 2U) != 0;
    };
    if (audio)
      audio->start(position);
    auto restart = [&](double p, bool hold) {
      finish_transport();
      chain->all(11);
      if (audio) {
        audio->stop();
        if (!hold)
          audio->start(p);
      }
      silent_base = p;
      position = p;
      origin = letki::monotonic_ms() + 500;
      next = 0;
      next_position = p;
      paused = hold;
    };
    while (!quit && !interrupted) {
      uint64_t now = letki::monotonic_ms();
      if (transport.valid() && transport.wait_for(std::chrono::milliseconds(0)) == std::future_status::ready) {
        if (finish_transport()) {
          next = 0;
          next_position = position;
        }
      }
      if (window) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
          if (e.type == SDL_QUIT)
            quit = true;
          if (e.type != SDL_KEYDOWN)
            continue;
          auto k = e.key.keysym.sym;
          if (k == SDLK_ESCAPE)
            quit = true;
          if (k == SDLK_SPACE)
            restart(position, !paused);
          if (k == SDLK_RIGHT)
            restart(std::min(total - .01, position + 5), paused);
          if (k == SDLK_LEFT)
            restart(std::max(0., position - 5), paused);
          if (k == SDLK_HOME)
            restart(0, paused);
          if (k == SDLK_v)
            video_enabled = !video_enabled;
          if (k == SDLK_n || k == SDLK_RIGHTBRACKET) {
            for (auto &cue : show.cues)
              if (!cue.effect.empty() && cue.at + show.intro > position + .5) {
                restart(std::max(0., cue.at + show.intro - 1), paused);
                break;
              }
          }
        }
      }
      if (!paused)
        position = audio
                       ? audio->position()
                       : std::clamp(silent_base + (double(now) - origin) / 1000,
                                    silent_base, total);
      if (!paused && audio && !audio->playing())
        position = total;
      if (position >= total - .002 ||
          (o.limit && double(now - start) / 1000 >= o.limit))
        break;
      if (!transport.valid() && now - last_sync >= 1000) {
        last_sync = now;
        transport = std::async(std::launch::async, [&]() -> unsigned {
          if (!chain->sync()) return 0;
          chain->all(11);
          return 2;
        });
      }
      if (!paused && !transport.valid()) {
        double epoch = audio ? audio->presentation_host_ms()
                             : double(origin) - silent_base * 1000;
        double horizon = std::min(.65, (chain->slots - 1.) / o.fps);
        unsigned uncertainty = 0;
        for (auto c : chain->clocks)
          uncertainty = std::max(uncertainty, c.uncertainty);
        double target = next_position + double(next) / o.fps;
        double host = epoch + target * 1000;
        if (host < double(letki::monotonic_ms() + 100 + uncertainty)) {
          uint64_t advance = uint64_t(std::ceil(
              (double(letki::monotonic_ms() + 150 + uncertainty) - host) *
              o.fps / 1000));
          next += advance;
          skipped += advance;
          target = next_position + double(next) / o.fps;
          host = epoch + target * 1000;
        }
        if (target < total &&
            host < double(letki::monotonic_ms()) + horizon * 1000) {
          auto f = draw_frame(std::max(0., target + show.offset / 1000));
          transport = std::async(std::launch::async, [&, f, host]() -> unsigned {
            chain->frame(f, uint64_t(std::llround(host)));
            bool overdue = letki::monotonic_ms() > host;
            chain->pixels(letki::monotonic_ms());
            return overdue ? 1 : 0;
          });
          next++;
        }
      }
      if (window && now - last_draw >= 16) {
        if (last_draw) draw_gap = std::max(draw_gap, now - last_draw);
        last_draw = now;
        ++draws;
        double pc_position = paused  ? position
                             : audio ? audio->position()
                                     : position;
        auto preview =
            draw_frame(std::max(0., pc_position + show.offset / 1000));
        const letki::VideoImage *movie =
            video && video_enabled
                ? &video->image(std::max(0., pc_position - show.intro))
                : nullptr;
        window->draw(preview,
                     show.name + " | " + letki::caption(show, pc_position) +
                         " | " + std::to_string(int(pc_position)) + "s / " +
                         std::to_string(int(total)) + "s" +
                         (paused ? " | PAUSED" : ""),
                     movie);
      }
      if (!transport.valid()) chain->pixels(letki::monotonic_ms());
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
    finish_transport();
    uint64_t warnings = audio ? audio->underruns() : 0;
    if (audio)
      audio->stop();
    report(o, show, chain->frames, skipped, late, warnings, chain->retries,
           chain->invalid, chain->retained,
           double(letki::monotonic_ms() - start) / 1000,
           interrupted ? "interrupted"
           : quit      ? "stopped"
                       : "completed", draws, draw_gap);
    std::cout << "Frames " << chain->frames << ", skipped " << skipped
              << ", late " << late << ", audio warnings " << warnings
              << ". Report: " << o.report << "\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "letki-player: " << e.what() << "\n";
    return 1;
  }
}
