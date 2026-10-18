#include "bells.hpp"
#include <algorithm>
#include <cmath>

namespace letki {
namespace {
double unit(double n) { return std::isfinite(n) ? std::clamp(n, 0., 1.) : 0.; }
double phase(double n) { return n - std::floor(n); }
double triangle(double n) { return 1 - std::abs(2 * phase(n) - 1); }
struct Canvas {
  Frame frame{};
  double gate = 0;
  void dot(int x, int y, double level) {
    if (x < 0 || x >= 40 || y < 0 || y >= 8) return;
    auto &p = frame[x / 8][y * 8 + x % 8];
    p = std::max(p, uint8_t(std::lround(100 * unit(level) * gate)));
  }
  void horizontal(int x, int end, int y, double level) {
    for (; x <= end; ++x) dot(x, y, level);
  }
  void vertical(int x, int y, int end, double level) {
    for (; y <= end; ++y) dot(x, y, level);
  }
};
double band(const Feature &f, unsigned n) { return unit(f.bands[n % 24]); }
double attack(float hit, float age) {
  return unit(hit) * std::exp(-std::max(0., double(age)) / .24);
}
void hammers(Canvas &c, const Feature &f, double) {
  // One pitched rack across all five tiles. Each bar owns its spectral bin;
  // strikers travel independently rather than following a global loudness flash.
  for (int n = 0; n < 10; ++n) {
    int x = n * 4, y = 3 + (n * 3 % 4);
    unsigned reg = 3 + n * 2;
    double e = band(f, reg), age = std::max(0., double(f.band_age[reg]));
    double hit = attack(f.band_hit[reg], f.band_age[reg]);
    // A short descent arrives 25 ms after the spectral attack; recovery takes
    // 180 ms. No oscillator can manufacture strikes between actual notes.
    double lift = age < .025 ? 1 - age / .025 : unit((age - .025) / .18);
    c.horizontal(x, x + 2, y, .035 + .7 * e + .25 * hit);
    c.horizontal(x, x + 2, y + 1, .02 + .3 * e);
    int head = y - 1 - int(lift * 2);
    c.dot(x + 1, head, .06 * e + .94 * hit);
    c.dot(x + 1, head - 1, .02 * e + .3 * hit);
  }
}
void gears(Canvas &c, const Feature &f, double) {
  // Three rectangular escapements mesh through opposed toothed racks. Their
  // open centres distinguish them from filled meters; there are no radial rings.
  const int starts[] = {0, 13, 28}, widths[] = {12, 14, 12};
  for (int n = 0; n < 3; ++n) {
    int x = starts[n], w = widths[n], top = n == 1 ? 2 : 1;
    double e = (band(f, n * 7 + 1) + band(f, n * 7 + 4)) * .5;
    unsigned count = n == 1 ? f.treble_count : f.bass_count;
    double hit = n == 1 ? attack(f.treble_hit, f.treble_age)
                        : attack(f.bass_hit, f.bass_age);
    double age = n == 1 ? f.treble_age : f.bass_age;
    int step = int(count % 3) + (hit > .01 ? int(unit(age / .24) * 2) : 2);
    c.horizontal(x + 1, x + w - 2, top + 1, .04 + .7 * e);
    c.horizontal(x + 1, x + w - 2, top + 4, .03 + .5 * e);
    c.vertical(x + 1, top + 1, top + 4, .1 + .6 * e);
    c.vertical(x + w - 2, top + 1, top + 4, .1 + .6 * e);
    for (int j = 1; j < w - 1; ++j) {
      if ((j + step) % 3 == 0) c.dot(x + j, top, .12 + .75 * e);
      if ((j - step + 12) % 3 == 0) c.dot(x + j, top + 5, .1 + .7 * e);
    }
    c.dot(x + 3 + int(count % unsigned(w - 6)), top + 2,
          .2 * e + .8 * hit);
  }
}
void weft(Canvas &c, const Feature &f, double) {
  // Straight shuttle tracks and vertical register pins. Alternating bridges
  // leave a dark pixel at crossings, making an orthogonal woven construction.
  for (int n = 0; n < 4; ++n) {
    int y = n * 2, start = n % 2 ? 3 : 0, end = 39 - (n * 3 % 7);
    double e = band(f, n * 5 + 2);
    unsigned reg = n * 5 + 2;
    double progress = unit(double(f.band_age[reg]) / .3);
    unsigned count = f.band_count[reg];
    int span = end - start - 1;
    int shuttle = start + int((count * 7 % unsigned(span) + progress * 6));
    if (shuttle > end - 2) shuttle -= span;
    for (int x = start; x <= end; ++x)
      if ((x + n * 2) % 9 != 4) c.dot(x, y, .025 + .35 * e);
    c.horizontal(shuttle, std::min(shuttle + 2, end), y,
                 .12 * e + .88 * attack(f.band_hit[reg], f.band_age[reg]));
    int pin = 4 + n * 9;
    c.vertical(pin, 1, 7, .025 + .6 * band(f, n * 5 + 4));
    c.dot(pin + 1, y + 1, .1 + .85 * e);
  }
}
void monoliths(Canvas &c, const Feature &f, double t) {
  const int x[] = {1, 7, 16, 23, 34}, widths[] = {3, 5, 2, 6, 4};
  for (int n = 0; n < 5; ++n) {
    double e = band(f, n * 4 + 2), breathing = triangle(t * .12 + n * .173);
    int top = 1 + int((1 - e) * 2 + breathing * 1.5);
    int bottom = std::min(7, top + 2 + n % 3);
    c.vertical(x[n] + widths[n] / 2, 0, top - 1, .02 + .18 * e);
    for (int dx = 0; dx < widths[n]; ++dx)
      for (int y = top; y <= bottom; ++y)
        c.dot(x[n] + dx, y, (.025 + .85 * e) *
              (dx == 0 ? 1 : .45 + .25 * breathing));
    c.horizontal(x[n], x[n] + widths[n] - 1, bottom, .04 + .65 * e);
  }
}
void strings(Canvas &c, const Feature &f, int left, int width, bool mirror,
             bool bass, bool mandolin, unsigned first) {
  auto dot = [&](int x, int y, double level) {
    c.dot(left + (mirror ? width - 1 - x : x), y, level);
  };
  int body = width == 20 ? 10 : (mandolin ? 18 : 22);
  // Contour only: the body interior and the two-pixel sound hole remain black.
  // The neck has two conceptual strings separated by three dark pixel rows.
  double body_level = .12 + .22 * band(f, first);
  for (int x = 2; x < body - 2; ++x) {
    dot(x, 0, body_level);
    dot(x, 7, body_level);
  }
  for (int y = 1; y < 7; ++y) {
    int inset = mandolin ? (y == 1 || y == 6 ? 1 : 0)
                        : (y == 3 || y == 4 ? 2 : 0);
    dot(1 + inset, y, body_level);
    dot(body - 2 - inset, y, body_level);
  }
  int hole = body / 2;
  for (int row = 0; row < (bass ? 2 : 3); ++row) {
    int y = row == 0 ? 2 : row == 1 ? 5 : 7;
    unsigned reg = first + row * (bass ? 2 : 3);
    double e = band(f, reg), hit = attack(f.band_hit[reg], f.band_age[reg]);
    int end = row == 2 ? body - 3 : width - 3;
    for (int x = 3; x <= end; ++x) {
      // A gap through every string makes the dark sound hole explicit even
      // with a concave brightness transform applied after rendering.
      if (x >= hole - 1 && x <= hole + 1) continue;
      dot(x, y, .025 + .32 * e);
    }
    int pluck = 3 + int(f.band_count[reg] % unsigned(std::max(1, body - 5)));
    if (pluck >= hole - 1 && pluck <= hole + 1) pluck = body - 3;
    dot(pluck, y, hit);
    if (row < 2) {
      int fret = body + int(f.band_count[reg] % unsigned(std::max(1, width - body - 3)));
      dot(fret, y, .12 * e + .85 * hit);
    }
  }
  // A sparse headstock terminates the long horizontal silhouette.
  dot(width - 2, 2, .16 + .35 * band(f, first));
  dot(width - 2, 5, .16 + .35 * band(f, first + 2));
  dot(width - 1, 1, .12);
  dot(width - 1, 6, .12);
}
} // namespace
bool bells_style(const std::string &s) {
  return s == "bells-hammers" || s == "bells-gears" ||
         s == "bells-weft" || s == "bells-monoliths" ||
         s == "bells-guitar" || s == "bells-bass" ||
         s == "bells-mandolin" || s == "bells-duet";
}
Frame bells(const Feature &f, double t, const std::string &s) {
  Canvas c;
  // Preserve silence and suppress the recording noise floor. This gate affects
  // visibility only: motion is a pure function of source time and feature data.
  c.gate = unit((double(f.rms) - .00015) / .00485);
  if (!std::isfinite(t)) return c.frame;
  // Current-register normalization retains the quiet opening without letting
  // late tutti peaks set every instrument's visibility for the entire track.
  Feature notes = f;
  double reference = .08;
  for (auto b : f.bands) reference = std::max(reference, unit(b));
  for (auto &b : notes.bands) b = float(unit(b / reference));
  if (s == "bells-hammers") hammers(c, notes, t);
  else if (s == "bells-gears") gears(c, notes, t);
  else if (s == "bells-weft") weft(c, notes, t);
  else if (s == "bells-monoliths") monoliths(c, notes, t);
  else if (s == "bells-guitar") strings(c, notes, 0, 40, false, false, false, 5);
  else if (s == "bells-bass") strings(c, notes, 0, 40, false, true, false, 1);
  else if (s == "bells-mandolin") strings(c, notes, 0, 40, false, false, true, 12);
  else if (s == "bells-duet") {
    strings(c, notes, 0, 20, false, false, false, 4);
    strings(c, notes, 20, 20, true, false, false, 14);
  }
  return c.frame;
}
} // namespace letki
