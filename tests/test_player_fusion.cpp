#include "fusion.hpp"
#include <cassert>
#include <iostream>
#include <set>
using namespace letki;
unsigned light(const Frame &f) {
  unsigned n=0;
  for(auto &tile:f) for(auto p:tile) { assert(p<=100); n+=p; }
  return n;
}
int main() {
  Feature a; a.rms=.5; a.mids=.6; a.bass=.6;
  a.bands.fill(.6); a.bass_hit=1; a.bass_age=0;
  std::set<Frame> scenes;
  for(auto style:{"fusion-duet","fusion-ride","fusion-radio","fusion-drama","fusion-toast"}) {
    assert(fusion_style(style));
    assert(fusion({},4,style)==Frame{});
    assert(fusion(a,-1,style)==Frame{});
    auto f=fusion(a,4,style); scenes.insert(f);
    assert(light(f)>0 && f==fusion(a,4,style));
    auto settled=a; settled.bass_age=.5;
    assert(light(f)>light(fusion(settled,4.8,style))*1.35);
    unsigned dark=0; for(auto &tile:f) for(auto p:tile) dark+=p==0;
    assert(dark>90); // Preserve negative space under the bright output profile.
    assert(f[0]!=f[1] || f[1]!=f[2]);
  }
  assert(scenes.size()==5);
  assert(fusion(a,4,"fusion-duet")!=fusion(a,20,"fusion-duet")); // exchange hats
  auto settled=a; settled.bass_age=.6;
  assert(fusion(a,4,"fusion-ride")!=fusion(settled,4.8,"fusion-ride"));
  std::cout<<"Fusion: five distinct motifs, silence, beat contrast, seek and hat exchange passed\n";
}
