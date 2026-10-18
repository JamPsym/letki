#include "rhythm.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace letki;
static void near(double a, double b) { assert(std::abs(a - b) < 1e-10); }
static void invalid(const Rhythm &r) {
  bool rejected = false;
  try { r.validate(); } catch (const std::runtime_error &) { rejected = true; }
  assert(rejected);
}
int main() {
  Rhythm r;
  r.validate();
  near(r.position(3), 6);
  r.offset = 2;
  near(r.position(1), -2);
  near(r.position(2), 0);
  r.anchors = {{3, 7}};
  r.validate();
  near(r.position(3), 7);
  near(r.position(2), 5);
  r.anchors = {{2, 4}, {4, 8}, {8, 12}};
  r.validate();
  for (const auto &a : r.anchors) near(r.position(a.at), a.beat);
  near(r.position(3), 6);
  near(r.position(6), 10);
  near(r.position(0), 0);
  near(r.position(10), 14);
  // Out-of-order calls model arbitrary forward/backward seeks.
  near(r.position(7), 11);
  // Both directions remain inverses before/inside/after the authored range,
  // with no state accumulated by seeks. Exercise fallback origins as well.
  for (const Rhythm &map : std::vector<Rhythm>{
           Rhythm{}, Rhythm{90, 2, {}}, Rhythm{120, 0, {{3, 7}}}, r}) {
    for (double seconds : {-20., -1., 0., 2., 3., 4., 6., 8., 20.})
      near(map.time(map.position(seconds)), seconds);
    for (double beat : {-20., -1., 0., 4., 6., 8., 10., 12., 30.})
      near(map.position(map.time(beat)), beat);
  }
  for (const auto &a : r.anchors) near(r.time(a.beat), a.at);
  near(r.time(6), 3);
  near(r.time(10), 6);
  near(r.time(-2), -1);
  near(r.time(14), 10);
  near(r.position(1), 2);
  near(r.position(7), 11);
  const double inf = std::numeric_limits<double>::infinity();
  const double nan = std::numeric_limits<double>::quiet_NaN();
  for (double bad : {29., 301., inf, nan}) {
    Rhythm bad_map; bad_map.bpm = bad; invalid(bad_map);
  }
  for (double bad : {inf, nan}) {
    Rhythm bad_map; bad_map.offset = bad; invalid(bad_map);
  }
  for (const auto &anchors : std::vector<std::vector<BeatAnchor>>{
           {{-1, 0}}, {{0, -1}}, {{nan, 0}}, {{0, inf}},
           {{1, 0}, {1, 1}}, {{2, 0}, {1, 1}},
           {{0, 1}, {1, 1}}, {{0, 2}, {1, 1}},
           {{0, 0}, {1, 6}}, {{0, 0}, {10, 1}}}) {
    Rhythm bad_map; bad_map.anchors = anchors; invalid(bad_map);
  }
  for (double bpm : {30., 300.}) {
    Rhythm edge; edge.bpm = bpm; edge.anchors = {{0, 0}, {60, bpm}};
    edge.validate();
  }
  bool rejected = false;
  try { r.position(nan); } catch (const std::runtime_error &) { rejected = true; }
  assert(rejected);
  for (double bad : {nan, inf, -inf}) {
    rejected = false;
    try { r.time(bad); } catch (const std::runtime_error &) { rejected = true; }
    assert(rejected);
  }
  std::cout << "Player rhythm tests passed\n";
}
