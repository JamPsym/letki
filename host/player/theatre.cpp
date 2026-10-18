#include "player.hpp"
#include <algorithm>
#include <cmath>
namespace letki {
namespace {
struct Canvas {
  Frame pixels{};
  void dot(int x, int y, double value) {
    if (x >= 0 && x < 40 && y >= 0 && y < 8) {
      auto &p = pixels[x / 8][y * 8 + x % 8];
      p = std::max(p, uint8_t(std::clamp(std::lround(value), 0L, 100L)));
    }
  }
  void line(int x0, int y0, int x1, int y1, double value) {
    int dx = std::abs(x1 - x0), dy = -std::abs(y1 - y0), sx = x0 < x1 ? 1 : -1,
        sy = y0 < y1 ? 1 : -1, err = dx + dy;
    for (;;) {
      dot(x0, y0, value);
      if (x0 == x1 && y0 == y1)
        break;
      int e = 2 * err;
      if (e >= dy) {
        err += dy;
        x0 += sx;
      }
      if (e <= dx) {
        err += dx;
        y0 += sy;
      }
    }
  }
};
double band(const Feature &f, unsigned n) {
  return std::clamp(double(f.bands[std::min(23U, n)]), 0., 1.);
}
void keyboard(Canvas &c, const Feature &f) {
  // One continuous keyboard, with spectral regions assigned to different keys.
  for (unsigned k = 0; k < 20; k++) {
    double note = std::pow(band(f, k + 2), 1.4), level = 4 + 96 * note;
    int x = k * 2;
    bool black =
        (k % 7 == 0 || k % 7 == 1 || k % 7 == 3 || k % 7 == 4 || k % 7 == 5);
    for (int y = 3; y < 7; y++) {
      c.dot(x, y, level);
      c.dot(x + 1, y, y == 6 ? level : level * .55);
    }
    if (black) {
      c.dot(x + 1, 1, 6 + note * 65);
      c.dot(x + 1, 2, 6 + note * 65);
    }
    // A short hammer dips toward an excited key.
    if (note > .5)
      c.dot(x, 1 + int(note * 2), 100 * note);
  }
  c.line(0, 7, 39, 7, 25 + 50 * f.rms);
}
void organ(Canvas &c, const Feature &f) {
  c.line(0, 7, 39, 7, 35);
  for (unsigned n = 0; n < 13; n++) {
    int x = 1 + n * 3, height = 3 + int(3 * (1 - std::abs(int(n) - 6) / 6.));
    double energy = band(f, n + 1), glow = 12 + 88 * energy;
    int top = 7 - height;
    c.line(x, top, x, 6, glow);
    c.line(x + 1, top, x + 1, 6, glow * .6);
    c.dot(x, top, 60 + 40 * energy);
    c.dot(x + 1, top, 60 + 40 * energy);
    c.dot(x, 6, 20 + 80 * std::pow(energy, .5));
    if (energy > .65)
      c.dot(x, top - 1, (energy - .65) * 200);
  }
}
void mallets(Canvas &c, const Feature &f) {
  unsigned hot = unsigned(std::max_element(f.bands.begin() + 8, f.bands.end()) -
                          f.bands.begin());
  for (unsigned n = 0; n < 8; n++) {
    int x = n * 5, y = n & 1 ? 4 : 2;
    double energy = band(f, n * 2 + 7);
    for (int dx = 0; dx < 4; dx++) {
      c.dot(x + dx, y, 15 + 85 * energy);
      c.dot(x + dx, y + 1, 10 + 65 * energy);
    }
    if (hot / 2 == n + 3 || hot / 2 == n + 4) {
      double attack = f.treble_hit * std::exp(-f.treble_age / .18);
      c.dot(x + 1, y - 1, 100 * attack);
      c.dot(x + 1, y - 2, 60 * attack);
    }
  }
  c.line(0, 7, 39, 7, 12);
}
void guitar(Canvas &c, const Feature &f, double t, int left, int width,
            bool reverse, bool bass, bool mandolin, double speed) {
  auto point = [&](int x, int y, double level) {
    c.dot(left + (reverse ? width - 1 - x : x), y, level);
  };
  // A body, sound hole, long neck/frets and visibly plucked strings.
  for (int y = 0; y < 8; y++)
    for (int x = 0; x < 9; x++) {
      double dx = (x - 4.) / (mandolin ? 3.7 : 3.2), dy = (y - 3.5) / 3.4;
      bool body = mandolin ? dx * dx + dy * dy < 1
                           : ((dx * dx + dy * dy < 1) &&
                              !(std::abs(y - 3.5) < 1 && x < 2));
      if (body)
        point(x, y, 18 + 22 * f.rms);
    }
  for (int x = 9; x < width; x++) {
    point(x, 1, 12);
    point(x, 6, 12);
  }
  for (int x = 12; x < width; x += 4)
    for (int y = 2; y < 6; y++)
      point(x, y, 8);
  unsigned strings = bass ? 4 : 6;
  for (unsigned s = 0; s < strings; s++) {
    double energy = band(f, (bass ? 1 : 6) + s * 2), amplitude = energy * .85;
    for (int x = 3; x < width; x++) {
      double wave = std::sin((x - 3.) / (width - 3) * 3.141592653589793) *
                    std::sin(t * speed * (s + 2)) * amplitude;
      double row = (bass ? 2. : 1.) + s + wave;
      int y = int(std::floor(row));
      double mix = row - y;
      point(x, y, (8 + 92 * energy) * (1 - mix));
      point(x, y + 1, (8 + 92 * energy) * mix);
    }
  }
  // Dark hole is cut after the strings so the body remains identifiable.
  for (int y = 3; y <= 4; y++)
    for (int x = 4; x <= 5; x++) {
      int gx = left + (reverse ? width - 1 - x : x);
      if (gx >= 0 && gx < 40)
        c.pixels[gx / 8][y * 8 + gx % 8] = 0;
    }
  unsigned fret =
      unsigned(std::max_element(f.bands.begin() + 5, f.bands.begin() + 18) -
               f.bands.begin());
  point(10 + int(fret % (width - 11)), 0, 25 + 75 * f.mids);
}
void bells(Canvas &c, const Feature &f, double t) {
  static const int positions[] = {2, 8, 14, 20, 26, 32, 38},
                   lengths[] = {4, 6, 5, 7, 4, 6, 5};
  c.line(0, 0, 39, 0, 30);
  for (unsigned n = 0; n < 7; n++) {
    double energy = band(f, 5 + n * 2),
           hit = f.treble_hit * std::exp(-f.treble_age / .45);
    double swing = (int(f.treble_count % 7) == int(n) ? hit : energy * .25) *
                   std::sin(t * 10 + n) * 1.1;
    int end = positions[n] + int(std::lround(swing));
    c.line(positions[n], 1, end, lengths[n], 15 + 70 * energy);
    c.line(positions[n] + 1, 1, end + 1, lengths[n], 8 + 45 * energy);
    c.dot(end, lengths[n], 25 + 75 * energy);
    if (int(f.treble_count % 7) == int(n))
      c.dot(end, lengths[n], 100 * hit);
  }
}
} // namespace
bool theatre_style(const std::string &s) {
  return s == "piano" || s == "organ" || s == "mallets" || s == "bass-guitar" ||
         s == "guitar" || s == "guitar-fast" || s == "guitar-duo" ||
         s == "mandolin" || s == "tubular-bells";
}
Frame theatre(const Feature &source, double t, const std::string &style) {
  // A quiet instrument still needs visible note-to-note contrast. Global
  // full-track normalization alone buries the opening piano under its later
  // tutti. Keep a noise floor instead of amplifying silence.
  auto f = source;
  float reference =
      std::max(.08f, *std::max_element(f.bands.begin(), f.bands.end()));
  float gate = std::clamp(f.rms / .005f, 0.f, 1.f);
  for (auto &b : f.bands)
    b = std::clamp(b / reference * gate, 0.f, 1.f);
  Canvas c;
  if (style == "piano")
    keyboard(c, f);
  else if (style == "organ")
    organ(c, f);
  else if (style == "mallets")
    mallets(c, f);
  else if (style == "tubular-bells")
    bells(c, f, t);
  else if (style == "guitar-duo") {
    guitar(c, f, t, 0, 20, false, false, false, 12);
    guitar(c, f, t + .4, 20, 20, true, false, false, 15);
  } else
    guitar(c, f, t, 0, 40, false, style == "bass-guitar", style == "mandolin",
           style == "guitar-fast" ? 24 : 12);
  return c.pixels;
}
} // namespace letki
