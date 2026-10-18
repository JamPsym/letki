#pragma once

#include <stddef.h>
#include <stdint.h>
#include <wchar.h>

/* Render an eight-column window into a repeating message. */
size_t text_columns(const wchar_t *text, size_t length);
void text_frame(uint8_t frame[8], const wchar_t *text, size_t length,
                size_t offset);
/* For demo scenes: columns past the end stay blank rather than wrapping. */
void text_frame_once(uint8_t frame[8], const wchar_t *text, size_t length,
                     size_t offset);
