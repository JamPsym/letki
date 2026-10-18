#pragma once
#include "text_program.hpp"
#include <atomic>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>
namespace control {
enum class Action {
  Connect,
  Disconnect,
  Apply,
  Pause,
  Resume,
  Restart,
  Blank,
  StreamBegin,
  StreamFrame,
  StreamEnd
};
struct State {
  bool connected = false, simulated = false, busy = false, streaming = false;
  uint64_t revision = 0, applied = 0, streamed = 0;
  unsigned baud = 0;
  uint64_t retries = 0, invalid = 0, frame_transfer_ms = 0,
           stream_late = 0, stream_dropped = 0;
  double stream_fps = 0;
  std::string message = "Draft preview is ready.", port, error;
  std::array<letki::Info, 5> nodes{};
  letki::Bytes applied_program;
  letki::Frame pixels{}; // Exact simulator output; never hardware readback.
};
class Controller {
  struct Job {
    Action action;
    TextProgram program;
    std::string port;
    bool simulate;
    letki::Frame frame{};
    uint64_t deadline = 0;
    unsigned format = 1;
  };
  mutable std::mutex mutex;
  std::condition_variable ready;
  std::deque<Job> jobs;
  State state;
  std::atomic<bool> quit{false};
  std::unique_ptr<letki::Chain> chain;
  uint64_t last_frame_deadline = 0;
  uint64_t last_stream_sync = 0;
  std::deque<uint64_t> frame_times;
  bool stream_active = false; // Worker-owned; snapshots expose State.streaming.
  std::thread worker; // Constructed after all state that the thread accesses.
  void finish_stream(bool drain = true);
  void run();
  void execute(const Job &);
  void update(const std::string &);

public:
  Controller();
  ~Controller();
  State snapshot() const;
  bool submit(Action, const TextProgram &program = {},
              const std::string &port = {}, bool simulate = false,
              unsigned format = 1);
  bool submitFrame(const letki::Frame &, uint64_t host_deadline = 0);
};
// RAM only; validates capacity before mutation, reads back before playing.
void upload_ram(letki::Chain &, const TextProgram &);
void play(letki::Chain &, bool restart);
// Streaming preserves the loaded program. Formats: GRAY4=1, LEVEL8=2.
// Ending a stream holds the last displayed frame; no implicit show restoration.
void begin_stream(letki::Chain &, unsigned format = 1);
void end_stream(letki::Chain &);
} // namespace control
