#include "player.hpp"
#include <algorithm>
#include <chrono>
#include <cstring>
#include <dlfcn.h>
#include <fcntl.h>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <map>
#include <poll.h>
#include <random>
#include <sstream>
#include <stdexcept>
#include <sys/file.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <termios.h>
#include <thread>
#include <unistd.h>
namespace letki {
void put16(Bytes &b, uint16_t v) {
  b.push_back(v & 255);
  b.push_back(v >> 8);
}
void put32(Bytes &b, uint32_t v) {
  put16(b, v & 65535);
  put16(b, v >> 16);
}
uint16_t get16(const Bytes &b, size_t p) {
  return b.at(p) | (b.at(p + 1) << 8);
}
uint32_t get32(const Bytes &b, size_t p) {
  return get16(b, p) | (uint32_t(get16(b, p + 2)) << 16);
}
static uint16_t crc(const Bytes &b) {
  uint16_t c = 65535;
  for (auto v : b) {
    c ^= uint16_t(v) << 8;
    for (int i = 0; i < 8; i++)
      c = uint16_t((c << 1) ^ ((c & 32768) ? 0x1021 : 0));
  }
  return c;
}
Bytes encode(const Message &m) {
  if (m.data.size() > 48)
    throw std::runtime_error("Packet payload too large");
  Bytes b{1, m.op, m.node};
  put16(b, m.session);
  put16(b, m.request);
  b.push_back(m.data.size());
  b.insert(b.end(), m.data.begin(), m.data.end());
  put16(b, crc(b));
  Bytes out{0};
  size_t p = 0;
  unsigned code = 1;
  for (auto v : b) {
    if (v) {
      out.push_back(v);
      code++;
    } else {
      out[p] = code;
      p = out.size();
      out.push_back(0);
      code = 1;
    }
  }
  out[p] = code;
  out.push_back(0);
  return out;
}
Message decode(const Bytes &wire) {
  if (wire.size() < 2 || wire.size() > 60 || wire.back())
    throw std::runtime_error("Invalid framing");
  Bytes b;
  size_t i = 0;
  while (i < wire.size() - 1) {
    unsigned n = wire[i++];
    if (!n || i + n - 1 > wire.size() - 1)
      throw std::runtime_error("Invalid COBS");
    for (unsigned j = 1; j < n; j++)
      b.push_back(wire[i++]);
    if (n != 255 && i < wire.size() - 1)
      b.push_back(0);
  }
  if (b.size() < 10 || b[0] != 1 || b[7] > 48 || b.size() != size_t(10 + b[7]))
    throw std::runtime_error("Invalid packet length");
  uint16_t check = get16(b, b.size() - 2);
  b.resize(b.size() - 2);
  if (crc(b) != check)
    throw std::runtime_error("Invalid CRC");
  return {b[2], b[1], get16(b, 3), get16(b, 5), Bytes(b.begin() + 8, b.end())};
}
namespace {
struct Serial final : Transport {
  int fd = -1;
  termios saved{};
  bool configured = false;
  Bytes tail;
  bool discard = false;
  explicit Serial(const std::string &name) {
    // TIOCEXCL prevents later opens but cannot evict an existing picocom
    // reader. Check before opening, then take both kernel and advisory
    // exclusivity.
    auto device_path = std::filesystem::canonical(name).string();
    pid_t child = fork();
    if (child < 0)
      throw std::runtime_error("Cannot check serial ownership");
    if (child == 0) {
      execlp("fuser", "fuser", "-s", device_path.c_str(),
             static_cast<char *>(nullptr));
      _exit(127);
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
      if (errno != EINTR)
        throw std::runtime_error("Cannot check serial ownership");
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) > 1)
      throw std::runtime_error(
          "fuser (psmisc) is required to check serial ownership");
    if (WEXITSTATUS(status) == 0)
      throw std::runtime_error(
          "Serial port is in use; close picocom or another reader first");
    fd = open(name.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0)
      throw std::runtime_error("Cannot open serial port: " + name + ": " +
                               strerror(errno));
    try {
      if (flock(fd, LOCK_EX | LOCK_NB) || ioctl(fd, TIOCEXCL) ||
          tcgetattr(fd, &saved))
        throw std::runtime_error("Serial port busy or not a tty");
      configured = true;
      termios t = saved;
      cfmakeraw(&t);
      t.c_cflag = (t.c_cflag & ~(CSTOPB | PARENB | CRTSCTS | CSIZE)) | CS8 |
                  CLOCAL | CREAD;
      t.c_cc[VMIN] = 0;
      t.c_cc[VTIME] = 0;
      cfsetispeed(&t, B115200);
      cfsetospeed(&t, B115200);
      if (tcsetattr(fd, TCSANOW, &t))
        throw std::runtime_error("Cannot configure serial");
      tcflush(fd, TCIOFLUSH);
      uint8_t nul = 0;
      if (write(fd, &nul, 1) != 1)
        throw std::runtime_error("Cannot initialize serial");
    } catch (...) {
      close_port();
      throw;
    }
  }
  void close_port() {
    if (fd >= 0) {
      if (configured)
        tcsetattr(fd, TCSANOW, &saved);
      ioctl(fd, TIOCNXCL);
      close(fd);
      fd = -1;
    }
  }
  ~Serial() { close_port(); }
  bool simulated() const override { return false; }
  void rate(unsigned n) override {
    speed_t b = n == 115200 ? B115200 : n == 230400 ? B230400 : 0;
    if (!b)
      throw std::runtime_error("Use qualified 115200 or 230400 baud");
    termios t{};
    if (tcgetattr(fd, &t) || tcdrain(fd))
      throw std::runtime_error("Serial baud read failed");
    cfsetispeed(&t, b);
    cfsetospeed(&t, b);
    if (tcsetattr(fd, TCSANOW, &t))
      throw std::runtime_error("Serial baud change failed");
  }
  std::vector<Bytes> exchange(const std::vector<Bytes> &messages,
                              int timeout) override {
    uint64_t deadline = monotonic_ms() + timeout;
    Bytes bytes;
    for (auto &m : messages)
      bytes.insert(bytes.end(), m.begin(), m.end());
    size_t at = 0;
    while (at < bytes.size()) {
      auto n = write(fd, bytes.data() + at, bytes.size() - at);
      if (n > 0) {
        at += n;
        continue;
      }
      if (n < 0 && errno != EAGAIN && errno != EINTR)
        throw std::runtime_error("Serial write failed");
      pollfd p{fd, POLLOUT, 0};
      int remain = int(deadline - monotonic_ms());
      if (remain <= 0 || poll(&p, 1, remain) <= 0)
        throw std::runtime_error("Serial write timeout");
    }
    std::vector<Bytes> replies;
    std::vector<bool> seen(messages.size());
    while (monotonic_ms() < deadline) {
      pollfd p{fd, POLLIN, 0};
      int r = poll(&p, 1, int(deadline - monotonic_ms()));
      if (r < 0 && errno == EINTR)
        continue;
      if (r < 0 || (p.revents & (POLLHUP | POLLERR | POLLNVAL)))
        throw std::runtime_error("Serial disconnected");
      if (!r)
        break;
      uint8_t buffer[512];
      auto n = read(fd, buffer, sizeof buffer);
      if (n < 0 && (errno == EAGAIN || errno == EINTR))
        continue;
      if (n <= 0)
        throw std::runtime_error("Serial read failed");
      for (ssize_t i = 0; i < n; i++) {
        uint8_t v = buffer[i];
        if (!v) {
          if (!discard && !tail.empty()) {
            tail.push_back(0);
            replies.push_back(tail);
          }
          tail.clear();
          discard = false;
        } else if (!discard) {
          if (tail.size() >= 59) {
            tail.clear();
            discard = true;
          } else
            tail.push_back(v);
        }
      }
      for (auto &raw : replies)
        try {
          auto m = decode(raw);
          for (size_t j = 0; j < messages.size(); j++) {
            auto q = decode(messages[j]);
            if (m.node == q.node && m.session == q.session &&
                m.request == q.request &&
                (m.op == q.op || m.op == (q.op | 128)))
              seen[j] = true;
          }
        } catch (const std::exception &) {
        }
      if (std::all_of(seen.begin(), seen.end(), [](bool v) { return v; }))
        break;
      if (replies.size() > 128)
        throw std::runtime_error("Excess serial traffic");
    }
    return replies;
  }
};
struct Sim final : Transport {
  void *library = nullptr;
  void *context = nullptr;
  void *(*create)() = nullptr;
  void (*destroy)(void *) = nullptr;
  unsigned (*exchange_fn)(void *, unsigned, uint8_t *, unsigned,
                          uint32_t) = nullptr;
  const uint8_t *(*render_fn)(void *, unsigned, uint32_t) = nullptr;
  uint64_t now = 0;
  Sim() {
    library = dlopen("build/general/libletki-general.so", RTLD_NOW);
    if (!library)
      throw std::runtime_error("Run make general-host from repository root");
    create =
        reinterpret_cast<decltype(create)>(dlsym(library, "lg_sim_create"));
    destroy =
        reinterpret_cast<decltype(destroy)>(dlsym(library, "lg_sim_destroy"));
    exchange_fn = reinterpret_cast<decltype(exchange_fn)>(
        dlsym(library, "lg_sim_exchange"));
    render_fn =
        reinterpret_cast<decltype(render_fn)>(dlsym(library, "lg_sim_render"));
    if (!create || !destroy || !exchange_fn || !render_fn) {
      dlclose(library);
      throw std::runtime_error("Incompatible simulator library");
    }
    context = create();
    if (!context) {
      dlclose(library);
      throw std::bad_alloc();
    }
    now = monotonic_ms();
  }
  ~Sim() {
    destroy(context);
    dlclose(library);
  }
  bool simulated() const override { return true; }
  void rate(unsigned) override {}
  void advance(uint64_t t) override {
    now = t;
    for (unsigned i = 0; i < 5; i++)
      render_fn(context, i, uint32_t(now));
  }
  Frame pixels() override {
    Frame f;
    for (unsigned i = 0; i < 5; i++)
      std::copy_n(render_fn(context, i, uint32_t(now)), 64, f[i].begin());
    return f;
  }
  std::vector<Bytes> exchange(const std::vector<Bytes> &messages,
                              int) override {
    std::vector<Bytes> out;
    advance(std::max(now, monotonic_ms()));
    for (auto raw : messages) {
      for (unsigned i = 0; i < 5; i++) {
        raw.resize(60);
        unsigned used = exchange_fn(context, i, raw.data(), decode_length(raw),
                                    uint32_t(now));
        if (!used) {
          raw.clear();
          break;
        }
        raw.resize(used);
      }
      if (!raw.empty())
        out.push_back(raw);
    }
    return out;
  }
  static unsigned decode_length(const Bytes &b) {
    return unsigned(std::find(b.begin(), b.end(), 0) - b.begin());
  }
};
Info parse_info(const Bytes &b, bool hello) {
  if (b.size() != 47 || b[0] != 1 || b[2] != 5)
    throw std::runtime_error("Incompatible five-tile firmware capabilities");
  Info i;
  i.raw = b;
  i.slots = b[3];
  i.storage = b[21];
  i.length = get16(b, 6);
  i.arena = get16(b, 44);
  i.late = get32(b, 28);
  if (hello) {
    std::ostringstream s;
    for (unsigned p = 34; p < 42; p++)
      s << std::hex << std::setw(2) << std::setfill('0') << unsigned(b[p]);
    i.uid = s.str();
  } else {
    i.errors = get32(b, 34);
    i.drops = get32(b, 38);
  }
  return i;
}
} // namespace
std::unique_ptr<Transport> serial(const std::string &p) {
  return std::make_unique<Serial>(p);
}
std::string discover_serial(const std::string &by_id) {
  std::error_code error;
  std::filesystem::directory_iterator entries(by_id, error);
  if (error == std::errc::no_such_file_or_directory)
    return {};
  if (error)
    throw std::runtime_error("Cannot scan serial adapters: " + error.message());
  std::map<std::string, std::string> devices;
  for (const auto &entry : entries) {
    auto name = entry.path().filename().string();
    if (name.find("WCH-Link") == std::string::npos)
      continue;
    auto target = std::filesystem::canonical(entry.path(), error);
    if (error == std::errc::no_such_file_or_directory)
      continue; // A disconnected adapter can leave a stale link.
    if (error)
      throw std::runtime_error("Cannot resolve serial adapter: " +
                               error.message());
    auto alias = entry.path().string();
    auto found = devices.find(target.string());
    if (found == devices.end() || alias < found->second)
      devices[target.string()] = alias;
  }
  if (devices.empty())
    return {};
  if (devices.size() > 1)
    throw std::runtime_error(
        "Multiple WCH-Link serial adapters found; select one with --port PATH");
  return devices.begin()->second;
}
std::unique_ptr<Transport> simulation() { return std::make_unique<Sim>(); }
Chain::Chain(std::unique_ptr<Transport> t) : link(std::move(t)) {
  std::random_device rd;
  session = uint16_t(rd()) | 1;
  for (unsigned i = 0; i < 5; i++) {
    info[i] = parse_info(request(i, 1), true);
    if (info[i].raw[1] != i)
      throw std::runtime_error("Wrong tile ID");
  }
  sync();
}
Chain::~Chain() {
  try {
    if (resume_on_close)
      restore();
  } catch (const std::exception &e) {
    std::cerr << "Chain cleanup: " << e.what() << "\n";
  }
  if (baud != 115200)
    try {
      set_baud(115200);
    } catch (const std::exception &e) {
      std::cerr << "Baud cleanup: " << e.what()
                << " (idle lease returns to 115200 in 10s)\n";
    }
}
std::vector<Bytes> Chain::transact(std::vector<Message> qs, int timeout) {
  std::vector<Bytes> wires, out(qs.size());
  std::vector<bool> done(qs.size());
  for (auto &q : qs) {
    q.session = session;
    q.request = ++sequence.at(q.node);
    wires.push_back(encode(q));
  }
  for (unsigned attempt = 0; attempt < 3; attempt++) {
    std::vector<Bytes> pending;
    for (size_t i = 0; i < qs.size(); i++)
      if (!done[i])
        pending.push_back(wires[i]);
    if (pending.empty())
      return out;
    if (attempt)
      retries++;
    auto replies = link->exchange(pending, timeout);
    for (auto &raw : replies) {
      Message r;
      try {
        r = decode(raw);
      } catch (const std::exception &) {
        invalid++;
        continue;
      }
      for (size_t i = 0; i < qs.size(); i++) {
        auto &q = qs[i];
        if (r.node != q.node || r.session != q.session ||
            r.request != q.request)
          continue;
        if (r.op == q.op)
          throw std::runtime_error("Tile " + std::to_string(q.node) +
                                   " missing from UART chain");
        if (r.op != (q.op | 128))
          continue;
        if (r.data.empty() || r.data[0])
          throw std::runtime_error(
              "Tile " + std::to_string(q.node) + " operation " +
              std::to_string(q.op) + " status " +
              (r.data.empty() ? "missing" : std::to_string(r.data[0])));
        done[i] = true;
        out[i] = Bytes(r.data.begin() + 1, r.data.end());
      }
    }
  }
  if (!std::all_of(done.begin(), done.end(), [](bool x) { return x; }))
    throw ReplyTimeout("Missing UART replies after 3 attempts");
  return out;
}
std::vector<Bytes> Chain::batch(uint8_t op, const std::vector<Bytes> &data,
                                int timeout) {
  if (data.size() != 5)
    throw std::runtime_error("Expected five tile payloads");
  std::vector<Message> qs;
  for (unsigned i = 0; i < 5; i++)
    qs.push_back({uint8_t(i), op, 0, 0, data[i]});
  return transact(qs, timeout);
}
Bytes Chain::request(unsigned n, uint8_t op, const Bytes &b, int timeout) {
  if (n >= 5)
    throw std::runtime_error("Invalid tile");
  return transact({Message{uint8_t(n), op, 0, 0, b}}, timeout)[0];
}
void Chain::all(uint8_t op, const Bytes &b) {
  batch(op, std::vector<Bytes>(5, b));
}
void Chain::inspect() {
  for (unsigned i = 0; i < 5; i++) {
    auto uid = info[i].uid;
    info[i] = parse_info(request(i, 2), false);
    info[i].uid = uid;
  }
}
bool Chain::sync() {
  auto old = clocks;
  for (unsigned i = 0; i < 5; i++) {
    unsigned best = ~0U;
    for (unsigned sample = 0; sample < 3; sample++) {
      uint64_t before = monotonic_ms();
      auto b = request(i, 3, {}, 100);
      uint64_t after = monotonic_ms();
      if (b.size() != 10)
        throw std::runtime_error("Invalid TIME reply");
      unsigned rtt = after - before;
      if (rtt < best) {
        best = rtt;
        uint64_t mid = (before + after) / 2;
        int32_t delta = int32_t(get32(b, 0) - uint32_t(mid));
        clocks[i] = {delta, (rtt + 1) / 2, get16(b, 8)};
      }
    }
  }
  bool jump = false;
  for (unsigned i = 0; i < 5; i++) {
    int32_t delta = int32_t(uint32_t(clocks[i].offset - old[i].offset));
    if (clocks_set &&
        std::abs(int64_t(delta)) >
            std::max(20U, old[i].uncertainty + clocks[i].uncertainty + 10))
      jump = true;
  }
  clocks_set = true;
  return jump;
}
void Chain::set_baud(unsigned rate) {
  if (simulated()) {
    baud = rate;
    return;
  }
  if (rate != 115200 && rate != 230400)
    throw std::runtime_error("Baud must be qualified 115200 or 230400");
  Bytes b;
  put16(b, rate / 100);
  all(18, b);
  if (!simulated())
    std::this_thread::sleep_for(std::chrono::milliseconds(1150));
  link->rate(rate);
  baud = rate;
  try {
    all(19);
    sync();
  } catch (...) {
    if (!simulated())
      std::this_thread::sleep_for(std::chrono::milliseconds(10500));
    link->rate(115200);
    baud = 115200;
    throw;
  }
}
void Chain::prepare() {
  resume_on_close = true;
  all(9);
  all(11);
  inspect();
  unsigned stride = format == 2 ? 80 : 48;
  slots = 16;
  retained = true;
  for (auto &i : info) {
    if (i.raw[23] || i.raw[33])
      throw std::runtime_error("Finish active upload before starting player");
    unsigned used = i.storage == 0 ? i.length : 0;
    if (i.arena < used + stride * 2)
      throw std::runtime_error("RAM show leaves fewer than two GRAY4 slots; "
                               "load a smaller show first");
    slots = std::min(slots, (i.arena - used) / stride);
    retained &= i.storage != 0 && i.length > 0;
  }
  all(16, {uint8_t(slots), uint8_t(format)});
  all(12, {100});
  resume_on_close = true;
}
void Chain::frame(const Frame &f, uint64_t when) {
  uint16_t g = ++generation;
  std::vector<Bytes> begin(5), extra(5), commit(5);
  for (unsigned i = 0; i < 5; i++) {
    auto &b = begin[i];
    put16(b, g);
    put32(b, uint32_t(when + clocks[i].offset));
    b.push_back(uint8_t(format));
    Bytes packed;
    for (auto p : f[i])
      if (p > 100)
        throw std::runtime_error("Pixel out of range");
    if (format == 2)
      packed.assign(f[i].begin(), f[i].end());
    else
      for (unsigned j = 0; j < 64; j += 2)
        packed.push_back(uint8_t((f[i][j] * 15 + 50) / 100) |
                         uint8_t((f[i][j + 1] * 15 + 50) / 100) << 4);
    b.insert(b.end(), packed.begin(),
             packed.begin() + std::min(size_t(41), packed.size()));
    if (format == 2) {
      put16(extra[i], g);
      extra[i].push_back(41);
      extra[i].insert(extra[i].end(), packed.begin() + 41, packed.end());
    }
    put16(commit[i], g);
  }
  int timeout = baud == 230400 ? 100 : 250;
  batch(13, begin, timeout);
  if (format == 2)
    batch(14, extra, timeout);
  batch(15, commit, timeout);
  frames++;
}
void Chain::restore() {
  all(11);
  all(9);
  inspect();
  unsigned available = 2;
  for (auto &i : info)
    available =
        std::min(available, (i.arena - (i.storage == 0 ? i.length : 0)) / 80);
  all(16, {uint8_t(available), 2});
  sync();
  std::vector<Bytes> play(5);
  uint64_t when = monotonic_ms() + 300;
  for (unsigned i = 0; i < 5; i++) {
    if (info[i].length && clocks[i].age > 500)
      throw std::runtime_error("Cannot resume saved show: stale I2C clock");
    put32(play[i], uint32_t(when + clocks[i].offset));
    put32(play[i], 0);
    Bytes r{0, 0, 8};
    auto h = info[i].length ? request(i, 17, r) : Bytes(8);
    play[i].push_back(h.at(7) & 1);
  }
  for (unsigned i = 0; i < 5; i++)
    if (info[i].length)
      request(i, 8, play[i]);
  resume_on_close = false;
}
Frame Chain::pixels(uint64_t now) {
  link->advance(now);
  return link->pixels();
}
} // namespace letki
