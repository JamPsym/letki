#include "demos.hpp"
#include <stdexcept>
extern "C" {
#include "pwm_show.h"
}
namespace control {
const char *demo_name(int choice) {
  if (choice < -1 || choice >= int(PWM_SHOW_SCENES))
    throw std::invalid_argument("Unknown demo scene");
  return choice < 0 ? "Full PWM showcase" : pwm_show_name(unsigned(choice));
}
DemoFrame render_demo(uint64_t elapsed_ms, int choice, unsigned speed,
                      unsigned brightness) {
  demo_name(choice);
  if (speed < 25 || speed > 200 || brightness > 100)
    throw std::invalid_argument(
        "Demo speed must be 25–200%; brightness 0–100%");
  const auto tick = uint32_t(elapsed_ms * speed / 4000);
  DemoFrame out{};
  for (unsigned tile = 0; tile < 5; tile++) {
    uint8_t local[64];
    pwm_show_tile(local, tick, tile, 5, choice);
    for (unsigned y = 0; y < 8; y++)
      for (unsigned x = 0; x < 8; x++)
        out[y * 40 + tile * 8 + x] =
            (unsigned(local[y * 8 + x]) * brightness + 50) / 100;
  }
  return out;
}
} // namespace control
