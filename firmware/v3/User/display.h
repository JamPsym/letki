#pragma once

#include <stdbool.h>
#include <stdint.h>

void display_init(void);
/* Call every 500 us from SysTick, independently of the animation. */
void display_tick(void);
/* TIM2 update releases the 100 us column blank without waiting in an ISR. */
void display_unblank(void);
/* Perceptual percentage, gamma 2.2 mapped to hardware PWM; 0 is off. */
void display_brightness(uint8_t percent);
uint8_t display_brightness_get(void);
/* Queue a frame; false means the previous frame is still waiting. */
#ifdef DISPLAY_LEVELS
/* Column-major 64 perceptual levels (0..100), gamma mapped in foreground.
 * Global brightness is sampled when queued; re-present after changing it.
 */
bool display_present_levels(const uint8_t levels[64]);
#ifdef DISPLAY_GENERAL
bool display_present_tagged(const uint8_t levels[64], uint16_t generation);
uint16_t display_presented_generation(void);
void display_suspend(void);
#endif
#else
bool display_present(const uint8_t columns[8]);
#endif
