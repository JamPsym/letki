#include "controller.hpp"
#include <algorithm>
#include <cctype>
#include <chrono>
#include <stdexcept>
namespace letki {
uint64_t monotonic_ms() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}
} // namespace letki
namespace control {
static uint16_t checksum(const letki::Bytes &b) {
  uint16_t c = 65535;
  for (auto x : b) {
    c ^= uint16_t(x) << 8;
    for (unsigned i = 0; i < 8; i++)
      c = uint16_t((c << 1) ^ ((c & 32768) ? 0x1021 : 0));
  }
  return c;
}
void play(letki::Chain &c, bool restart) {
  c.inspect();
  c.sync();
  for (auto clock : c.clocks)
    if (clock.age > 500)
      throw std::runtime_error("Text is loaded but the shared clock is stale. "
                               "Check SDA/SCL, then press Resume.");
  uint32_t position = restart ? 0 : letki::get32(c.info[0].raw, 16);
  std::vector<letki::Bytes> payload(5);
  auto when = letki::monotonic_ms() + 300;
  for (unsigned n = 0; n < 5; n++) {
    if (!c.info[n].length)
      throw std::runtime_error(
          "No program is loaded on every tile. Apply a message first.");
    letki::Bytes read;
    letki::put16(read, 0);
    read.push_back(8);
    auto header = c.request(n, 17, read);
    if (header.size() != 8)
      throw std::runtime_error("Invalid program header");
    letki::put32(payload[n], uint32_t(when + c.clocks[n].offset));
    letki::put32(payload[n], position);
    payload[n].push_back(header[7] & 1);
  }
  c.all(11);
  c.all(12, {100});
  c.batch(8, payload);
}
void upload_ram(letki::Chain &c, const TextProgram &program) {
  const auto &p = program.bytes;
  if (p.empty())
    throw std::runtime_error("Enter a valid message first.");
  c.inspect();
  for (auto &i : c.info)
    if (p.size() > i.arena)
      throw std::runtime_error("Message exceeds board RAM. Shorten the text; "
                               "flash is never used by this app.");
  c.all(9);
  c.all(11);
  c.all(16, {0, 2});
  std::vector<unsigned> started;
  try {
    for (unsigned n = 0; n < 5; n++) {
      unsigned used = c.info[n].storage == 0 ? c.info[n].length : 0;
      letki::Bytes b{0, uint8_t(used + p.size() > c.info[n].arena ? 1 : 0)};
      letki::put16(b, p.size());
      letki::put16(b, checksum(p));
      c.request(n, 4, b);
      started.push_back(n);
    }
    for (unsigned n = 0; n < 5; n++)
      for (size_t at = 0; at < p.size(); at += 46) {
        letki::Bytes b;
        letki::put16(b, at);
        b.insert(b.end(), p.begin() + at,
                 p.begin() + std::min(at + 46, p.size()));
        c.request(n, 5, b);
      }
    for (unsigned n = 0; n < 5; n++)
      c.request(n, 6);
    for (unsigned n = 0; n < 5; n++)
      for (size_t at = 0; at < p.size(); at += 47) {
        letki::Bytes b;
        letki::put16(b, at);
        b.push_back(std::min(size_t(47), p.size() - at));
        auto r = c.request(n, 17, b);
        if (r.size() != b[2] ||
            r != letki::Bytes(p.begin() + at, p.begin() + at + b[2]))
          throw std::runtime_error("Text readback failed. Retry Apply.");
      }
    unsigned slots = 2;
    for (auto &i : c.info)
      if (p.size() + 160 > i.arena)
        slots = 0;
    c.all(16, {uint8_t(slots), 2});
    play(c, true);
  } catch (...) {
    for (auto n : started)
      try {
        c.request(n, 7);
      } catch (...) {
      }
    throw;
  }
}
void begin_stream(letki::Chain &c, unsigned format) {
  if (format != 1 && format != 2)
    throw std::runtime_error("Streaming format must be GRAY4(1) or LEVEL8(2).");
  const unsigned required = format == 2 ? 160 : 96;
  c.resume_on_close = false;
  c.inspect();
  for (const auto &i : c.info) {
    if (i.raw.size() <= 33 || i.raw[23] || i.raw[33])
      throw std::runtime_error(
          "Finish active upload before starting a stream.");
    const unsigned used = i.storage == 0 ? i.length : 0;
    if (used > i.arena || i.arena - used < required)
      throw std::runtime_error("Streaming needs " + std::to_string(required) +
                               " spare RAM bytes on every tile. "
                               "Apply a shorter message first.");
  }
  c.sync();
  for (const auto &clock : c.clocks)
    if (clock.age > 500)
      throw std::runtime_error("Cannot stream: the shared I2C clock is stale.");
  c.format = format;
  try {
    c.prepare();
    // LEVEL8 crosses five tiles in three acknowledged batches. The qualified
    // fast rate is essential for animation; 115200 is for idle/manual control.
    c.set_baud(230400);
  } catch (...) {
    c.resume_on_close = false;
    throw;
  }
  c.resume_on_close = false;
}
void end_stream(letki::Chain &c) {
  c.resume_on_close = false;
  c.all(11);
  if (c.baud != 115200)
    c.set_baud(115200);
}
Controller::Controller() {
  worker = std::thread([this] { run(); });
}
Controller::~Controller() {
  quit = true;
  ready.notify_all();
  if (worker.joinable())
    worker.join();
}
State Controller::snapshot() const {
  std::lock_guard<std::mutex> l(mutex);
  return state;
}
bool Controller::submit(Action a, const TextProgram &p, const std::string &port,
                        bool simulate, unsigned format) {
  if (format != 1 && format != 2)
    throw std::runtime_error("Invalid streaming format");
  std::lock_guard<std::mutex> l(mutex);
  if (state.busy || quit || a == Action::StreamFrame)
    return false;
  state.busy = true;
  state.error.clear();
  state.revision++;
  state.message = a == Action::Connect ? "Connecting…" : "Working…";
  Job job{a, p, port, simulate};
  job.format = format;
  jobs.push_back(std::move(job));
  ready.notify_one();
  return true;
}
bool Controller::submitFrame(const letki::Frame &frame, uint64_t deadline) {
  for (const auto &tile : frame)
    for (auto value : tile)
      if (value > 100)
        throw std::runtime_error("Pixel values must be in 0–100%.");
  const auto now = letki::monotonic_ms();
  if (deadline && (deadline < now + 40 || deadline > now + 1000))
    throw std::runtime_error(
        "Frame deadline must be 40–1000 ms in the future.");
  std::lock_guard<std::mutex> l(mutex);
  if (state.busy || quit || !state.streaming)
    return false;
  state.busy = true;
  state.error.clear();
  state.revision++;
  Job job{Action::StreamFrame, {}, {}, false};
  job.frame = frame;
  job.deadline = deadline;
  jobs.push_back(std::move(job));
  ready.notify_one();
  return true;
}
void Controller::update(const std::string &message) {
  std::lock_guard<std::mutex> l(mutex);
  state.connected = bool(chain);
  state.streaming = stream_active;
  state.baud = chain ? chain->baud : 0;
  if (chain) {
    state.nodes = chain->info;
    state.retries = chain->retries;
    state.invalid = chain->invalid;
    if (chain->simulated())
      state.pixels = chain->pixels(letki::monotonic_ms());
  } else
    state.pixels = {};
  state.message = message;
  state.busy = false;
  state.revision++;
}
void Controller::finish_stream(bool drain) {
  // FRAME acknowledgements mean queued, not presented. A normal end drains the
  // newest accepted deadline before FLUSH so one-frame clients keep their
  // frame.
  if (drain && last_frame_deadline) {
    const auto until =
        std::min(last_frame_deadline + 20, letki::monotonic_ms() + 1020);
    while (!quit && letki::monotonic_ms() < until)
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  end_stream(*chain);
  last_frame_deadline = 0;
  stream_active = false;
}
void Controller::execute(const Job &j) {
  if (j.action == Action::Disconnect) {
    if (chain && stream_active)
      finish_stream();
    stream_active = false;
    chain.reset();
    update("Disconnected. The display keeps its current state.");
    return;
  }
  if (j.action == Action::Connect) {
    if (chain && stream_active)
      finish_stream();
    stream_active = false;
    chain.reset();
    std::string port = j.port;
    auto whitespace = [](unsigned char c) { return std::isspace(c); };
    port.erase(port.begin(),
               std::find_if_not(port.begin(), port.end(), whitespace));
    port.erase(std::find_if_not(port.rbegin(), port.rend(), whitespace).base(),
               port.end());
    if (j.simulate)
      chain = std::make_unique<letki::Chain>(letki::simulation());
    else {
      if (port.empty())
        port = letki::discover_serial();
      if (port.empty())
        throw std::runtime_error(
            "No WCH-Link found. Connect the adapter and try Connect again.");
      try {
        chain = std::make_unique<letki::Chain>(letki::serial(port));
      } catch (const letki::ReplyTimeout &) {
        {
          std::lock_guard<std::mutex> l(mutex);
          state.message = "Waiting for the previous session’s baud lease…";
          state.revision++;
        }
        auto until = letki::monotonic_ms() + 10500;
        while (!quit && letki::monotonic_ms() < until)
          std::this_thread::sleep_for(std::chrono::milliseconds(50));
        if (quit)
          return;
        chain = std::make_unique<letki::Chain>(letki::serial(port));
      }
    }
    chain->inspect();
    {
      std::lock_guard<std::mutex> l(mutex);
      state.simulated = j.simulate;
      state.port = port;
    }
    update(j.simulate
               ? "Simulation connected. Apply changes only the virtual boards."
               : "Five boards connected. Your draft has not been sent.");
    return;
  }
  if (!chain)
    throw std::runtime_error("Connect to the boards first.");
  if (stream_active && j.action != Action::StreamFrame &&
      j.action != Action::StreamBegin) {
    finish_stream(j.action != Action::Blank);
  }
  switch (j.action) {
  case Action::StreamBegin:
    if (!stream_active) {
      begin_stream(*chain, j.format);
      stream_active = true;
      last_stream_sync = letki::monotonic_ms();
      frame_times.clear();
      std::lock_guard<std::mutex> l(mutex);
      state.frame_transfer_ms = state.stream_late = state.stream_dropped = 0;
      state.stream_fps = 0;
    }
    break;
  case Action::StreamFrame: {
    if (!stream_active)
      throw std::runtime_error("Start a stream before sending frames.");
    auto now = letki::monotonic_ms();
    if (now - last_stream_sync >= 5000) {
      chain->sync();
      last_stream_sync = letki::monotonic_ms();
      now = last_stream_sync;
    }
    if (j.deadline && j.deadline <= now) {
      // The UART can remain healthy even if earlier work consumed the lead
      // time. Drop only this frame; retain the stream and any queued frames.
      {
        std::lock_guard<std::mutex> l(mutex);
        state.error = "Frame deadline has already passed.";
        state.stream_dropped++;
      }
      update("Frame dropped: its deadline passed. The stream remains active.");
      return;
    }
    const auto deadline = j.deadline ? j.deadline : now + 120;
    const auto before = letki::monotonic_ms();
    chain->frame(j.frame, deadline);
    const auto after = letki::monotonic_ms();
    frame_times.push_back(after);
    while (frame_times.size() > 2 && frame_times.front() + 2000 < after)
      frame_times.pop_front();
    last_frame_deadline = std::max(last_frame_deadline, deadline);
    {
      std::lock_guard<std::mutex> l(mutex);
      state.streamed++;
      state.frame_transfer_ms = after - before;
      state.stream_late += after > deadline;
      if (frame_times.size() > 1 && after > frame_times.front())
        state.stream_fps = (frame_times.size() - 1) * 1000. /
                           (after - frame_times.front());
    }
    update("Streaming frame accepted.");
    return;
  }
  case Action::StreamEnd:
    break; // Already flushed above; holds the current raw frame.
  case Action::Apply:
    upload_ram(*chain, j.program);
    {
      std::lock_guard<std::mutex> l(mutex);
      state.applied++;
      state.applied_program = j.program.bytes;
    }
    break;
  case Action::Pause:
    chain->all(9);
    break;
  case Action::Resume:
    control::play(*chain, false);
    break;
  case Action::Restart:
    control::play(*chain, true);
    break;
  case Action::Blank:
    chain->all(12, {0});
    break;
  default:
    break;
  }
  chain->inspect();
  update(
      j.action == Action::StreamBegin
          ? (j.format == 2
                 ? "Streaming started. Frames retain all 101 brightness levels."
                 : "Streaming started. Frames use 16 brightness levels.")
      : j.action == Action::StreamEnd
          ? "Stream ended. The last frame stays displayed."
      : j.action == Action::Apply ? "Applied and read back on all five tiles. "
                                    "Text runs independently in RAM."
      : j.action == Action::Pause ? "Board playback paused."
      : j.action == Action::Blank
          ? "Display blanked. Resume restores brightness."
          : "Board playback running.");
}
void Controller::run() {
  while (!quit) {
    Job job;
    bool have = false;
    {
      std::unique_lock<std::mutex> l(mutex);
      ready.wait_for(l, std::chrono::seconds(1),
                     [this] { return quit || !jobs.empty(); });
      if (quit)
        break;
      if (!jobs.empty()) {
        job = std::move(jobs.front());
        jobs.pop_front();
        have = true;
      }
    }
    try {
      if (have)
        execute(job);
      else if (chain) {
        if (stream_active)
          chain->sync();
        chain->inspect();
        std::lock_guard<std::mutex> l(mutex);
        state.nodes = chain->info;
        if (chain->simulated())
          state.pixels = chain->pixels(letki::monotonic_ms());
        state.revision++;
      }
    } catch (const std::exception &e) {
      if (chain && stream_active)
        try {
          finish_stream(false);
        } catch (...) {
        }
      {
        std::lock_guard<std::mutex> l(mutex);
        state.error = e.what();
      }
      stream_active = false;
      chain.reset();
      update(std::string(e.what()) +
             "  Draft kept; reconnect and retry if Apply was interrupted.");
    }
  }
  if (chain && stream_active)
    try {
      finish_stream(false);
    } catch (...) {
    }
  chain.reset();
}
} // namespace control
