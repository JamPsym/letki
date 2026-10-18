#include "player.hpp"
#include "dance.hpp"
#include "adagio.hpp"
#include "lamour.hpp"
#include "fusion.hpp"
#include "bells.hpp"
#include <algorithm>
#include <cmath>
#include <complex>
#include <filesystem>
#include <json-c/json.h>
#include <set>
#include <sndfile.h>
#include <stdexcept>
extern "C" {
#include "pwm_show.h"
uint8_t font_compact_column(wchar_t, uint8_t);
}
namespace letki {
namespace {
json_object *field(json_object *o, const char *key) {
  json_object *v = nullptr;
  json_object_object_get_ex(o, key, &v);
  return v;
}
std::string str(json_object *o, const char *k, const std::string &d = "") {
  auto v = field(o, k);
  if (!v)
    return d;
  if (!json_object_is_type(v, json_type_string))
    throw std::runtime_error(std::string(k) + " must be a string");
  return json_object_get_string(v);
}
double num(json_object *o, const char *k, double d) {
  auto v = field(o, k);
  if (!v)
    return d;
  if (!json_object_is_type(v, json_type_int) &&
      !json_object_is_type(v, json_type_double))
    throw std::runtime_error(std::string(k) + " must be numeric");
  double n = json_object_get_double(v);
  if (!std::isfinite(n))
    throw std::runtime_error("Non-finite number");
  return n;
}
const std::set<std::string> styles = {"piano",
                                      "organ",
                                      "mallets",
                                      "bass-guitar",
                                      "guitar",
                                      "guitar-fast",
                                      "guitar-duo",
                                      "mandolin",
                                      "tubular-bells",
                                      "ribbons",
                                      "bells",
                                      "strings",
                                      "pwm",
                                      "ribbon",
                                      "ripple",
                                      "embers",
                                      "lanterns",
                                      "ladder",
                                      "daisy",
                                      "bars",
                                      "weird",
                                      "choreography",
                                      "music-ribbon",
                                      "music-ripple",
                                      "music-lanterns",
                                      "music-daisy", "dance-steps", "dance-accordion",
                                      "dance-clap", "dance-weave", "dance-skirts", "dance-flowers",
                                      "fusion-duet", "fusion-ride", "fusion-radio", "fusion-drama", "fusion-toast",
                                      "lamour-theme", "lamour-wings", "lamour-floor",
                                      "adagio-bows", "adagio-vault", "adagio-shutters", "adagio-prism",
                                      "bells-hammers", "bells-gears", "bells-weft", "bells-monoliths",
                                      "bells-guitar", "bells-bass", "bells-mandolin", "bells-duet"};
std::vector<uint32_t> text_chars(const std::string &s) {
  std::vector<uint32_t> out;
  for (size_t i = 0; i < s.size();) {
    uint32_t c = (uint8_t)s[i++];
    unsigned n = 0;
    if (c >= 0xc2 && c <= 0xdf) {
      c &= 31;
      n = 1;
    } else if (c >= 0xe0 && c <= 0xef) {
      c &= 15;
      n = 2;
    } else if (c >= 0xf0 && c <= 0xf4) {
      c &= 7;
      n = 3;
    } else if (c >= 128)
      throw std::runtime_error("Invalid UTF-8 text");
    unsigned count = n;
    while (n--) {
      if (i == s.size() || ((uint8_t)s[i] & 192) != 128)
        throw std::runtime_error("Invalid UTF-8 text");
      c = (c << 6) | ((uint8_t)s[i++] & 63);
    }
    if ((count == 1 && c < 128) || (count == 2 && c < 2048) ||
        (count == 3 && c < 65536) || c > 0x10ffff ||
        (c >= 0xd800 && c <= 0xdfff))
      throw std::runtime_error("Invalid UTF-8 text");
    if (c >= 'a' && c <= 'z')
      c -= 32;
    static const uint32_t low[] = {0x105, 0x107, 0x119, 0x142, 0x144,
                                   0xf3,  0x15b, 0x17a, 0x17c},
                          up[] = {0x104, 0x106, 0x118, 0x141, 0x143,
                                  0xd3,  0x15a, 0x179, 0x17b};
    for (unsigned j = 0; j < 9; j++)
      if (c == low[j])
        c = up[j];
    out.push_back(c);
  }
  return out;
}
void text(Frame &f, const std::string &s, double progress, unsigned level = 100,
          bool centered = false) {
  auto chars = text_chars(s);
  int gap = 1;
  auto measure = [&]() {
    int width = 0;
    for (auto c : chars)
      width += c == ' ' ? 2 : 3 + gap;
    return width;
  };
  int width = measure();
  if (centered && width > 40) {
    gap = 0;
    width = measure();
  }
  int x = centered && width <= 40 ? (40 - width) / 2
                                  : 40 - int(progress * (width + 40));
  for (auto c : chars) {
    if (c == ' ') {
      x += 2;
      continue;
    }
    for (int j = 0; j < 3; j++) {
      uint8_t bits = font_compact_column(wchar_t(c), j);
      int gx = x + j;
      if (gx < 0 || gx >= 40)
        continue;
      for (int y = 0; y < 8; y++)
        if (bits & (1 << y))
          f[gx / 8][y * 8 + gx % 8] = uint8_t(level);
    }
    x += 3 + gap;
  }
}
} // namespace
Show Show::load(const std::string &path) {
  std::unique_ptr<json_object, decltype(&json_object_put)> root(
      json_object_from_file(path.c_str()), json_object_put);
  if (!root || !json_object_is_type(root.get(), json_type_object))
    throw std::runtime_error("Cannot parse show: " + path);
  auto o = root.get();
  Show s;
  s.name = str(o, "name");
  s.audio = str(o, "audio");
  s.video = str(o, "video");
  s.title = str(o, "title", s.name);
  s.artist = str(o, "artist");
  s.style = str(o, "style", "bells");
  s.intro = num(o, "intro_seconds", 8);
  s.gain = num(o, "gain", .7);
  s.offset = num(o, "visual_offset_ms", 0);
  s.transition = num(o, "transition_seconds", 0);
  s.output_gamma = num(o, "output_gamma", 1);
  if (s.name.empty() || s.intro < 0 || s.intro > 120 || s.gain < 0 ||
      s.gain > 1 || s.output_gamma < .25 || s.output_gamma > 3 || s.transition < 0 || s.transition > 5 ||
      std::abs(s.offset) > 2000 || !styles.count(s.style))
    throw std::runtime_error("Invalid show name, style, gain, intro or offset");
  if (!s.audio.empty() && std::filesystem::path(s.audio).is_relative())
    s.audio = (std::filesystem::absolute(path).parent_path() / s.audio)
                  .lexically_normal()
                  .string();
  if (!s.video.empty() && std::filesystem::path(s.video).is_relative())
    s.video = (std::filesystem::absolute(path).parent_path() / s.video)
                  .lexically_normal()
                  .string();
  if (auto r = field(o, "rhythm")) {
    if (!json_object_is_type(r, json_type_object))
      throw std::runtime_error("rhythm must be an object");
    s.rhythm.bpm = num(r, "bpm", 120);
    s.rhythm.offset = num(r, "offset", 0);
    if (auto anchors = field(r, "anchors")) {
      if (!json_object_is_type(anchors, json_type_array) ||
          json_object_array_length(anchors) > 10000)
        throw std::runtime_error("rhythm anchors must be an array (max 10000)");
      for (size_t i = 0; i < json_object_array_length(anchors); ++i) {
        auto a = json_object_array_get_idx(anchors, i);
        if (!json_object_is_type(a, json_type_object) || !field(a, "at") || !field(a, "beat"))
          throw std::runtime_error("rhythm anchor requires at and beat");
        s.rhythm.anchors.push_back({num(a, "at", 0), num(a, "beat", 0)});
      }
    }
    s.rhythm.validate();
  }
  auto cues = field(o, "cues");
  if (cues) {
    if (!json_object_is_type(cues, json_type_array) ||
        json_object_array_length(cues) > 10000)
      throw std::runtime_error("cues must be an array (max 10000)");
    for (size_t i = 0; i < json_object_array_length(cues); i++) {
      auto c = json_object_array_get_idx(cues, i);
      if (!json_object_is_type(c, json_type_object))
        throw std::runtime_error("Invalid cue");
      Cue q;
      q.at = num(c, "at", 0);
      q.duration = num(c, "duration", 6);
      q.text = str(c, "text");
      q.effect = str(c, "effect");
      q.mode = str(c, "mode", "scroll");
      q.label = str(c, "label");
      q.clock = str(c, "clock", "grid");
      if (q.clock != "grid" && q.clock != "bass" && q.clock != "treble")
        throw std::runtime_error("Cue clock must be grid, bass or treble");
      q.level = num(c, "level", 1);
      q.speed = num(c, "speed", 1);
      q.sustain = num(c, "sustain", 0);
      double variant = num(c, "variant", 0);
      if (q.level < 0 || q.level > 1 || q.speed < .1 || q.speed > 3 ||
          q.sustain < 0 || q.sustain > 1 || variant < 0 || variant > 3 ||
          variant != std::floor(variant))
        throw std::runtime_error(
            "Invalid cue level, speed, sustain or variant");
      q.variant = unsigned(variant);
      if (q.mode != "scroll" && q.mode != "center")
        throw std::runtime_error("Cue mode must be scroll or center");
      if (q.at < 0 || q.duration <= 0 || q.duration > 86400 ||
          (!q.effect.empty() && !styles.count(q.effect)))
        throw std::runtime_error("Invalid cue timing or effect");
      text_chars(q.text);
      s.cues.push_back(q);
    }
    std::stable_sort(s.cues.begin(), s.cues.end(),
                     [](const Cue &a, const Cue &b) { return a.at < b.at; });
  }
  text_chars(s.title);
  text_chars(s.artist);
  return s;
}
Media::Media(const std::string &name) : path(name) {
  SF_INFO info{};
  std::unique_ptr<SNDFILE, decltype(&sf_close)> file(
      sf_open(path.c_str(), SFM_READ, &info), sf_close);
  if (!file)
    throw std::runtime_error("Cannot decode audio: " + path + ": " +
                             sf_strerror(nullptr));
  rate = info.samplerate;
  channels = info.channels;
  frames = info.frames;
  if (rate < 8000 || rate > 192000 || channels < 1 || channels > 2 ||
      frames <= 0 || duration() > 21600)
    throw std::runtime_error(
        "Audio must be mono or stereo, 8..192kHz, nonempty, at most 6 hours");
  // Centred Hann windows, radix-2 FFT, 24 logarithmic bands, 50 Hz analysis.
  unsigned size = 1;
  while (size < unsigned(rate * .04))
    size *= 2;
  unsigned hop = unsigned(rate / 50);
  std::vector<float> history(size), input(size * channels), window(size);
  std::vector<std::complex<float>> bins(size), roots(size / 2);
  for (unsigned i = 0; i < size; i++)
    window[i] =
        float(.5 - .5 * std::cos(2 * 3.141592653589793 * i / (size - 1)));
  for (unsigned i = 0; i < size / 2; i++)
    roots[i] = std::polar(1.f, float(-2 * 3.141592653589793 * i / size));
  auto read = [&](unsigned at, unsigned count) {
    auto n = sf_readf_float(file.get(), input.data(), count);
    if (n < 0 || sf_error(file.get()))
      throw std::runtime_error("Audio analysis read failed");
    for (unsigned i = 0; i < count; i++) {
      double v = 0;
      if (i < unsigned(n))
        for (int c = 0; c < channels; c++)
          v += input[i * channels + c] / channels;
      if (!std::isfinite(v))
        throw std::runtime_error("Non-finite audio samples");
      history[at + i] = float(v);
    }
  };
  read(size / 2, size / 2);
  float peak = .00001f;
  std::array<float, 24> band_peak{}, previous{};
  for (int64_t center = 0; center < frames; center += hop) {
    double square = 0;
    for (unsigned i = 0; i < size; i++) {
      bins[i] = {history[i] * window[i], 0};
      square += history[i] * history[i];
    }
    for (unsigned i = 1, j = 0; i < size; i++) {
      unsigned bit = size >> 1;
      for (; j & bit; bit >>= 1)
        j ^= bit;
      j ^= bit;
      if (i < j)
        std::swap(bins[i], bins[j]);
    }
    for (unsigned length = 2; length <= size; length *= 2)
      for (unsigned base = 0; base < size; base += length)
        for (unsigned j = 0; j < length / 2; j++) {
          auto a = bins[base + j],
               b = bins[base + j + length / 2] * roots[j * size / length];
          bins[base + j] = a + b;
          bins[base + j + length / 2] = a - b;
        }
    Feature f;
    f.rms = float(std::sqrt(square / size));
    peak = std::max(peak, f.rms);
    for (unsigned b = 0; b < 24; b++) {
      double low = 40 * std::pow(400., b / 24.),
             high = 40 * std::pow(400., (b + 1) / 24.);
      unsigned begin = std::clamp(unsigned(std::lround(low * size / rate)), 1U,
                                  size / 2 - 1),
               end = std::clamp(unsigned(std::lround(high * size / rate)),
                                begin + 1, size / 2);
      float power = 0;
      for (unsigned k = begin; k < end; k++)
        power += std::norm(bins[k]);
      f.bands[b] = std::sqrt(power) * 2 / size;
      band_peak[b] = std::max(band_peak[b], f.bands[b]);
    }
    features.push_back(f);
    std::move(history.begin() + hop, history.end(), history.begin());
    read(size - hop, hop);
  }
  std::array<float, 24> smoothed{};
  float smooth_rms = 0, motion = 0;
  for (auto &f : features) {
    f.rms = std::min(1.f, f.rms / peak);
    smooth_rms += (f.rms > smooth_rms ? .25f : .1f) * (f.rms - smooth_rms);
    f.rms = smooth_rms;
    float flux = 0;
    for (unsigned b = 0; b < 24; b++) {
      // A shared noise floor prevents silent/near-silent bins from blooming.
      f.bands[b] = std::clamp(f.bands[b] / std::max(peak * .035f, band_peak[b]),
                              0.f, 1.f);
      float delta = std::max(0.f, f.bands[b] - previous[b]);
      f.band_hit[b] = delta; // Temporary raw novelty, resolved to events below.
      flux += delta;
      if (b < 7)
        f.low_flux += delta;
      if (b >= 16)
        f.high_flux += delta;
      previous[b] = f.bands[b];
      smoothed[b] +=
          (f.bands[b] > smoothed[b] ? .25f : .1f) * (f.bands[b] - smoothed[b]);
      f.bands[b] = smoothed[b];
    }
    for (unsigned b = 0; b < 6; b++)
      f.bass += f.bands[b] / 6;
    for (unsigned b = 17; b < 24; b++)
      f.treble += f.bands[b] / 7;
    for (unsigned b = 7; b < 16; b++)
      f.mids += f.bands[b] / 9;
    f.onset = std::min(1.f, flux * .7f);
    f.motion = motion;
    motion += float(hop) / rate * (.75f + .5f * f.rms + .15f * f.bass);
  }
  // Local-maximum spectral-flux events, with a 180ms refractory interval.
  // Persist their source-time age so a 12fps renderer cannot miss a 20ms
  // attack.
  auto events = [&](bool high) {
    float last = -100, strength = 0;
    unsigned count = 0;
    std::vector<float> fluxes;
    for (auto &f : features)
      fluxes.push_back(high ? f.high_flux : f.low_flux);
    auto sorted = fluxes;
    std::sort(sorted.begin(), sorted.end());
    float reference = std::max(.03f, sorted[sorted.size() * 95 / 100]);
    for (size_t i = 0; i < features.size(); i++) {
      float now = float(i * hop) / rate;
      size_t lo = i > 25 ? i - 25 : 0, hi = std::min(features.size(), i + 26);
      float mean = 0;
      for (size_t j = lo; j < hi; j++)
        mean += fluxes[j];
      mean /= hi - lo;
      if (i > 0 && i + 1 < features.size() && fluxes[i] >= fluxes[i - 1] &&
          fluxes[i] > fluxes[i + 1] && fluxes[i] > mean * 1.4f + .015f &&
          now - last > (high ? .24f : .32f)) {
        last = now;
        strength = std::clamp(fluxes[i] / reference, .45f, 1.f);
        count++;
      }
      auto &f = features[i];
      if (high) {
        f.treble_age = now - last;
        f.treble_hit = strength;
        f.treble_count = count;
      } else {
        f.bass_age = now - last;
        f.bass_hit = strength;
        f.bass_count = count;
      }
    }
  };
  events(false);
  events(true);
  // Independent note attacks prevent a fixed animation oscillator from making
  // all pitched strikers hit together. Local thresholds reject steady tones.
  for (unsigned b = 0; b < 24; ++b) {
    std::vector<float> fluxes;
    for (const auto &f : features) fluxes.push_back(f.band_hit[b]);
    auto sorted = fluxes;
    std::sort(sorted.begin(), sorted.end());
    float reference = std::max(.02f, sorted[sorted.size() * 95 / 100]);
    float last = -100, strength = 0;
    unsigned count = 0;
    for (size_t i = 0; i < features.size(); ++i) {
      float now = float(i * hop) / rate;
      size_t lo = i > 15 ? i - 15 : 0, hi = std::min(features.size(), i + 16);
      float mean = 0;
      for (size_t j = lo; j < hi; ++j) mean += fluxes[j];
      mean /= hi - lo;
      if (i && i + 1 < features.size() && fluxes[i] >= fluxes[i - 1] &&
          fluxes[i] > fluxes[i + 1] && fluxes[i] > mean * 1.5f + .012f &&
          now - last > .14f) {
        last = now;
        strength = std::clamp(fluxes[i] / reference, .25f, 1.f);
        ++count;
      }
      features[i].band_age[b] = now - last;
      features[i].band_hit[b] = strength;
      features[i].band_count[b] = count;
    }
  }
}
Feature Media::feature(double seconds) const {
  if (seconds < 0 || seconds >= duration() || features.empty())
    return {};
  size_t i = size_t(seconds * rate / std::max(1, rate / 50));
  return features[std::min(i, features.size() - 1)];
}
std::string caption(const Show &s, double t) {
  if (t < s.intro)
    return s.title + (s.artist.empty() ? "" : " / " + s.artist);
  std::string out = s.name;
  for (auto &c : s.cues)
    if (t - s.intro >= c.at && t - s.intro < c.at + c.duration &&
        (!c.text.empty() || !c.label.empty()))
      out = c.text.empty() ? c.label : c.text;
  return out;
}
namespace {
Frame effect(const Cue &scene, Feature a, double mt, double beat, double beat_age, const Media &media, const Rhythm &rhythm) {
  if ((fusion_style(scene.effect) || dance_style(scene.effect) || scene.effect == "adagio-shutters" || scene.effect == "adagio-prism") && scene.clock == "grid" && beat >= 0) {
    // The authored pulse controls attack timing, while measured audio energy
    // controls strength. Spectral subdivisions cannot spuriously move the beat.
    a.bass_age = float(beat_age);
    a.bass_hit = float(std::clamp(.65 + .35 * a.bass, 0., 1.));
  }
  Frame f{};
  const auto &style = scene.effect;
  // Attack clocks retain a visible, seek-safe movement after brief FFT events.
  if (scene.clock == "bass")
    beat = a.bass_count ? a.bass_count - std::exp(-std::max(0.f, a.bass_age) / .18) : 0;
  else if (scene.clock == "treble")
    beat = a.treble_count ? a.treble_count - std::exp(-std::max(0.f, a.treble_age) / .14) : 0;
  mt *= scene.speed;
  int choice = -1;
  if (style == "ribbon")
    choice = 0;
  else if (style == "ripple")
    choice = 1;
  else if (style == "embers")
    choice = 2;
  else if (style == "lanterns")
    choice = 3;
  else if (style == "ladder")
    choice = 4;
  else if (style == "daisy")
    choice = 5;
  if (fusion_style(style))
    f = fusion(a, beat * scene.speed, style);
  else if (lamour_style(style))
    f = lamour(media, rhythm, mt, style);
  else if (dance_style(style))
    f = dance(a, mt, style, beat * scene.speed);
  else if (adagio_style(style))
    f = adagio(a, mt, style, beat * scene.speed);
  else if (bells_style(style))
    f = bells(a, mt, style);
  else if (theatre_style(style))
    f = theatre(a, mt, style);
  else if (style == "music-ribbon" || style == "music-ripple" ||
           style == "music-lanterns" || style == "music-daisy") {
    // Preserve the original geometry; let measured attacks change its light.
    // Interpolate C-demo phases rather than adding independently moving shapes.
    // Motion follows a hit's attack/release instead of a free-running loop.
    double age = std::max(0.f, a.bass_age);
    double phase =
        ((a.bass_count + 1 - std::exp(-age / .1)) * 7 * (1 - scene.sustain) +
         a.motion * 22 * scene.sustain) *
        scene.speed;
    double fraction = phase - std::floor(phase);
    uint32_t tick = uint32_t(phase);
    // A short hold survives the 12fps UART cadence; near-dark troughs make
    // individual attacks legible. Event strength controls bloom width.
    double pulse =
        a.bass_count ? std::exp(-std::max(0., age - .055) / .085) : 0;
    double bass = (.65 + .35 * a.bass_hit) * pulse,
           high = a.treble_hit * std::exp(-a.treble_age / .1);
    double floor = .025 + scene.sustain * (.12 + .25 * a.rms);
    double gain = floor + (1 - floor) * pulse;
    int geometry = style == "music-ribbon"     ? 0
                   : style == "music-ripple"   ? 1
                   : style == "music-lanterns" ? 3
                                               : 5;
    for (unsigned tile = 0; tile < 5; tile++) {
      std::array<uint8_t, 64> after{};
      pwm_show_tile(f[tile].data(), tick, tile, 5, geometry);
      pwm_show_tile(after.data(), tick + 1, tile, 5, geometry);
      for (unsigned p = 0; p < 64; p++) {
        double shape =
            (f[tile][p] * (1 - fraction) + after[p] * fraction) / 100.;
        double glow = std::pow(shape, 1.7 - 1.05 * bass) * gain;
        glow += .08 * high * std::pow(shape, 3);
        if (style == "music-lanterns")
          glow *= .4 + .6 * std::sqrt(a.bands[std::min(23U, tile * 5 + 2)]);
        f[tile][p] = uint8_t(std::clamp(std::lround(glow * 100), 0L, 100L));
      }
    }
  } else if (style == "ribbons") {
    double bass = a.bass_hit * std::exp(-a.bass_age / .18),
           treble = a.treble_hit * std::exp(-a.treble_age / .13);
    for (unsigned y = 0; y < 8; y++)
      for (unsigned x = 0; x < 40; x++) {
        double phase = a.motion * 2.45;
        double centre = 3.5 +
                        (2.15 + .5 * a.mids) * std::sin(x * .196 + phase) +
                        .4 * a.mids * std::sin(x * .4 - phase * .6);
        double width = 1.15 + 1.25 * bass;
        double ribbon = std::max(0., 1 - std::abs(y - centre) / width);
        double glow = .55 + .45 * (.5 + .5 * std::sin(x * .17 - phase * 1.3));
        double other = 3.5 - 2.2 * std::sin(x * .196 + phase + 1.57);
        double thread = std::max(0., 1 - std::abs(y - other) / .8);
        double value =
            ribbon * glow * (.08 + .42 * std::sqrt(a.rms) + .5 * bass) +
            thread * (.04 + .7 * treble + .25 * a.treble);
        f[x / 8][y * 8 + x % 8] =
            uint8_t(std::clamp(std::lround(value * 100), 0L, 100L));
      }
  } else if (style == "choreography") {
    static const int scenes[] = {0, 1, 2, 5};
    unsigned scene = unsigned(mt / 18) % 4;
    double fade = std::clamp((std::fmod(mt, 18.) - 16) / 2, 0., 1.);
    uint32_t tick = uint32_t(a.motion * 25);
    for (unsigned tile = 0; tile < 5; tile++) {
      std::array<uint8_t, 64> next{};
      pwm_show_tile(f[tile].data(), tick, tile, 5, scenes[scene]);
      if (fade > 0)
        pwm_show_tile(next.data(), tick, tile, 5, scenes[(scene + 1) % 4]);
      auto base = f[tile];
      for (unsigned y = 0; y < 8; y++)
        for (unsigned x = 0; x < 8; x++) {
          double sy = std::clamp(3.5 + (y - 3.5) / (.8 + .8 * a.mids), 0., 7.);
          unsigned row = unsigned(sy), row2 = std::min(7U, row + 1);
          double fraction = sy - row;
          auto sample = [&](unsigned r) {
            return base[r * 8 + x] * (1 - fade) + next[r * 8 + x] * fade;
          };
          double shape = sample(row) * (1 - fraction) + sample(row2) * fraction;
          double beat = a.bass_hit * std::exp(-a.bass_age / .16);
          double gain = .12 + .3 * a.rms + .58 * beat;
          unsigned gx = tile * 8 + x;
          double centre = 19.5 + 8 * std::sin(a.bass_count * 2.39996);
          double radius = std::hypot((gx - centre), double(y - 3.5) * 2);
          double ring =
              std::exp(-std::pow((radius - a.bass_age * 55) / 1.6, 2)) *
              a.bass_hit * std::exp(-a.bass_age / .45) * 80;
          double tip = a.treble_age * 95;
          if (a.treble_count & 1)
            tip = 39 - tip;
          double behind = (a.treble_count & 1) ? gx - tip : tip - gx;
          double comet = behind >= 0 && behind < 9
                             ? std::pow(1 - behind / 9, 2) * a.treble_hit *
                                   std::exp(-std::pow(
                                       (y - (1.5 + 4 * a.treble)) / .8, 2)) *
                                   85
                             : 0;
          f[tile][y * 8 + x] = uint8_t(
              std::clamp(std::lround(shape * gain + ring + comet), 0L, 100L));
        }
    }
  } else if (style == "pwm" || choice >= 0) {
    for (unsigned i = 0; i < 5; i++)
      pwm_show_tile(f[i].data(), uint32_t(mt * 25), i, 5, choice);
  } else
    for (unsigned y = 0; y < 8; y++)
      for (unsigned x = 0; x < 40; x++) {
        double v = 0;
        if (style == "weird") {
          double u = (x - 19.5) / 8., v0 = (y - 3.5) / 3.;
          double bend = std::sin(u * 1.7 + mt * .37 + a.bass * 3) +
                        std::sin(v0 * 2.1 - mt * .61 + a.treble * 4);
          double px = u + .7 * std::sin(v0 * 2 + mt * .73) + bend * .23;
          double py = v0 + .6 * std::cos(u * .9 - mt * .47) - a.bass * .7;
          double radius = std::hypot(px, py), angle = std::atan2(py, px);
          double spiral = .5 + .5 * std::sin(radius * 7 - angle * 3 -
                                             mt * (1 + a.bass * 3) + bend * 2);
          unsigned band =
              std::min(23U, unsigned(std::clamp((px + 3.5) * 24 / 7, 0., 23.)));
          double energy = a.bands[band];
          double knots =
              std::pow(.5 + .5 * std::sin(px * 4 + std::sin(py * 4 + mt) +
                                          mt * 2 + energy * 5),
                       4);
          double veins = std::exp(
              -std::abs(std::sin(px * 2.3 - py * 3.1 + mt * .8 + bend)) * 9);
          double morph = .5 + .5 * std::sin(mt * .11);
          v = (spiral * spiral * (1 - morph) + knots * morph) *
                  (.08 + .85 * energy + .25 * a.rms) +
              veins * (.05 + .65 * a.bass) + a.onset * .25 * std::exp(-radius);
        } else if (style == "strings") {
          double energy = a.bands[std::min(23U, x * 24 / 40)];
          double arch = 3.5 + 2.3 * std::sin(mt * .5 + x * .12) +
                        energy * .6 * std::sin(mt + x * .4);
          double ribbon = std::exp(-std::pow((y - arch) / (.45 + a.rms), 2));
          double halo = std::exp(-std::pow((y - (7 - arch)) / 1.8, 2));
          double pulse = a.bass_hit * std::exp(-a.bass_age / .2);
          v = (ribbon * (.08 + .35 * a.rms + .4 * energy + .6 * pulse) +
               halo * a.bass * .4) *
              (0.7 + 0.3 * std::sin(x * .5 - mt * 2));
        } else if (style == "bars") {
          double band = a.bands[std::min(23U, x * 24 / 40)] *
                        (.65 + .35 * std::sin(mt * 1.9 + x * .2));
          v = (7 - y < band * 8) ? (.25 + .75 * band) : .01;
        } else {
          double dist = std::hypot((x - 19.5) * .35, (y - 3.5) * .8);
          double ripple = .5 + .5 * std::cos(dist * 2.1 - mt * 7);
          double chain = std::pow(std::max(0., std::cos(mt * 3 - x * .25)), 8);
          double energy = a.bands[std::min(23U, x * 24 / 40)];
          v = ripple * ripple * (.05 + .3 * a.rms + .6 * energy) +
              chain * (.2 + .6 * a.treble) + a.onset * std::exp(-dist * .5);
        }
        f[x / 8][y * 8 + x % 8] =
            uint8_t(std::clamp(std::lround(v * 100), 0L, 100L));
      }
  Frame out{};
  for (unsigned y = 0; y < 8; y++)
    for (unsigned x = 0; x < 40; x++) {
      unsigned sx = scene.variant & 1 ? 39 - x : x;
      unsigned sy = scene.variant & 2 ? 7 - y : y;
      out[x / 8][y * 8 + x % 8] =
          uint8_t(std::lround(f[sx / 8][sy * 8 + sx % 8] * scene.level));
    }
  return out;
}
Cue scene_at(const Show &s, double mt) {
  Cue scene;
  scene.effect = s.style;
  for (auto &c : s.cues)
    if (!c.effect.empty() && mt >= c.at && mt < c.at + c.duration)
      scene = c;
  return scene;
}
} // namespace
Frame render(const Show &s, const Media &m, double t) {
  Frame f{};
  if (t < 0)
    return f;
  if (t < s.intro) {
    text(f, s.title + (s.artist.empty() ? "" : "  " + s.artist), t / s.intro);
    return f;
  }
  double mt = t - s.intro;
  auto a = m.feature(mt);
  auto scene = scene_at(s, mt);
  double beat = s.rhythm.position(mt);
  double beat_age = std::max(0., mt - s.rhythm.time(std::floor(beat + 1e-7)));
  f = effect(scene, a, mt, beat, beat_age, m, s.rhythm);
  double duration = std::min(s.transition, scene.duration);
  if (duration > 0 && mt >= scene.at && mt < scene.at + duration) {
    auto previous = scene_at(s, scene.at - 1e-7);
    auto from = effect(previous, a, mt, beat, beat_age, m, s.rhythm);
    double mix = (mt - scene.at) / duration;
    mix = mix * mix * (3 - 2 * mix);
    for (unsigned tile = 0; tile < 5; tile++)
      for (unsigned p = 0; p < 64; p++)
        f[tile][p] =
            uint8_t(std::lround(from[tile][p] * (1 - mix) + f[tile][p] * mix));
  }
  for (auto &c : s.cues)
    if (mt >= c.at && mt < c.at + c.duration && !c.text.empty()) {
      for (auto &tile : f)
        for (auto &p : tile)
          p /= 5;
      text(f, c.text, (mt - c.at) / c.duration, 100, c.mode == "center");
    }
  double fade = std::clamp((m.duration() - mt) / 1.5, 0., 1.);
  for (auto &tile : f)
    for (auto &p : tile)
      p = s.output_gamma == 1 ? uint8_t(p * fade) : uint8_t(std::clamp(std::lround(100 * std::pow(p * fade / 100., s.output_gamma)), 0L, 100L));
  return f;
}
} // namespace letki
