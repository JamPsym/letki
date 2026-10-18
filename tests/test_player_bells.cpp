#include "bells.hpp"
#include <cassert>
#include <iostream>
#include <set>

using namespace letki;
static unsigned energy(const Frame &frame) {
  unsigned sum = 0;
  for (const auto &tile : frame) for (auto pixel : tile) {
    assert(pixel <= 100);
    sum += pixel;
  }
  return sum;
}
int main() {
  Feature quiet, full;
  full.rms = .1;
  full.bands.fill(.7);
  full.bass_hit = full.treble_hit = 1;
  full.bass_age = full.treble_age = .02;
  full.band_hit.fill(1);
  full.band_age.fill(.02);
  std::set<Frame> unique;
  for (const auto &s : {"bells-hammers", "bells-gears", "bells-weft", "bells-monoliths"}) {
    assert(bells_style(s));
    assert(energy(bells(quiet, 2, s)) == 0);
    auto frame = bells(full, 2, s);
    assert(energy(frame) > 0);
    unique.insert(frame);
    bool moves = false;
    for (double t : {2.1, 2.4, 3., 5.7, 8.})
      moves |= frame != bells(full, t, s);
    if (std::string(s) == "bells-monoliths") assert(moves);
    else assert(!moves); // Mechanical notes follow audio events, not free time.
    // Backward seeks reproduce exactly the same source-time image.
    assert(frame == bells(full, 2, s));
    bool tiles_differ = false;
    for (int n = 1; n < 5; ++n) tiles_differ |= frame[n] != frame[0];
    assert(tiles_differ);
    Feature low, high;
    low.rms = high.rms = .1;
    low.bands[3] = low.bands[1] = low.bands[2] = 1;
    high.bands[17] = high.bands[18] = high.bands[19] = 1;
    assert(bells(low, 2, s) != bells(high, 2, s));
    Feature gated = full;
    gated.rms = 0;
    assert(energy(bells(gated, 2, s)) == 0);
    assert(energy(bells(full, 5.7, s)) > 0);
    Feature opening = full;
    opening.rms = .003;
    opening.bands.fill(.025);
    assert(energy(bells(opening, 2, s)) > 100);
  }
  assert(unique.size() == 4);
  assert(!bells_style("tubular-bells"));
  assert(energy(bells(full, 1, "unknown")) == 0);
  Feature event = full;
  ++event.bass_count;
  ++event.treble_count;
  assert(bells(event, 2, "bells-gears") != bells(full, 2, "bells-gears"));
  Feature note = full;
  note.band_age[3] = .3;
  auto before = bells(full, 2, "bells-hammers");
  auto after = bells(note, 2, "bells-hammers");
  assert(before != after);
  // The first register changes only its own three-column bar/striker.
  for (int x = 4; x < 40; ++x) for (int y = 0; y < 8; ++y)
    assert(before[x / 8][y * 8 + x % 8] == after[x / 8][y * 8 + x % 8]);
  assert(after == bells(note, 90, "bells-hammers"));
  assert(before == bells(full, 1, "bells-hammers"));
  Feature shuttle = full;
  ++shuttle.band_count[2];
  assert(bells(shuttle, 2, "bells-weft") != bells(full, 2, "bells-weft"));
  std::set<Frame> instruments;
  for (const auto &style : {"bells-guitar", "bells-bass", "bells-mandolin", "bells-duet"}) {
    assert(bells_style(style));
    assert(energy(bells(quiet, 2, style)) == 0);
    auto frame = bells(full, 2, style);
    instruments.insert(frame);
    unsigned lit = 0;
    for (const auto &tile : frame) for (auto p : tile) lit += p != 0;
    assert(lit > 30 && lit < 150); // Majority stays truly black after any gamma.
    assert(frame == bells(full, 90, style));
    Feature decayed = full;
    decayed.band_age.fill(2);
    assert(frame != bells(decayed, 2, style));
  }
  assert(instruments.size() == 4);
  Feature right = full;
  right.band_age[14] = 2;
  auto duet = bells(full, 2, "bells-duet");
  auto changed = bells(right, 2, "bells-duet");
  assert(duet != changed);
  for (int x = 0; x < 20; ++x) for (int y = 0; y < 8; ++y)
    assert(duet[x / 8][y * 8 + x % 8] == changed[x / 8][y * 8 + x % 8]);
  std::cout << "Player bells tests passed\n";
}
