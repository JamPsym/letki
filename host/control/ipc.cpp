#include "ipc.hpp"
#include <cerrno>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <glib.h>
#include <json-c/json.h>
#include <poll.h>
#include <stdexcept>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>
#include <vector>
namespace control::ipc {
namespace {
struct Fd {
  int n;
  ~Fd() {
    if (n >= 0)
      close(n);
  }
};
uint64_t now() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}
void wait_fd(int fd, short events, uint64_t until) {
  for (;;) {
    auto t = now();
    if (t >= until)
      throw std::runtime_error("Display service timed out");
    pollfd p{fd, events, 0};
    int r = poll(&p, 1, int(until - t));
    if (r < 0 && errno == EINTR)
      continue;
    if (r <= 0)
      throw std::runtime_error("Display service timed out");
    if (p.revents & (events | POLLHUP))
      return;
    throw std::runtime_error("Display service connection failed");
  }
}
} // namespace
std::string default_socket() {
  const char *runtime = g_getenv("XDG_RUNTIME_DIR");
  if (runtime && *runtime)
    return std::string(runtime) + "/letki/display.sock";
  return "/tmp/letki-" + std::to_string(getuid()) + "/display.sock";
}
std::string call(const std::string &request, const std::string &selected,
                 int timeout) {
  if (timeout < 1 || timeout > 60000)
    throw std::runtime_error("Invalid IPC timeout");
  std::string path = selected.empty() ? default_socket() : selected;
  sockaddr_un address{};
  address.sun_family = AF_UNIX;
  if (path.size() >= sizeof(address.sun_path))
    throw std::runtime_error("Socket path is too long");
  std::memcpy(address.sun_path, path.c_str(), path.size() + 1);
  Fd fd{socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0)};
  if (fd.n < 0)
    throw std::runtime_error(std::strerror(errno));
  uint64_t until = now() + unsigned(timeout);
  if (connect(fd.n, reinterpret_cast<sockaddr *>(&address), sizeof(address)) <
      0) {
    if (errno != EINPROGRESS)
      throw std::runtime_error("Display service is not running: " + path);
    wait_fd(fd.n, POLLOUT, until);
    int error = 0;
    socklen_t size = sizeof(error);
    if (getsockopt(fd.n, SOL_SOCKET, SO_ERROR, &error, &size) || error)
      throw std::runtime_error("Could not connect to display service");
  }
  if (request.size() > 65535 || request.find('\n') != std::string::npos)
    throw std::runtime_error("Expected one JSON request, at most 65535 bytes");
  std::string wire = request + '\n';
  for (size_t at = 0; at < wire.size();) {
    ssize_t n = send(fd.n, wire.data() + at, wire.size() - at, MSG_NOSIGNAL);
    if (n > 0)
      at += size_t(n);
    else if (n < 0 && (errno == EAGAIN || errno == EINTR))
      wait_fd(fd.n, POLLOUT, until);
    else
      throw std::runtime_error("Display service disconnected while sending");
  }
  std::string result;
  char buffer[4096];
  for (;;) {
    wait_fd(fd.n, POLLIN, until);
    ssize_t n = recv(fd.n, buffer, sizeof(buffer), 0);
    if (n < 0 && (errno == EAGAIN || errno == EINTR))
      continue;
    if (n <= 0)
      throw std::runtime_error("Display service disconnected before replying");
    result.append(buffer, size_t(n));
    if (result.size() > 131072)
      throw std::runtime_error("Display service reply exceeds limit");
    auto end = result.find('\n');
    if (end != std::string::npos)
      return result.substr(0, end);
  }
}
bool ensure_service(const std::string &selected, bool simulate,
                    bool autoconnect, const std::string &port) {
  const auto path = selected.empty() ? default_socket() : selected;
  auto verify = [](const std::string &wire) {
    auto *j = json_tokener_parse(wire.c_str());
    json_object *version = nullptr, *success = nullptr;
    bool valid = j && json_object_object_get_ex(j, "v", &version) &&
                 json_object_object_get_ex(j, "ok", &success) &&
                 json_object_is_type(version, json_type_int) &&
                 json_object_get_int(version) == 1 &&
                 json_object_is_type(success, json_type_boolean) &&
                 json_object_get_boolean(success);
    if (j)
      json_object_put(j);
    if (!valid)
      throw std::runtime_error(
          "The socket does not speak Letki display API v1");
  };
  std::string existing;
  try {
    existing = call("{\"v\":1,\"op\":\"status\"}", path, 400);
  } catch (...) {
  }
  if (!existing.empty()) {
    verify(existing);
    return false;
  }
  char executable[4096];
  ssize_t length =
      readlink("/proc/self/exe", executable, sizeof(executable) - 1);
  if (length < 0)
    throw std::runtime_error("Cannot locate display service binary");
  executable[length] = 0;
  auto daemon =
      (std::filesystem::path(executable).parent_path() / "letkid").string();
  std::vector<std::string> arguments{daemon, "--socket", path};
  if (simulate)
    arguments.push_back("--simulate");
  if (!autoconnect)
    arguments.push_back("--no-connect");
  if (!port.empty()) {
    arguments.push_back("--port");
    arguments.push_back(port);
  }
  std::vector<char *> argv;
  for (auto &a : arguments)
    argv.push_back(a.data());
  argv.push_back(nullptr);
  GError *error = nullptr;
  // GLib's default double-fork detaches the broker from the UI process.
  if (!g_spawn_async(
          nullptr, argv.data(), nullptr,
          GSpawnFlags(G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL),
          nullptr, nullptr, nullptr, &error)) {
    std::string message = error ? error->message : "Could not start service";
    g_clear_error(&error);
    throw std::runtime_error(message);
  }
  for (unsigned i = 0; i < 100; i++) {
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
    try {
      verify(call("{\"v\":1,\"op\":\"status\"}", path, 100));
      return true;
    } catch (...) {
    }
  }
  throw std::runtime_error(
      "Service did not start; run letkid in a terminal for diagnostics");
}
} // namespace control::ipc
