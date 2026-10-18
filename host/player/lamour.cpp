#include "lamour.hpp"
#include <algorithm>
#include <cmath>
namespace letki {
namespace {
double unit(double x) { return std::clamp(x, 0., 1.); }
double frac(double x) { return x - std::floor(x); }
struct Canvas {
  Frame f{};
  void dot(int x, int y, double light) {
    if (x < 0 || x >= 40 || y < 0 || y >= 8) return;
    auto &p = f[x / 8][y * 8 + x % 8];
    p = std::max(p, uint8_t(std::lround(100 * unit(light))));
  }
  void point(double x, double y, double light) {
    for (int iy = int(std::floor(y)); iy <= int(std::floor(y)) + 1; ++iy)
      for (int ix = int(std::floor(x)); ix <= int(std::floor(x)) + 1; ++ix)
        dot(ix, iy, light * (1 - std::abs(x - ix)) * (1 - std::abs(y - iy)));
  }
  void line(double x, double y, double xx, double yy, double light) {
    int n = std::max(1, int(std::ceil(std::hypot(xx - x, yy - y) * 3)));
    for (int i = 0; i <= n; ++i) point(x + (xx - x) * i / n, y + (yy - y) * i / n, light);
  }
};
// Register contour: eight half-beat samples are stable throughout each beat.
// This intentionally makes no claim to isolate the lead from the vocal/chords.
double register_height(const Feature &a) {
  unsigned peak = 8;
  for (unsigned i = 9; i <= 14; ++i) if (a.bands[i] > a.bands[peak]) peak = i;
  double weighted = 0, weight = 0;
  for (unsigned i = std::max(8U, peak - 1); i <= std::min(14U, peak + 1); ++i) {
    double w = std::pow(a.bands[i], 3);
    weighted += i * w; weight += w;
  }
  return weight > 1e-8 ? 5.7 - (weighted / weight - 8) * .78 : 3.4;
}
}
bool lamour_style(const std::string &s) {
  return s == "lamour-theme" || s == "lamour-wings" || s == "lamour-floor";
}
Frame lamour(const Media &media, const Rhythm &rhythm, double t, const std::string &style) {
  Canvas c;
  if (!std::isfinite(t) || t < 0 || t >= media.duration()) return c.f;
  auto a = media.feature(t);
  double gate = unit((a.rms - .006) / .12);
  if (gate == 0) return c.f;
  double beat = rhythm.position(t), phase = frac(beat);
  double age = std::max(0., t - rhythm.time(std::floor(beat)));
  // Grid timing with measured bass strength: the intro/break do not invent a kick.
  double kick = std::exp(-age / .115) * unit(a.bass * 2.5);
  double light = gate * (.22 + .35 * a.mids + .43 * kick);
  if (style == "lamour-theme") {
    double step = std::floor(beat * 2), previous = 0;
    for (int i = 0; i < 8; ++i) {
      double sample = std::min(t, rhythm.time((step - 7 + i) / 2));
      auto note = media.feature(sample);
      double y = register_height(note), x = 2.5 + i * 4.7;
      double energy = unit(note.mids * 2.5);
      if (sample >= 0 && energy > .01) {
        if (i && previous > 0) c.line(x - 4.7, previous, x, y, light * .34);
        double size = .6 + (i == 7 ? kick * .7 : 0);
        c.line(x - size, y, x, y - size, light * energy);
        c.line(x, y - size, x + size, y, light * energy);
        c.line(x + size, y, x, y + size, light * energy);
        c.line(x, y + size, x - size, y, light * energy);
      }
      previous = sample >= 0 ? y : 0;
    }
    // Four-beat footlights make the primary pulse unmistakable.
    int active = int(std::floor(beat)) % 4;
    if (active < 0) active += 4;
    for (int i = 0; i < 4; ++i)
      for (int x = i * 10 + 2; x < i * 10 + 8; ++x)
        c.dot(x, 7, gate * (i == active ? .16 + .84 * kick : .025));
  } else if (style == "lamour-wings") {
    double fold = .5 - .5 * std::cos(phase * 6.283185307179586);
    for (int side = 0; side < 2; ++side) {
      double center = side ? 28 : 11;
      double tip = .4 + 2.7 * fold, bottom = 6.7 - 1.3 * fold;
      double span = 5.5 + 1.5 * kick;
      double l = light * (.6 + .4 * unit(a.bands[side ? 13 : 9] * 2));
      for (int sign : {-1, 1}) {
        c.line(center, 3.7, center + sign * span, tip, l);
        c.line(center + sign * span, tip, center + sign * (span - 1), bottom, l * .65);
        c.line(center + sign * (span - 1), bottom, center, 3.7, l);
      }
      c.line(center, 2.7, center, 5.2, gate * (.35 + .65 * kick));
    }
    c.line(19, 4, 20, 4, gate * kick);
  } else if (style == "lamour-floor") {
    // Six interlocking chevrons across the complete canvas, not one per tile.
    for (int i = 0; i < 6; ++i) {
      double x = 2 + i * 7 - 2 * phase;
      bool up = (i + int(std::floor(beat))) % 2 == 0;
      double y = up ? 1 + kick : 6 - kick;
      double l = light * (.5 + .5 * unit(a.bands[7 + i] * 2));
      c.line(x - 2, up ? y + 2 : y - 2, x, y, l);
      c.line(x, y, x + 2, up ? y + 2 : y - 2, l);
      c.point(x, up ? y + 3 : y - 3, gate * kick);
    }
  }
  return c.f;
}
}
