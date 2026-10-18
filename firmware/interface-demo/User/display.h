#pragma once

#include <stdbool.h>
#include <stdint.h>

void display_init(void);
/* Call once per millisecond from SysTick, not from the animation loop. */
void display_tick(void);
/* Queue a frame; false means the previous frame is still waiting. */
bool display_present(const uint8_t columns[8]);
