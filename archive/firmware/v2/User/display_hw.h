#pragma once

#include <stddef.h>
#include <stdint.h>
#include <wchar.h>

typedef struct { wchar_t ch; uint8_t columns[8]; } Glyph8x8;

struct gpio_line { uint32_t gpio_base; uint8_t pin; };

extern const Glyph8x8 FONT_8x8[];
extern const size_t GLYPH_LEN;

extern const struct gpio_line row_drive_lines[8];
extern const struct gpio_line column_sink_lines[8];

#define GPIOA_CLEAR_MASK 0x2  // A 1
#define GPIOC_CLEAR_MASK 0x19 // C 0 3 4
#define GPIOD_CLEAR_MASK 0x9C // D 2 3 4 7
#define GPIOA_SET_MASK 0x4    // A 2
#define GPIOC_SET_MASK 0xE6   // C 1 2 5 6 7
#define GPIOD_SET_MASK 0x3    // D 0 1
