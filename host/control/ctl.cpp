#include "ipc.hpp"
#include <cerrno>
#include <chrono>
#include <csignal>
#include <fstream>
#include <iostream>
#include <json-c/json.h>
#include <memory>
#include <poll.h>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>

namespace {
using Json = std::unique_ptr<json_object, decltype(&json_object_put)>;
Json own(json_object *p) {
  if (!p)
    throw std::runtime_error("Cannot allocate JSON value");
  return Json(p, json_object_put);
}
Json parse(const std::string &s) {
  std::unique_ptr<json_tokener, decltype(&json_tokener_free)> tok(
      json_tokener_new(), json_tokener_free);
  if (!tok)
    throw std::runtime_error("Cannot allocate JSON parser");
  json_tokener_set_flags(tok.get(),
                         JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
  auto result =
      Json(json_tokener_parse_ex(tok.get(), s.c_str(), int(s.size() + 1)),
           json_object_put);
  if (!result || json_tokener_get_error(tok.get()) != json_tokener_success)
    throw std::runtime_error("Invalid JSON input");
  return result;
}
json_object *field(json_object *p, const char *key) {
  json_object *value = nullptr;
  return json_object_object_get_ex(p, key, &value) ? value : nullptr;
}
std::string string(json_object *p, const char *key) {
  auto *v = field(p, key);
  return v && json_object_is_type(v, json_type_string)
             ? json_object_get_string(v)
             : "";
}
bool boolean(json_object *p, const char *key) {
  auto *v = field(p, key);
  return v && json_object_get_boolean(v);
}
void set(json_object *p, const char *key, const std::string &v) {
  json_object_object_add(p, key,
                         json_object_new_string_len(v.data(), int(v.size())));
}
void set(json_object *p, const char *key, int64_t v) {
  json_object_object_add(p, key, json_object_new_int64(v));
}
void set(json_object *p, const char *key, bool v) {
  json_object_object_add(p, key, json_object_new_boolean(v));
}
Json request(const std::string &op) {
  auto p = own(json_object_new_object());
  set(p.get(), "v", int64_t(1));
  set(p.get(), "op", op);
  return p;
}
std::string encode(json_object *p) {
  return json_object_to_json_string_ext(p, JSON_C_TO_STRING_PLAIN);
}
Json invoke(json_object *p, const std::string &socket) {
  auto result = parse(control::ipc::call(encode(p), socket, 5000));
  if (!json_object_is_type(result.get(), json_type_object) ||
      !field(result.get(), "ok"))
    throw std::runtime_error("Service returned an invalid response");
  return result;
}
void require_ok(json_object *p) {
  if (!boolean(p, "ok")) {
    auto e = string(p, "error");
    throw std::runtime_error(e.empty() ? "Service rejected command" : e);
  }
}
int64_t number(const std::string &s, const std::string &name) {
  size_t used = 0;
  long long n;
  try {
    n = std::stoll(s, &used);
  } catch (...) {
    throw std::runtime_error(name + " requires an integer");
  }
  if (used != s.size())
    throw std::runtime_error(name + " requires an integer");
  return n;
}
void pixels(json_object *p) {
  if (!json_object_is_type(p, json_type_array) ||
      json_object_array_length(p) != 320)
    throw std::runtime_error(
        "Pixels must be a JSON array of 320 integers (40 by 8, row-major)");
  for (size_t i = 0; i < 320; ++i) {
    auto *v = json_object_array_get_idx(p, i);
    if (!json_object_is_type(v, json_type_int) ||
        json_object_get_int64(v) < 0 || json_object_get_int64(v) > 100)
      throw std::runtime_error("Each pixel must be an integer from 0 to 100");
  }
}
volatile std::sig_atomic_t interrupted = 0;
extern "C" void stop(int) { interrupted = 1; }
void wait_idle(const std::string &socket, int timeout_ms = 15000) {
  const auto until =
      std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
  while (std::chrono::steady_clock::now() < until) {
    auto p = request("status");
    auto r = invoke(p.get(), socket);
    require_ok(r.get());
    if (!boolean(r.get(), "busy")) {
      auto e = string(r.get(), "last_error");
      if (!e.empty())
        throw std::runtime_error(e);
      return;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(15));
  }
  throw std::runtime_error("Timed out waiting for display operation");
}
Json stream_call(json_object *p, const std::string &socket) {
  const auto until =
      std::chrono::steady_clock::now() + std::chrono::seconds(15);
  while (true) {
    auto r = invoke(p, socket);
    if (boolean(r.get(), "ok"))
      return r;
    auto e = string(r.get(), "error");
    if (e.find("busy") == std::string::npos &&
        e.find("Busy") == std::string::npos)
      require_ok(r.get());
    if (std::chrono::steady_clock::now() >= until)
      require_ok(r.get());
    std::this_thread::sleep_for(std::chrono::milliseconds(15));
  }
}
// Polling keeps Ctrl+C responsive even when an input producer stops writing.
class Lines {
  std::string pending;
  bool ended = false;

public:
  bool next(std::string &line) {
    while (!interrupted) {
      auto nl = pending.find('\n');
      if (nl != std::string::npos || ended) {
        if (pending.empty() && ended)
          return false;
        line = pending.substr(0, nl);
        if (nl == std::string::npos)
          pending.clear();
        else
          pending.erase(0, nl + 1);
        return true;
      }
      pollfd p{STDIN_FILENO, POLLIN, 0};
      int ready = poll(&p, 1, 100);
      if (ready < 0) {
        if (errno == EINTR)
          continue;
        throw std::runtime_error("Failed to poll stream input");
      }
      if (!ready)
        continue;
      char data[4096];
      auto n = read(STDIN_FILENO, data, sizeof(data));
      if (n < 0) {
        if (errno == EINTR)
          continue;
        throw std::runtime_error("Failed to read stream input");
      }
      if (!n)
        ended = true;
      else
        pending.append(data, size_t(n));
      if (pending.size() > 16384 && pending.find('\n') == std::string::npos)
        throw std::runtime_error("Stream frame line is too large");
    }
    return false;
  }
};
int stream(const std::string &owner, const std::string &socket) {
  auto begin = request("stream_begin");
  set(begin.get(), "owner", owner);
  set(begin.get(), "ttl_ms", int64_t(3000));
  auto r = stream_call(begin.get(), socket);
  const auto lease = string(r.get(), "lease");
  if (lease.empty())
    throw std::runtime_error("Service did not return a stream lease");
  std::signal(SIGINT, stop);
  std::signal(SIGTERM, stop);
  std::exception_ptr failure;
  uint64_t count = 0;
  try {
    wait_idle(socket);
    std::string line;
    Lines input;
    while (input.next(line)) {
      if (line.empty())
        continue;
      if (line.size() > 16384)
        throw std::runtime_error("Stream frame line is too large");
      auto values = parse(line);
      pixels(values.get());
      auto p = request("stream_frame");
      set(p.get(), "lease", lease);
      json_object_object_add(p.get(), "pixels", json_object_get(values.get()));
      auto accepted = stream_call(p.get(), socket);
      require_ok(accepted.get());
      wait_idle(socket);
      ++count;
    }
  } catch (...) {
    failure = std::current_exception();
  }
  auto end = request("stream_end");
  set(end.get(), "lease", lease);
  try {
    r = stream_call(end.get(), socket);
    require_ok(r.get());
    wait_idle(socket);
  } catch (...) {
    if (!failure)
      failure = std::current_exception();
  }
  if (failure)
    std::rethrow_exception(failure);
  set(r.get(), "frames", int64_t(count));
  std::cout << encode(r.get()) << '\n';
  return interrupted ? 130 : 0;
}
void help() {
  std::cout
      << "letkictl [--socket PATH] [--start] COMMAND\n"
         "  status | connect [--simulate | --port PATH] | disconnect\n"
         "  text TEXT [OPTIONS] | preview TEXT [OPTIONS]\n"
         "  pause | resume | restart | blank\n"
         "  pixels FILE       JSON array of 320 levels, 40x8 row-major, "
         "0..100\n"
         "  stream OWNER      one JSON pixel array per stdin line; Ctrl+C/EOF "
         "ends\n"
         "  rpc JSON          send a complete versioned API request\n"
         "Text options:\n"
         "  --font compact|large|bold --motion scroll|bounce|fall|still\n"
         "  --speed MS --brightness 0..100 --minimum 0..100 --pulses N\n"
         "  --modulation steady|breathe|blink --once --position MS (preview)\n"
         "Commands contact an existing service. --start may launch letkid.\n";
}
} // namespace
int main(int argc, char **argv) {
  try {
    std::string socket;
    bool start = false;
    std::vector<std::string> args;
    int i = 1;
    for (; i < argc; ++i) {
      std::string a = argv[i];
      if (a == "--socket") {
        if (++i == argc)
          throw std::runtime_error("--socket requires a path");
        socket = argv[i];
      } else if (a == "--start")
        start = true;
      else
        break;
    }
    for (; i < argc; ++i)
      args.emplace_back(argv[i]);
    if (args.empty() || args[0] == "--help" || args[0] == "help") {
      help();
      return args.empty() ? 1 : 0;
    }
    const auto command = args[0];
    auto p = request(command);
    bool simulate = false;
    std::string port;
    if (command == "text" || command == "preview") {
      if (args.size() < 2)
        throw std::runtime_error(command + " requires a quoted text argument");
      auto draft = own(json_object_new_object());
      set(draft.get(), "text", args[1]);
      set(draft.get(), "font", std::string("compact"));
      set(draft.get(), "motion", std::string("scroll"));
      set(draft.get(), "speed", int64_t(75));
      set(draft.get(), "brightness", int64_t(75));
      set(draft.get(), "minimum", int64_t(5));
      set(draft.get(), "pulses", int64_t(2));
      set(draft.get(), "modulation", std::string("steady"));
      set(draft.get(), "loop", true);
      for (size_t i = 2; i < args.size(); ++i) {
        const auto &a = args[i];
        if (a == "--once") {
          set(draft.get(), "loop", false);
          continue;
        }
        if (i + 1 == args.size())
          throw std::runtime_error(a + " requires a value");
        const auto value = args[++i];
        if (a == "--font" || a == "--motion" || a == "--modulation")
          set(draft.get(), a.substr(2).c_str(), value);
        else if (a == "--speed" || a == "--brightness" || a == "--minimum" ||
                 a == "--pulses")
          set(draft.get(), a.substr(2).c_str(), number(value, a));
        else if (a == "--position" && command == "preview")
          set(p.get(), "position_ms", number(value, a));
        else
          throw std::runtime_error("Unknown option: " + a);
      }
      json_object_object_add(p.get(), "draft", json_object_get(draft.get()));
    } else if (command == "connect") {
      for (size_t i = 1; i < args.size(); ++i) {
        if (args[i] == "--simulate")
          simulate = true;
        else if (args[i] == "--port" && i + 1 < args.size())
          port = args[++i];
        else
          throw std::runtime_error("Unknown/incomplete connect option: " +
                                   args[i]);
      }
      if (simulate && !port.empty())
        throw std::runtime_error("--simulate cannot be combined with --port");
      set(p.get(), "simulate", simulate);
      set(p.get(), "port", port);
    } else if (command == "pixels") {
      if (args.size() != 2)
        throw std::runtime_error("pixels requires a JSON file path");
      std::ifstream file(args[1], std::ios::binary);
      if (!file)
        throw std::runtime_error("Cannot open pixel file: " + args[1]);
      char buffer[16385];
      file.read(buffer, sizeof(buffer));
      if (file.gcount() > 16384)
        throw std::runtime_error("Pixel file is too large");
      if (file.bad())
        throw std::runtime_error("Cannot read pixel file: " + args[1]);
      std::string data(buffer, size_t(file.gcount()));
      auto values = parse(data);
      pixels(values.get());
      json_object_object_add(p.get(), "pixels", json_object_get(values.get()));
    } else if (command == "rpc") {
      if (args.size() != 2)
        throw std::runtime_error("rpc requires one complete JSON request");
      p = parse(args[1]);
      if (!json_object_is_type(p.get(), json_type_object))
        throw std::runtime_error("RPC request must be a JSON object");
    } else if (command == "stream") {
      if (args.size() != 2 || args[1].empty())
        throw std::runtime_error("stream requires an owner name");
    } else if (command == "status" || command == "disconnect" ||
               command == "pause" || command == "resume" ||
               command == "restart" || command == "blank") {
      if (args.size() != 1)
        throw std::runtime_error("Unexpected arguments for " + command);
    } else
      throw std::runtime_error("Unknown command: " + command);
    if (start)
      control::ipc::ensure_service(socket, simulate, true, port);
    if (command == "stream")
      return stream(args[1], socket);
    auto result = invoke(p.get(), socket);
    std::cout << encode(result.get()) << '\n';
    if (!boolean(result.get(), "ok")) {
      std::cerr << "letkictl: " << string(result.get(), "error") << '\n';
      return 1;
    }
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "letkictl: " << e.what() << '\n';
    return 1;
  }
}
