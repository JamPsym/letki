#pragma once
#include <stdbool.h>
#include <stdint.h>
enum brightness_result { BRIGHTNESS_PENDING, BRIGHTNESS_APPLIED, BRIGHTNESS_INVALID, BRIGHTNESS_CANCELLED };
void brightness_begin(void);
bool brightness_editing(void);
enum brightness_result brightness_feed(uint8_t byte, uint8_t *percent);
