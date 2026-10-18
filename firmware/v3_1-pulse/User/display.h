#pragma once
#include <stdbool.h>
#include <stdint.h>

#define PULSE_SCAN_HZ 8000U
#define PULSE_TIMER_TICKS 1320U /* 110us at nominal 12MHz. */
#define PULSE_MAX_TICKS 960U    /* 80us, leaving 30us initial blank. */

void display_init(void);
/* Call from SysTick at 8kHz; fixed eight-column frame is nominally 1ms. */
void display_tick(void);
/* Compatibility entry only: one-pulse hardware ends output, no IRQ release. */
void display_unblank(void);
void display_brightness(uint8_t percent);
uint8_t display_brightness_get(void);
bool display_present(const uint8_t columns[8]);
