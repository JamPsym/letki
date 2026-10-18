#pragma once
#include <cstdint>
#include <string>
#include <sys/types.h>
#include <vector>
namespace control {
struct SongDemo {
  std::string id, title, description, show;
};
const std::vector<SongDemo> &song_demos();
struct SongLaunch {
  std::string id, port, wayland, display;
  bool simulate = false, silent = false, headless = false;
  unsigned duration_ms = 0;
};
// Owns only the companion player. No UART calls, shell, or media decoding here.
class MusicDemo {
  pid_t pid = -1;
  uint64_t stop_at = 0;
  int result = 0;

public:
  ~MusicDemo();
  static std::string unavailable(const SongDemo &);
  void start(const SongLaunch &);
  void stop();
  bool running();
  int exit_code() const { return result; }
};
} // namespace control
