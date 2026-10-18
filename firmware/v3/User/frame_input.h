#pragma once
#include <stdbool.h>
#include <stdint.h>

enum frame_result { FRAME_PENDING, FRAME_APPLIED, FRAME_INVALID, FRAME_CANCELLED };
void frame_begin(void);
bool frame_editing(void);
enum frame_result frame_feed(uint8_t byte, uint8_t pixels[8]);
