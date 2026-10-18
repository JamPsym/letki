#pragma once
#include <array>
#include <cstdint>
namespace control {
using DemoFrame = std::array<int, 320>;
// -1 cycles through the original six PWM scenes; 0..5 selects one.
const char *demo_name(int choice);
DemoFrame render_demo(uint64_t elapsed_ms, int choice, unsigned speed = 100,
                      unsigned brightness = 100);
} // namespace control
