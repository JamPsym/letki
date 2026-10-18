#include "adagio.hpp"
#include <cassert>
#include <iostream>
#include <set>
using namespace letki;
static unsigned energy(const Frame &f) {
  unsigned sum = 0;
  for (auto &tile : f) for (auto v : tile) { assert(v <= 100); sum += v; }
  return sum;
}
int main() {
  Feature music;
  music.rms = .65; music.mids = .6; music.bass = .55; music.treble = .35;
  music.bass_hit = .9; music.bass_age = .04;
  music.treble_hit = .8; music.treble_age = .06;
  const char *styles[] = {"adagio-bows", "adagio-vault", "adagio-shutters", "adagio-prism"};
  std::set<Frame> distinct;
  for (auto style : styles) {
    assert(adagio_style(style));
    assert(energy(adagio({},10,style,21.25)) == 0);
    Feature quiet = music; quiet.rms = .007;
    assert(energy(adagio(quiet,10,style,21.25)) < 30);
    auto first = adagio(music,10,style,21.25);
    assert(energy(first) > 100);
    distinct.insert(first);
    std::set<Frame> phases;
    std::set<unsigned> pwm;
    for (unsigned k = 0; k < 64; ++k) {
      auto frame = adagio(music,10+k/12.,style,21.25+k*.147);
      phases.insert(frame);
      std::set<std::array<uint8_t,64>> tiles(frame.begin(),frame.end());
      assert(tiles.size() > 1);
      unsigned dark = 0;
      for (auto &tile : frame) for (auto v : tile) { pwm.insert(v); dark += v == 0; }
      assert(dark > 35);
    }
    assert(phases.size() > 20);
    assert(pwm.size() > 20);
    adagio(music,190,style,425.8);
    assert(first == adagio(music,10,style,21.25));
  }
  assert(distinct.size() == 4);
  Feature sustain = music;
  sustain.bass_hit = sustain.treble_hit = 0;
  sustain.bass_age = sustain.treble_age = 99;
  Feature noMids = sustain; noMids.mids = 0;
  for (auto style : {"adagio-bows","adagio-vault"})
    assert(energy(adagio(sustain,20,style,12)) > 2*energy(adagio(noMids,20,style,12)));
  Feature old = music; old.bass_age = 4;
  assert(energy(adagio(music,10,"adagio-shutters",21.25)) >
         2*energy(adagio(old,10,"adagio-shutters",21.25)));
  assert(!adagio_style("dance-steps"));
  assert(energy(adagio(music,10,"unknown",0)) == 0);
  std::cout << "adagio renderer passed\n";
}
