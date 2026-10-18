#pragma once
#include <stdbool.h>
#include <stdint.h>

enum speed_result { SPEED_PENDING, SPEED_APPLIED, SPEED_INVALID, SPEED_CANCELLED };
void speed_begin(void);
bool speed_editing(void);
enum speed_result speed_feed(uint8_t byte, uint32_t *milliseconds);
