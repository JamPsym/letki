#pragma once

#include <stddef.h>
#include <stdint.h>
#include <wchar.h>

/* Column-major glyphs: bit 0 is the top pixel, bit 7 the bottom. */
typedef struct { wchar_t ch; uint8_t columns[8]; } Glyph;

extern const Glyph font[];
extern const size_t font_count;
uint8_t font_column(wchar_t ch, uint8_t column);
/* Compact 3-column font, with one blank column between letters, for live text. */
uint8_t font_compact_column(wchar_t ch, uint8_t column);
