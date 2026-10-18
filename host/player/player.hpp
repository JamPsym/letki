#pragma once
#include "rhythm.hpp"
#include <array>
#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
namespace letki {
using Bytes = std::vector<uint8_t>;
using Frame = std::array<std::array<uint8_t, 64>, 5>;
uint64_t monotonic_ms();
struct Cue {
  double at = 0, duration = 0;
  std::string text, effect, label, mode = "scroll", clock = "grid";
  double level = 1, speed = 1, sustain = 0;
  unsigned variant = 0;
};
struct Show {
  std::string name, audio, video, artist, title, style = "bells";
  double intro = 8, gain = .7, offset = 0, transition = 0, output_gamma = 1;
  Rhythm rhythm;
  std::vector<Cue> cues;
  static Show load(const std::string &path);
};
struct Feature {
  float rms = 0, bass = 0, treble = 0, onset = 0;
  std::array<float, 24> bands{};
  // Per-register attacks retained in source time for pitched/instrument scenes.
  // Age/hit describe the last event; count==0 means no event has occurred.
  std::array<float, 24> band_age{}, band_hit{};
  std::array<unsigned, 24> band_count{};
  float motion = 0, mids = 0, low_flux = 0, high_flux = 0;
  float bass_age = 99, treble_age = 99, bass_hit = 0, treble_hit = 0;
  unsigned bass_count = 0, treble_count = 0;
};
struct Media {
  std::string path;
  int rate = 0, channels = 0;
  int64_t frames = 0;
  std::vector<Feature> features;
  explicit Media(const std::string &path);
  double duration() const { return double(frames) / rate; }
  Feature feature(double seconds) const;
};
Frame render(const Show &, const Media &, double show_seconds);
std::string caption(const Show &, double show_seconds);
bool theatre_style(const std::string &);
Frame theatre(const Feature &, double, const std::string &);
struct VideoImage {
  int width = 0, height = 0, stride = 0;
  std::vector<uint8_t> rgb;
};
struct Video {
  struct Impl;
  std::unique_ptr<Impl> p;
  explicit Video(const std::string &);
  ~Video();
  const VideoImage &image(double seconds);
  double duration() const;
};

struct Audio {
  struct Impl;
  std::unique_ptr<Impl> p;
  Audio(const Media &, double intro, double gain);
  ~Audio();
  void start(double position = 0);
  void stop();
  bool playing() const;
  double position() const;
  double presentation_host_ms() const;
  uint64_t underruns() const;
};
struct Message {
  uint8_t node = 0, op = 0;
  uint16_t session = 0, request = 0;
  Bytes data;
};
Bytes encode(const Message &);
Message decode(const Bytes &);
struct Transport {
  virtual ~Transport() = default;
  virtual std::vector<Bytes> exchange(const std::vector<Bytes> &, int) = 0;
  virtual void rate(unsigned) = 0;
  virtual bool simulated() const = 0;
  virtual void advance(uint64_t) {};
  virtual Frame pixels() { return {}; };
};
std::unique_ptr<Transport> serial(const std::string &path);
// An empty result means no matching adapter. Ambiguity is an error.
std::string discover_serial(const std::string &by_id = "/dev/serial/by-id");
struct ReplyTimeout : std::runtime_error {
  using std::runtime_error::runtime_error;
};
std::unique_ptr<Transport> simulation();
struct Info {
  Bytes raw;
  unsigned slots = 0, storage = 0, length = 0, arena = 0;
  uint32_t late = 0, errors = 0, drops = 0;
  std::string uid;
};
struct Clock {
  int64_t offset = 0;
  unsigned uncertainty = 0, age = 65535;
};
class Chain {
  std::unique_ptr<Transport> link;
  uint16_t session = 0, generation = 0;
  bool clocks_set = false;
  std::array<uint16_t, 5> sequence{};
  std::vector<Bytes> transact(std::vector<Message>, int);

public:
  std::array<Info, 5> info;
  std::array<Clock, 5> clocks{};
  unsigned baud = 115200, slots = 0, format = 1;
  bool retained = false;
  uint64_t retries = 0, invalid = 0, frames = 0;
  bool resume_on_close = false;
  explicit Chain(std::unique_ptr<Transport>);
  ~Chain();
  std::vector<Bytes> batch(uint8_t op, const std::vector<Bytes> &data,
                           int timeout = 250);
  Bytes request(unsigned node, uint8_t op, const Bytes &data = {},
                int timeout = 250);
  void all(uint8_t op, const Bytes &data = {});
  void inspect();
  bool sync();
  void set_baud(unsigned);
  void prepare();
  void frame(const Frame &, uint64_t host_deadline);
  void restore();
  Frame pixels(uint64_t now);
  bool simulated() const { return link->simulated(); }
};
void put16(Bytes &, uint16_t);
void put32(Bytes &, uint32_t);
uint16_t get16(const Bytes &, size_t);
uint32_t get32(const Bytes &, size_t);
} // namespace letki
