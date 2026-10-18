#pragma once
#include <stdint.h>
/* A frame is column-major, top pixel first; phase wraps every 32 steps. */
void wave_frame(uint8_t levels[64], uint8_t phase);
