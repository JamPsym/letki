#pragma once
#include <stdbool.h>
#include <stdint.h>

/* Experimental sparse frames: at most one lit row per selected column. */
void pwm_display_init(void);
bool pwm_display_present(const uint8_t pixels[8], const uint8_t levels[8]);
void pwm_display_tick(void);
void pwm_display_unblank(void);
void pwm_display_blank_period(bool enable);
uint32_t pwm_display_scans(void);
/* Foreground digital-pad observation, excluding compare/wrap edges. */
bool pwm_display_sample(uint8_t *row, uint8_t *duty, bool *high, bool *expected);
