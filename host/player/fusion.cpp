#include "fusion.hpp"
#include <algorithm>
#include <cmath>
namespace letki {
namespace {
double unit(double v) { return std::isfinite(v) ? std::clamp(v, 0., 1.) : 0; }
struct Stage {
  Frame frame{};
  double gain;
  explicit Stage(double g) : gain(g) {}
  void dot(int x, int y, double light) {
    if (x < 0 || x > 39 || y < 0 || y > 7) return;
    auto &p = frame[x / 8][y * 8 + x % 8];
    p = std::max(p, uint8_t(std::lround(100 * unit(light * gain))));
  }
  void point(double x, double y, double l) {
    int xx = int(std::floor(x)), yy = int(std::floor(y));
    for (int j = yy; j <= yy + 1; ++j) for (int i = xx; i <= xx + 1; ++i)
      dot(i, j, l * (1 - std::abs(x - i)) * (1 - std::abs(y - j)));
  }
  void line(double x, double y, double xx, double yy, double l) {
    int n = std::max(1, int(std::ceil(std::hypot(xx - x, yy - y) * 3)));
    for (int i = 0; i <= n; ++i) point(x + (xx-x)*i/n, y + (yy-y)*i/n, l);
  }
  void mask(int x, int y, const char *const *rows, int height, double l) {
    for (int j = 0; j < height; ++j)
      for (int i = 0; rows[j][i]; ++i) if (rows[j][i] != ' ') dot(x+i,y+j,l);
  }
};
void figure(Stage &s, int x, bool cap, double beat, double hit, double l) {
  int step = int(std::floor(beat)) % 2;
  s.dot(x,1,l); s.dot(x+1,1,l);
  if (cap) { s.line(x-1,0,x+2,0,l); s.dot(x+3,1,l); }
  else { s.dot(x,0,l*.5); s.dot(x+1,0,l*.5); }
  s.line(x,2,x,5,l); s.line(x+1,2,x+1,5,l);
  // Exaggerated alternating raised arm and opposite leg: a solemn duet.
  s.line(x,3,x-3,step ? 2 : 4,l);
  s.line(x+1,3,x+4,step ? 4 : 2,l);
  s.dot(x+4,step ? 3 : 1,l*(.5+.5*hit)); // microphone
  s.line(x,5,x-(step ? 2 : 1),7,l);
  s.line(x+1,5,x+(step ? 2 : 3),7,l);
  if (!cap) { s.dot(x-1,2,1); s.dot(x+2,2,1); } // bow tie
}
void ride(Stage &s, double beat, double hit, double l) {
  static const char *car[] = {
    "      ########      ",
    "     #   #    #     ",
    " ################## ",
    "#                  #",
    " ################## "};
  // The body rises on the kick while the wheels remain planted.
  int y = hit > .45 ? 1 : 2;
  s.mask(1,y,car,5,l);
  s.dot(4,7,l); s.dot(5,7,l); s.dot(16,7,l); s.dot(17,7,l);
  s.line(22,6,27,6,l*.55); // absurdly dignified wedding-cake trailer
  s.line(27,6,38,6,l);
  s.line(29,5,36,5,l); s.line(29,4,36,4,l);
  s.line(31,3,34,3,l); s.line(31,2,34,2,l);
  s.dot(32,1,.7); s.dot(33,0,.3+.7*hit); // candle
  s.dot(28,7,l); s.dot(37,7,l);
  // Two small flags flap together, not a noisy trail.
  int flag = int(std::floor(beat)) % 2;
  s.dot(24,3+flag,l); s.dot(25,3,l);
}
void radio(Stage &s, double beat, double hit, const Feature &a, double l) {
  s.line(2,2,37,2,l); s.line(2,7,37,7,l);
  s.line(2,2,2,7,l); s.line(37,2,37,7,l);
  s.line(12,1,27,1,l*.7);
  for (int x : {5,29}) {
    s.line(x,3,x+5,3,l); s.line(x,6,x+5,6,l);
    s.line(x,3,x,6,l); s.line(x+5,3,x+5,6,l);
    s.line(x+2,4,x+3,4,.1+.9*hit);
    s.line(x+2,5,x+3,5,.1+.9*hit);
  }
  for (int i=0;i<6;++i) {
    int height = 1 + int(unit(a.bands[7+i])*2.9);
    s.line(14+i*2,6,14+i*2,6-height,l*(.45+.55*hit));
  }
  // A formal bow tie sits on the handle of an otherwise streetwise boombox.
  int tilt = int(std::floor(beat)) % 2;
  s.dot(17,0,l); s.dot(18,tilt,l); s.dot(20,1,l);
  s.dot(22,1-tilt,l); s.dot(23,0,l);
}
void drama(Stage &s, double beat, double hit, double l) {
  static const char *tear[] = {"   #   ","  ###  "," ##### ","#######","#######"," ##### ","  ###  "};
  int fall = int(std::floor(beat)) % 4 == 3 ? 1 : 0;
  s.mask(17,fall,tear,7,l);
  // Theatre curtains and two spotlights frame a comically monumental tear.
  double opening = 2 + 2 * (.5-.5*std::cos(beat*3.141592653589793/4));
  for (int x=0;x<int(opening);++x) {
    s.line(x,0,x,7,l*.65); s.line(39-x,0,39-x,7,l*.65);
  }
  s.line(5,0,14,7,.1+.25*hit);
  s.line(34,0,26,7,.1+.25*hit);
  s.dot(19,2,.95); // tear highlight
}
void toast(Stage &s, double hit, double l) {
  for (int side : {-1,1}) {
    double x = side < 0 ? 12 + hit*3 : 27 - hit*3;
    s.line(x-2,1,x+2,1,l);
    s.line(x-2,1,x-1,4,l); s.line(x+2,1,x+1,4,l);
    s.line(x-1,4,x+1,4,l); s.line(x,4,x,6,l);
    s.line(x-2,7,x+2,7,l);
    s.line(x-1,2,x+1,2,.2+.8*hit);
  }
  s.dot(19,0,hit); s.dot(20,1,hit); s.dot(21,0,hit);
  for(int x : {3,36}) { s.line(x,3,x,7,l*.6); s.dot(x,1,.25+.75*hit); }
}
}
bool fusion_style(const std::string &s) {
  return s=="fusion-duet" || s=="fusion-ride" || s=="fusion-radio" ||
         s=="fusion-drama" || s=="fusion-toast";
}
Frame fusion(const Feature &a, double beat, const std::string &style) {
  Stage s(unit((a.rms-.005)/.10));
  if (!std::isfinite(beat) || beat < 0 || s.gain==0) return s.frame;
  double hit=unit(a.bass_hit)*std::exp(-std::max(0.f,a.bass_age)/.13);
  double light=.25+.28*unit(a.mids)+.47*hit;
  if(style=="fusion-ride") ride(s,beat,hit,light);
  else if(style=="fusion-radio") radio(s,beat,hit,a,light);
  else if(style=="fusion-drama") drama(s,beat,hit,light);
  else if(style=="fusion-toast") toast(s,hit,light);
  else if(style=="fusion-duet") {
    bool swap=int(std::floor(beat/16))%2;
    figure(s,8,swap,beat,hit,light);
    figure(s,30,!swap,beat+1,hit,light);
    // A tiny diplomatic handshake in the otherwise dark centre.
    s.line(17,4,19,3,.2+.8*hit); s.line(19,3,22,4,.2+.8*hit);
  }
  return s.frame;
}
}
