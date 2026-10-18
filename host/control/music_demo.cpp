#include "music_demo.hpp"
#include "player.hpp"
#include <cerrno>
#include <chrono>
#include <csignal>
#include <fcntl.h>
#include <filesystem>
#include <json-c/json.h>
#include <spawn.h>
#include <stdexcept>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>
#include <vector>
extern char **environ;
namespace control {
const std::vector<SongDemo> &song_demos() {
  static const std::vector<SongDemo> list{
      {"tubular-bells", "Tubular Bells",
       "Mike Oldfield · BBC 1973 · 25:48 · Instrument theatre",
       "config/player/tubular-bells-full.json"},
      {"my-cyganie", "My Cyganie", "Don Vasyl · Ore ore · 4:38 · Stepping together",
       "config/player/my-cyganie-full.json"},
      {"adagio", "Adagio for Strings", "Tiësto · 3:26 · Suspended light",
       "config/player/adagio-full.json"},
      {"lamour-toujours", "L'Amour Toujours", "Gigi D'Agostino · 4:02 · Together in light",
       "config/player/lamour-toujours-full.json"},
      {"laskowski-2pac", "Laskowski x 2Pac", "Świat nie wierzy łzom / Baby Don’t Cry · 5:06 · Wielkie pojednanie",
       "config/player/laskowski-2pac-full.json"}};
  return list;
}
std::string MusicDemo::unavailable(const SongDemo &song) {
  if (!std::filesystem::exists("build/player/letki-player"))
    return "Music player is missing; run make player.";
  auto *j = json_object_from_file(song.show.c_str());
  if (!j)
    return "Show configuration is missing or invalid.";
  std::string reason;
  for (auto key : {"audio", "video"}) {
    json_object *v = nullptr;
    if (!json_object_object_get_ex(j, key, &v) ||
        !json_object_is_type(v, json_type_string) ||
        !std::filesystem::is_regular_file(
            std::filesystem::path(song.show).parent_path() /
            json_object_get_string(v)))
      reason = "The local audio/video recording is missing.";
  }
  json_object_put(j);
  return reason;
}
void MusicDemo::start(const SongLaunch &launch) {
  if (running())
    throw std::runtime_error("A music demo is already running");
  const SongDemo *song = nullptr;
  for (auto &s : song_demos())
    if (s.id == launch.id)
      song = &s;
  if (!song)
    throw std::runtime_error("Unknown music demo");
  auto missing = unavailable(*song);
  if (!missing.empty())
    throw std::runtime_error(missing);
  if (!launch.simulate && launch.port.empty())
    throw std::runtime_error("Music playback needs the connected UART port");
  std::vector<std::string> args{
      std::filesystem::absolute("build/player/letki-player").string(), "--show",
      song->show, "--report", "build/control/music-demo-result.json"};
  if (launch.simulate)
    args.push_back("--simulate");
  else {
    args.push_back("--port");
    args.push_back(launch.port);
  }
  if (launch.silent)
    args.push_back("--silent");
  if (launch.headless)
    args.push_back("--headless");
  if (launch.duration_ms) {
    args.push_back("--seconds");
    args.push_back(std::to_string(launch.duration_ms / 1000.));
  }
  std::vector<char *> argv;
  for (auto &s : args)
    argv.push_back(s.data());
  argv.push_back(nullptr);
  std::vector<std::string> env;
  for (char **p = environ; *p; p++) {
    std::string value = *p;
    if ((!launch.wayland.empty() && value.rfind("WAYLAND_DISPLAY=", 0) == 0) ||
        (!launch.display.empty() && value.rfind("DISPLAY=", 0) == 0))
      continue;
    env.push_back(value);
  }
  if (!launch.wayland.empty())
    env.push_back("WAYLAND_DISPLAY=" + launch.wayland);
  if (!launch.display.empty())
    env.push_back("DISPLAY=" + launch.display);
  std::vector<char *> envp;
  for (auto &s : env)
    envp.push_back(s.data());
  envp.push_back(nullptr);
  posix_spawn_file_actions_t files;
  posix_spawn_file_actions_init(&files);
  posix_spawn_file_actions_addopen(&files, STDIN_FILENO, "/dev/null", O_RDONLY,
                                   0);
  posix_spawn_file_actions_addopen(&files, STDOUT_FILENO,
                                   "build/control/music-demo.log",
                                   O_WRONLY | O_CREAT | O_TRUNC, 0600);
  posix_spawn_file_actions_adddup2(&files, STDOUT_FILENO, STDERR_FILENO);
  int error =
      posix_spawn(&pid, argv[0], &files, nullptr, argv.data(), envp.data());
  posix_spawn_file_actions_destroy(&files);
  if (error) {
    pid = -1;
    throw std::runtime_error("Could not launch the companion music player");
  }
  result = 0;
  stop_at = 0;
}
bool MusicDemo::running() {
  if (pid < 0)
    return false;
  int status = 0;
  pid_t r = waitpid(pid, &status, WNOHANG);
  if (r == pid) {
    result = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    pid = -1;
    return false;
  }
  if (r < 0 && errno != EINTR) {
    pid = -1;
    result = 1;
    return false;
  }
  if (stop_at && letki::monotonic_ms() - stop_at > 6000)
    kill(pid, SIGKILL);
  return true;
}
void MusicDemo::stop() {
  if (pid > 0 && !stop_at) {
    stop_at = letki::monotonic_ms();
    kill(pid, SIGINT);
  }
}
MusicDemo::~MusicDemo() {
  stop();
  while (running())
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
}
} // namespace control
