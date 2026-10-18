#include "dance.hpp"
#include <algorithm>
#include <cmath>

namespace letki {
namespace {
double unit(double v) { return std::clamp(v, 0., 1.); }
double fract(double v) { return v - std::floor(v); }
double ease(double v) { v = unit(v); return v * v * (3 - 2 * v); }
double triangle(double v) { return 1 - std::abs(2 * fract(v) - 1); }
double attack(float strength, float age, double release) {
  if (!std::isfinite(age) || age < 0) return 0;
  // Hold through at least one 12fps frame, then release in source time.
  return unit(strength) * std::exp(-std::max(0., double(age) - .085) / release);
}
struct Light {
  double gate, body, bass, treble;
  explicit Light(const Feature &f)
      : gate(ease((f.rms - .008) / .105)),
        body(unit(.30 + .42 * f.rms + .28 * f.mids)),
        bass(attack(f.bass_hit, f.bass_age, .16)),
        treble(attack(f.treble_hit, f.treble_age, .12)) {}
};
// Area-sampled geometry preserves broad silhouettes while edges traverse LEDs.
// All primitives use display coordinates, independently of the five tile seams.
struct Canvas {
  double pixels[8][40]{};
  template<class Mask> void shape(Mask mask, double level) {
    if (level <= 0) return;
    for (int y = 0; y < 8; ++y)
      for (int x = 0; x < 40; ++x) {
        double coverage = 0;
        for (int sy = 0; sy < 5; ++sy)
          for (int sx = 0; sx < 5; ++sx)
            coverage += mask(x + (sx + .5) / 5., y + (sy + .5) / 5.) ? 1. / 25 : 0;
        pixels[y][x] = std::max(pixels[y][x], level * coverage);
      }
  }
  void box(double x, double y, double w, double h, double level) {
    shape([=](double px, double py) {
      return px >= x && px < x + w && py >= y && py < y + h;
    }, level);
  }
  Frame frame(double gate) const {
    Frame f{};
    for (int y = 0; y < 8; ++y)
      for (int x = 0; x < 40; ++x)
        f[x / 8][y * 8 + x % 8] = uint8_t(std::lround(100 * unit(pixels[y][x] * gate)));
    return f;
  }
};
void steps(Canvas &c, const Light &a, double beat) {
  // Five pairs march through the entire strip over twenty beats. The upper
  // and lower feet alternate planting; a bright toe identifies each footprint.
  double travel = beat * 2.65;
  for (int pair = 0; pair < 5; ++pair) {
    double phase = beat + pair * .37;
    for (int foot = 0; foot < 2; ++foot) {
      double p = fract(phase * .5 + foot * .5);
      double swing = ease(unit((p - .18) / .64));
      double x = fract((pair * 10.6 + travel + 2.6 * swing) / 53.) * 53. - 6;
      double lift = triangle(p) * .7;
      double y = foot ? 4.35 - lift : .6 + lift;
      double level = a.body * (.54 + .25 * (1 - triangle(p))) + .28 * a.bass;
      c.box(x, y, 4.1, 2.25, level);
      c.box(x + 2.8, y + .25, 1.65, 1.75, level + .22 * a.treble);
      c.box(x - .55, y + .55, .65, 1.1, .18 + .58 * a.bass);
    }
  }
}
void accordion(Canvas &c, const Light &a, double beat) {
  // A single instrument, rather than one icon per tile: broad end boxes and
  // nine articulated pleats. Four-beat breathing leaves the folds readable.
  double open = ease(triangle(beat / 4));
  double width = 12 + 17 * open + 1.4 * a.bass;
  double left = 20 - width / 2, right = 20 + width / 2;
  c.box(left - 4.5, .7, 4.5, 6.6, a.body * .8 + .18 * a.bass);
  c.box(right, .7, 4.5, 6.6, a.body * .7 + .28 * a.treble);
  for (int i = 0; i < 9; ++i) {
    double x = left + width * (i + .5) / 9.;
    double slant = (i % 2 ? 1 : -1) * (.65 + open * .55);
    double level = a.body * (i % 2 ? .5 : .8) + .28 * a.bass;
    c.shape([=](double px, double py) {
      return py > 1.1 && py < 6.9 && std::abs(px - x - slant * (py - 4) / 3) < .55 + width / 90;
    }, level);
  }
  for (int i = 0; i < 5; ++i)
    c.box(right + .9, 1.1 + i * 1.15, 2.6, .65,
          a.body * .45 + a.treble * (.35 + .08 * i));
}
void clap(Canvas &c, const Light &a, double beat) {
  // Alternating broad palms converge at three unequal meeting points, then
  // open again. Flat wrists and stepped fingers read as opposing groups.
  double p = fract(beat);
  for (int group = 0; group < 3; ++group) {
    double center = 6.5 + group * 13.5;
    double delay = group == 1 ? .5 : 0;
    double close = 1 - ease(triangle(p + delay));
    double gap = .3 + 3.6 * (1 - close);
    double y = group == 1 ? 1.8 : 2.5;
    for (int side : {-1, 1}) {
      double palm = center + side * (gap + 1.8);
      c.box(palm - 1.65, y, 3.3, 3.1, a.body * .78 + .28 * a.bass);
      c.box(palm + side * 1.8 - 1.2, y + .65, 2.4, 1.8, a.body * .48);
      c.box(center + side * gap - .5, y - .65, 1., 3.9,
            a.body * .55 + .42 * a.treble * close);
    }
    c.box(center - .55, .35, 1.1, 1.0, a.treble * close);
    c.box(center - 1.0, 6.7, 2., .7, a.bass * close);
  }
}
void weave(Canvas &c, const Light &a, double beat) {
  // Straight warp/weft diagonals cross as an embroidered diamond lattice.
  // The over/under ordering alternates at crossings; no sinusoidal ribbons.
  double offset = 2.4 * ease(triangle(beat / 4));
  for (int direction : {-1, 1})
    for (int thread = -2; thread < 8; ++thread) {
      double origin = thread * 10.5 + (direction > 0 ? offset : 5.25 - offset);
      double level = a.body * (direction > 0 ? .82 : .55) +
                     (direction > 0 ? a.bass * .25 : a.treble * .4);
      c.shape([=](double x, double y) {
        double d = x - origin - direction * (y - 4);
        if (std::abs(d) > 1.05) return false;
        int crossing = int(std::floor((x + y) / 4));
        return direction > 0 || crossing % 2 == 0 || std::abs(d) < .38;
      }, level);
    }
  // Small rectangular selvage stitches accent the two independent registers.
  for (int i = 0; i < 10; ++i) {
    c.box(i * 4. + fract(beat / 8) * 2, .1, 1.4, .55, a.treble * .75);
    c.box(i * 4. + 1, 7.3, 2.2, .55, a.bass * .75);
  }
}
void skirts(Canvas &c, const Light &a, double beat) {
  // Three full skirt silhouettes: narrow waists, broad scalloped hems, and
  // contrasting pleats. Each dancer turns at a different part of the phrase.
  const double centers[] = {6.1, 20.0, 33.7};
  for (int dancer = 0; dancer < 3; ++dancer) {
    double phase = beat / 4 + dancer * .21;
    double sway = 2 * ease(triangle(phase)) - 1;
    double turn = ease(triangle(phase + .25));
    double width = 3.4 + 1.7 * turn + .45 * a.bass;
    double cx = centers[dancer] + .8 * sway;
    double lean = .7 * sway;
    auto inside = [=](double x, double y) {
      double depth = (y - 1.4) / 5.9;
      if (depth < 0 || depth > 1) return false;
      double local = x - cx - lean * depth;
      double half = .9 + (width - .9) * depth;
      // Three broad hem lobes keep the bottom from reading as a solid bar.
      double hem = 7.3 - .35 * std::abs(std::sin(local * 1.25));
      return std::abs(local) < half && y < hem;
    };
    c.shape(inside, a.body * .53 + .22 * a.bass);
    for (int pleat = -1; pleat <= 1; ++pleat) {
      c.shape([=](double x, double y) {
        if (!inside(x, y)) return false;
        double depth = (y - 1.4) / 5.9;
        double line = cx + lean * depth + pleat * width * .57 * depth;
        return std::abs(x - line) < .24 + .22 * depth;
      }, a.body * .82 + .34 * a.treble);
    }
    c.box(cx - 1.05, .6, 2.1, .85, a.body * .65 + .4 * a.bass);
  }
}
void flowers(Canvas &c, const Light &a, double beat) {
  // Three embroidered four-petal blossoms, separated by dark fabric. Petals
  // grow out from the bright diamond centers, rather than forming rings.
  const double centers[] = {6.2, 19.8, 33.3};
  for (int flower = 0; flower < 3; ++flower) {
    double opening = ease(triangle(beat / 4 + flower * .23));
    double bloom = .64 + .32 * opening + .12 * a.bass;
    double cx = centers[flower] + .3 * (2 * opening - 1);
    double cy = flower == 1 ? 3.1 : 3.65;
    for (int petal = 0; petal < 4; ++petal) {
      double angle = petal * 1.5707963267948966 + .17 * (2 * opening - 1);
      double dx = std::cos(angle), dy = std::sin(angle);
      double reach = (petal % 2 ? 1.85 : 2.65) * bloom;
      double length = (petal % 2 ? 1.45 : 1.85) * bloom;
      double breadth = (petal % 2 ? 1.3 : 1.15) * bloom;
      c.shape([=](double x, double y) {
        double px = x - cx, py = y - cy;
        double along = (px * dx + py * dy - reach) / length;
        double across = (-px * dy + py * dx) / breadth;
        return along * along + across * across < 1;
      }, a.body * (petal % 2 ? .65 : .82) + .3 * a.treble);
    }
    c.shape([=](double x, double y) {
      return std::abs(x - cx) / 1.15 + std::abs(y - cy) / .95 < 1;
    }, a.body * .9 + .42 * a.bass);
    // Two small leaf stitches under each blossom retain a textile character.
    for (int side : {-1, 1})
      c.shape([=](double x, double y) {
        double px = x - cx - side * 3.8, py = y - 6.7;
        return std::abs(px + side * py) / 1.2 + std::abs(py) / .6 < 1;
      }, a.body * .4 + .25 * a.bass);
  }
}

} // namespace
bool dance_style(const std::string &style) {
  return style == "dance-steps" || style == "dance-accordion" ||
         style == "dance-clap" || style == "dance-weave" ||
         style == "dance-skirts" || style == "dance-flowers";
}
Frame dance(const Feature &f, double sourceSeconds, const std::string &style,
            double beatPosition) {
  if (!dance_style(style) || !std::isfinite(sourceSeconds) ||
      !std::isfinite(beatPosition) || !std::isfinite(f.rms)) return {};
  Canvas c;
  Light a(f);
  if (a.gate == 0) return {};
  if (style == "dance-steps") steps(c, a, beatPosition);
  else if (style == "dance-accordion") accordion(c, a, beatPosition);
  else if (style == "dance-clap") clap(c, a, beatPosition);
  else if (style == "dance-weave") weave(c, a, beatPosition);
  else if (style == "dance-skirts") skirts(c, a, beatPosition);
  else flowers(c, a, beatPosition);
  // Keep a visible silhouette, with a much wider dynamic range on attacks.
  double accent = .32 + .68 * std::max(a.bass, .7 * a.treble);
  return c.frame(a.gate * accent);
}
} // namespace letki
