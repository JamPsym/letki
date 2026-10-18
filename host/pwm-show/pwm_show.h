#pragma once
#include <stdint.h>
#define PWM_SHOW_SCENES 6U
#define PWM_SHOW_ACT_STEPS 160U
#define PWM_SHOW_FADE_STEPS 24U
/* choice=-1 runs the complete show; 0..5 holds one scene.
   Row-major tile output: levels[y*8+x], each 0..100. Integer-only, no heap. */
void pwm_show_tile(uint8_t levels[64], uint32_t tick, unsigned tile,
                   unsigned tiles, int choice);
unsigned pwm_show_scene(uint32_t tick, int choice);
const char *pwm_show_name(unsigned scene);
