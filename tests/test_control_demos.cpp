#include "demos.hpp"
#include <cassert>
#include <iostream>
#include <set>
int main() {
  for (int scene = -1; scene < 6; scene++) {
    std::set<int> levels;
    assert(control::demo_name(scene)[0]);
    for (unsigned t = 0; t < 5000; t += 37) {
      auto f = control::render_demo(t, scene);
      for (auto v : f) {
        assert(v >= 0 && v <= 100);
        levels.insert(v);
      }
      for (auto v : control::render_demo(t, scene, 200, 25))
        assert(v >= 0 && v <= 25);
    }
    assert(levels.size() > 8);
  }
  auto ladder = control::render_demo(0, 4);
  int expected[] = {0, 1, 2, 5, 10, 25, 50, 100};
  for (unsigned y = 0; y < 8; y++)
    assert(ladder[y * 40 + 36] == expected[y]);
  assert(control::render_demo(1000, 0, 200) ==
         control::render_demo(2000, 0, 100));
  assert(control::render_demo(1234, -1) ==
         control::render_demo(1234 + 38400, -1));
  for (auto v : control::render_demo(500, 3, 100, 0))
    assert(v == 0);
  bool failed = false;
  try {
    control::render_demo(0, 6);
  } catch (...) {
    failed = true;
  }
  assert(failed);
  std::cout << "Demo: six shared PWM scenes, exact low levels, mapping, speed, "
               "brightness and showcase loop passed.\n";
}
