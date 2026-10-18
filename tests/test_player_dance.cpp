#include "dance.hpp"
#include <cassert>
#include <iostream>
#include <set>
using namespace letki;
static unsigned energy(const Frame &f) {
  unsigned n = 0;
  for (auto &tile : f) for (auto v : tile) { assert(v <= 100); n += v; }
  return n;
}
int main() {
  Feature active;
  active.rms = .65; active.mids = .55;
  active.bass_hit = .9; active.bass_age = .04;
  active.treble_hit = .8; active.treble_age = .06;
  const char *styles[] = {"dance-steps", "dance-accordion", "dance-clap", "dance-weave",
                          "dance-skirts", "dance-flowers"};
  std::set<Frame> distinct;
  for (auto style : styles) {
    assert(dance_style(style));
    assert(energy(dance({}, 10, style, 21.25)) == 0);
    Feature quiet = active; quiet.rms = .009;
    assert(energy(dance(quiet, 10, style, 21.25)) < 40);
    auto first = dance(active, 10, style, 21.25);
    assert(energy(first) > 100);
    assert(first == dance(active, 10, style, 21.25));
    distinct.insert(first);
    std::set<Frame> phases;
    std::set<unsigned> pwm;
    for (unsigned k = 0; k < 48; ++k) {
      auto frame = dance(active, 10 + k / 12., style, 21.25 + k * .147);
      phases.insert(frame);
      // A textile repeat matching tile width can accidentally clone all five
      // physical boards despite distinct frames over time. Check each phase.
      std::set<std::array<uint8_t, 64>> tile_shapes(frame.begin(), frame.end());
      assert(tile_shapes.size() > 1);
      for (auto &tile : frame) for (auto v : tile) pwm.insert(v);
    }
    assert(phases.size() > 12);
    assert(pwm.size() > 20);
    Feature old = active; old.bass_age = old.treble_age = 4;
    assert(energy(first) > 2 * energy(dance(old, 10, style, 21.25)));
    // Seek backward after unrelated future calls reproduces identical pixels.
    dance(active, 190, style, 425.8);
    assert(first == dance(active, 10, style, 21.25));
  }
  assert(distinct.size() == 6);
  assert(!dance_style("ripple"));
  assert(energy(dance(active, 10, "unknown", 0)) == 0);
  std::cout << "dance renderer passed\n";
}
