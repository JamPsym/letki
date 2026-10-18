#include "adagio.hpp"
#include <algorithm>
#include <cmath>

namespace letki {
namespace {
double clamp(double v) { return std::isfinite(v) ? std::clamp(v, 0., 1.) : 0; }
double fraction(double v) { return v - std::floor(v); }
double smooth(double v) { v = clamp(v); return v * v * (3 - 2 * v); }
double sway(double v) { return 1 - std::abs(2 * fraction(v) - 1); }
double hit(double strength, double age, double decay) {
  if (!std::isfinite(age) || age < 0) return 0;
  return clamp(strength) * std::exp(-std::max(0., age - .075) / decay);
}
struct Music {
  double gate, mid, high, low, kick, accent;
  explicit Music(const Feature &f)
      : gate(smooth((f.rms - .006) / .10)), mid(clamp(f.mids)),
        high(clamp(f.treble)), low(clamp(f.bass)),
        kick(hit(f.bass_hit, f.bass_age, .15)),
        accent(hit(f.treble_hit, f.treble_age, .18)) {}
};
struct Point { double x, y; };
double side(Point a, Point b, double x, double y) {
  return (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x);
}
// Subpixel area coverage gives moving broad facets smooth PWM edges. Levels
// remain perceptual percentages; hardware/profile gamma belongs to the caller.
struct Raster {
  double pixels[8][40]{};
  template<class Mask> void paint(Mask mask, double light) {
    light = clamp(light);
    for (int y = 0; y < 8; ++y)
      for (int x = 0; x < 40; ++x) {
        double area = 0;
        for (int sy = 0; sy < 4; ++sy)
          for (int sx = 0; sx < 4; ++sx)
            if (mask(x + (sx + .5) / 4, y + (sy + .5) / 4)) area += 1. / 16;
        pixels[y][x] = std::max(pixels[y][x], area * light);
      }
  }
  void rectangle(double x, double y, double w, double h, double light) {
    paint([=](double px, double py) {
      return px >= x && px < x + w && py >= y && py < y + h;
    }, light);
  }
  void triangle(Point a, Point b, Point c, double light) {
    paint([=](double x, double y) {
      double ab = side(a,b,x,y), bc = side(b,c,x,y), ca = side(c,a,x,y);
      return (ab >= 0 && bc >= 0 && ca >= 0) || (ab <= 0 && bc <= 0 && ca <= 0);
    }, light);
  }
  Frame finish(double gate) const {
    Frame result{};
    for (int y = 0; y < 8; ++y)
      for (int x = 0; x < 40; ++x)
        result[x / 8][y * 8 + x % 8] = uint8_t(std::lround(100 * clamp(pixels[y][x] * gate)));
    return result;
  }
};
void bows(Raster &r, const Music &m, double beat) {
  double phrase = smooth(sway(beat / 16));
  double contact = 5 + 30 * smooth(sway(beat / 8));
  for (int string = 0; string < 4; ++string) {
    double row = .85 + string * 1.85;
    double direction = string % 2 ? -1 : 1;
    double depth = direction * (.12 + .55 * m.mid) * (.35 + .65 * phrase);
    r.paint([=](double x, double y) {
      double span = x / 40;
      double curve = row + depth * 4 * span * (1 - span);
      return std::abs(y - curve) < .16 + .16 * m.mid;
    }, .12 + .63 * m.mid + .18 * m.accent);
    // The illuminated contact travels on a taut string, with a dark interval
    // on either side rather than a repeating waveform across every tile.
    r.paint([=](double x, double y) {
      double span = x / 40;
      double curve = row + depth * 4 * span * (1 - span);
      return std::abs(x - contact - string * .48) < 1.3 + m.mid &&
             std::abs(y - curve) < .38 + .22 * m.mid;
    }, .22 + .64 * m.mid + .2 * m.accent);
  }
  r.paint([=](double x, double y) {
    return y > .3 && y < 7.7 && std::abs(x - contact - (y - 4) * .65) < .32;
  }, .13 + .42 * m.mid);
}
void vault(Raster &r, const Music &m, double beat) {
  double phrase = smooth(sway(beat / 16));
  for (int arch = 0; arch < 3; ++arch) {
    double half = 17.8 - arch * 4.7 + phrase * (.4 + arch * .2);
    double center = 20 + (arch - 1) * .9;
    double apex = .25 + arch * .55 + .45 * (1 - phrase);
    double shoulder = 4.3 + arch * .3;
    r.paint([=](double x, double y) {
      double u = std::abs(x - center) / half;
      if (u > 1.04) return false;
      // Pointed roof rises to a sharp central apex; tall side piers anchor it.
      double roof = apex + (shoulder - apex) * std::pow(u, .72);
      bool rib = std::abs(y - roof) < .25 + .16 * m.mid;
      bool pier = std::abs(std::abs(x - center) - half) < .38 && y >= shoulder && y < 8;
      return rib || pier;
    }, .12 + m.mid * (.67 - arch * .1) + m.high * .12 + m.accent * .13);
  }
  // A central lancet opens with sustained strings; no kick is fabricated.
  double width = .55 + 1.5 * m.mid + .45 * phrase;
  r.paint([=](double x, double y) {
    double dx = std::abs(x - 20);
    return y > 2.4 + dx * 1.7 && y < 7.7 && dx < width;
  }, .08 + .43 * m.mid);
}
void shutters(Raster &r, const Music &m, double beat) {
  // Seven gates deliberately avoid the eight-pixel tile cadence. Alternating
  // upper/lower leaves open a central dark channel, then strike on each kick.
  for (int gate = 0; gate < 7; ++gate) {
    double phase = smooth(sway(beat / 2 + gate * .16));
    double height = .55 + 2.8 * phase + 2.8 * m.kick;
    double left = gate * 5.8 + .35;
    double y = gate % 2 ? 8 - height : 0;
    r.rectangle(left, y, 4.45, height,
                .08 + .22 * m.low + .18 * m.mid + .52 * m.kick + .09 * phase);
    r.rectangle(left + .45, gate % 2 ? y : height - .6, 3.55, .6,
                .12 + .3 * m.mid + .58 * m.kick + .16 * m.accent);
  }
}
void prism(Raster &r, const Music &m, double beat) {
  double opening = smooth(sway(beat / 8));
  double split = 1 + 6 * opening + 1.5 * m.kick;
  double center = 19 + 1.5 * smooth(sway(beat / 16));
  double left = center - split, right = center + split;
  double body = .10 + .4 * m.mid + .35 * m.kick;
  // Four large triangular planes split away from a narrow axial seam. Dark
  // gaps remain between planes; treble lights the opposing upper facets.
  r.triangle({1.0,1.0},{left,3.65},{left-3.0,7.5},body);
  r.triangle({2.0,.25},{left-2.0,.65},{left,3.25},body*.65+.28*m.accent);
  r.triangle({right,4.35},{38.8,7.4},{right+3.2,.7},body*.88+.1*m.high);
  r.triangle({right,4.75},{right+2.5,7.7},{37.8,7.8},body*.6+.32*m.accent);
  r.rectangle(center-.3,1.6, .6,4.8,.15+.5*m.mid+.3*m.kick);
}
} // namespace
bool adagio_style(const std::string &s) {
  return s == "adagio-bows" || s == "adagio-vault" ||
         s == "adagio-shutters" || s == "adagio-prism";
}
Frame adagio(const Feature &f, double sourceSeconds, const std::string &s,
             double beatPosition) {
  if (!adagio_style(s) || !std::isfinite(sourceSeconds) ||
      !std::isfinite(beatPosition) || !std::isfinite(f.rms)) return {};
  Music m(f);
  if (m.gate == 0) return {};
  Raster r;
  if (s == "adagio-bows") bows(r,m,beatPosition);
  else if (s == "adagio-vault") vault(r,m,beatPosition);
  else if (s == "adagio-shutters") shutters(r,m,beatPosition);
  else prism(r,m,beatPosition);
  return r.finish(m.gate);
}
} // namespace letki
