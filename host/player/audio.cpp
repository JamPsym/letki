#include "player.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <portaudio.h>
#include <sndfile.h>
#include <stdexcept>
#include <thread>
namespace letki {
static_assert(std::atomic<double>::is_always_lock_free,
              "Audio timestamps require lock-free atomics");
uint64_t monotonic_ms() {
  return std::chrono::duration_cast<std::chrono::milliseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}
struct Audio::Impl {
  const Media &media;
  double intro, gain;
  static constexpr uint64_t capacity = 65536;
  std::array<float, capacity * 2> ring{};
  std::atomic<uint64_t> read{0}, write{0}, warnings{0};
  std::atomic<bool> quit{false}, eof{false};
  std::atomic<int> error{0};
  std::thread worker;
  PaStream *stream = nullptr;
  std::atomic<unsigned> epoch_seq{0};
  std::atomic<double> dac{0}, anchor{0}, end{0};
  uint64_t cursor = 0, total = 0, lead = 0;
  double lower = 0;
  bool initialized = false;
  Impl(const Media &m, double i, double g) : media(m), intro(i), gain(g) {
    auto e = Pa_Initialize();
    if (e != paNoError)
      throw std::runtime_error(Pa_GetErrorText(e));
    initialized = true;
  }
  ~Impl() {
    stop();
    if (initialized)
      Pa_Terminate();
  }
  void check(PaError e) {
    if (e != paNoError)
      throw std::runtime_error(Pa_GetErrorText(e));
  }
  static int callback(const void *, void *output, unsigned long count,
                      const PaStreamCallbackTimeInfo *time,
                      PaStreamCallbackFlags flags, void *arg) {
    auto &s = *static_cast<Impl *>(arg);
    auto out = static_cast<float *>(output);
    std::fill(out, out + count * 2, 0.f);
    if (flags)
      s.warnings.fetch_add(1, std::memory_order_seq_cst);
    uint64_t offset = std::min<uint64_t>(count, s.lead);
    double presentation =
        time->outputBufferDacTime + double(s.lead) / s.media.rate;
    s.lead -= offset;
    uint64_t r = s.read.load(std::memory_order_seq_cst),
             w = s.write.load(std::memory_order_seq_cst),
             available = std::min<uint64_t>(
                 {count - offset, w - r, s.total - s.cursor});
    for (uint64_t i = 0; i < available; i++) {
      out[(offset + i) * 2] = s.ring[((r + i) % capacity) * 2];
      out[(offset + i) * 2 + 1] = s.ring[((r + i) % capacity) * 2 + 1];
    }
    s.read.store(r + available, std::memory_order_seq_cst);
    if (available < count - offset && s.cursor + available < s.total)
      s.warnings.fetch_add(1, std::memory_order_seq_cst);
    s.epoch_seq.fetch_add(1, std::memory_order_seq_cst);
    s.dac.store(presentation, std::memory_order_seq_cst);
    s.anchor.store(double(s.cursor) / s.media.rate, std::memory_order_seq_cst);
    s.end.store(double(s.cursor + available) / s.media.rate,
                std::memory_order_seq_cst);
    s.epoch_seq.fetch_add(1, std::memory_order_seq_cst);
    s.cursor += available;
    return s.cursor >= s.total ? paComplete : paContinue;
  }
  void produce(uint64_t start) {
    SF_INFO info{};
    SNDFILE *file = sf_open(media.path.c_str(), SFM_READ, &info);
    if (!file) {
      error = 1;
      eof = true;
      return;
    }
    if (info.samplerate != media.rate || info.channels != media.channels ||
        info.frames != media.frames) {
      sf_close(file);
      error = 5;
      eof = true;
      return;
    }
    uint64_t silence = uint64_t(std::llround(intro * media.rate));
    int64_t at = start > silence ? int64_t(start - silence) : 0;
    if (sf_seek(file, at, SEEK_SET) != at) {
      sf_close(file);
      error = 2;
      eof = true;
      return;
    }
    uint64_t p = start;
    std::vector<float> input(2048 * media.channels);
    while (!quit && p < total) {
      uint64_t w = write.load(std::memory_order_seq_cst),
               r = read.load(std::memory_order_seq_cst),
               n = std::min<uint64_t>({2048, capacity - (w - r), total - p});
      if (!n) {
        std::this_thread::sleep_for(std::chrono::milliseconds(2));
        continue;
      }
      bool silent = p < silence;
      if (silent)
        n = std::min(n, silence - p);
      else {
        auto got = sf_readf_float(file, input.data(), n);
        if (got != int64_t(n)) {
          error = 3;
          break;
        }
      }
      for (uint64_t i = 0; i < n; i++) {
        float l = 0, h = 0;
        if (!silent) {
          l = input[i * media.channels];
          h = input[i * media.channels + (media.channels == 1 ? 0 : 1)];
          if (!std::isfinite(l) || !std::isfinite(h)) {
            l = h = 0;
            error = 4;
          }
        }
        ring[((w + i) % capacity) * 2] = std::clamp(float(l * gain), -1.f, 1.f);
        ring[((w + i) % capacity) * 2 + 1] =
            std::clamp(float(h * gain), -1.f, 1.f);
      }
      write.store(w + n, std::memory_order_seq_cst);
      p += n;
    }
    sf_close(file);
    eof = true;
  }
  void start(double pos) {
    stop();
    quit = false;
    eof = false;
    error = 0;
    read = write = 0;
    dac = 0;
    warnings = 0;
    total = uint64_t(std::llround(intro * media.rate)) + media.frames;
    cursor = std::min(total, uint64_t(std::max(0., pos) * media.rate));
    anchor = end = double(cursor) / media.rate;
    lower = double(cursor) / media.rate;
    lead = uint64_t(media.rate) / 2;
    if (cursor == total)
      return;
    worker = std::thread([this, p = cursor] { produce(p); });
    while (write.load() < std::min<uint64_t>(capacity / 2, total - cursor) &&
           !eof)
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
    if (error) {
      stop();
      throw std::runtime_error("Audio decoder failed during prebuffer");
    }
    try {
      PaStreamParameters out{};
      out.device = Pa_GetDefaultOutputDevice();
      if (out.device == paNoDevice)
        throw std::runtime_error("No audio output device");
      out.channelCount = 2;
      out.sampleFormat = paFloat32;
      out.suggestedLatency = .08;
      check(Pa_OpenStream(&stream, nullptr, &out, media.rate, 512, paNoFlag,
                          callback, this));
      check(Pa_StartStream(stream));
      uint64_t wait = monotonic_ms();
      while (dac.load() == 0) {
        if (monotonic_ms() - wait > 3000)
          throw std::runtime_error("No audio callback");
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }
    } catch (...) {
      stop();
      throw;
    }
  }
  void stop() {
    if (stream) {
      Pa_AbortStream(stream);
      Pa_CloseStream(stream);
      stream = nullptr;
    }
    quit = true;
    if (worker.joinable())
      worker.join();
  }
  double position() const {
    if (error.load())
      throw std::runtime_error("Audio decoder read failed");
    if (!stream)
      return anchor.load();
    for (;;) {
      unsigned a = epoch_seq.load(std::memory_order_seq_cst);
      if (a & 1)
        continue;
      double d = dac.load(std::memory_order_seq_cst),
             p = anchor.load(std::memory_order_seq_cst),
             e = end.load(std::memory_order_seq_cst);
      if (a != epoch_seq.load(std::memory_order_seq_cst))
        continue;
      // A callback describes samples still in the device's future. Permit
      // negative extrapolation so queued output, rather than CPU submission, is
      // the clock.
      return std::clamp(p + Pa_GetStreamTime(stream) - d, lower, e);
    }
  }
};
Audio::Audio(const Media &m, double i, double g) : p(new Impl(m, i, g)) {}
Audio::~Audio() = default;
void Audio::start(double t) { p->start(t); }
void Audio::stop() { p->stop(); }
bool Audio::playing() const {
  return p->stream && Pa_IsStreamActive(p->stream) == 1;
}
double Audio::position() const { return p->position(); }
double Audio::presentation_host_ms() const {
  if (!p->stream)
    return double(monotonic_ms()) - p->anchor.load() * 1000;
  for (;;) {
    unsigned seq = p->epoch_seq.load(std::memory_order_seq_cst);
    if (seq & 1)
      continue;
    double d = p->dac.load(std::memory_order_seq_cst),
           a = p->anchor.load(std::memory_order_seq_cst);
    if (seq != p->epoch_seq.load(std::memory_order_seq_cst))
      continue;
    return double(monotonic_ms()) +
           (d - Pa_GetStreamTime(p->stream) - a) * 1000;
  }
}
uint64_t Audio::underruns() const { return p->warnings.load(); }
} // namespace letki
