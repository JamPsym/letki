#include "text.h"
#include "font.h"
#include <stdbool.h>

static size_t width(wchar_t character) { return character == L' ' ? 2U : 8U; }

size_t text_columns(const wchar_t *text, size_t length)
{
    size_t columns = 0;
    for (size_t i = 0; i < length; ++i) columns += width(text[i]);
    return columns;
}

static void render(uint8_t frame[8], const wchar_t *text, size_t length,
                   size_t offset, bool repeat)
{
    const size_t total = text_columns(text, length);
    for (size_t column = 0; column < 8; ++column)
    {
        if (total == 0 || (!repeat && (offset >= total || column >= total - offset)))
        {
            frame[column] = 0;
            continue;
        }
        size_t position = repeat ? ((offset % total) + column) % total : offset + column;
        size_t glyph = 0;
        while (position >= width(text[glyph])) position -= width(text[glyph++]);
        frame[column] = font_column(text[glyph], (uint8_t)position);
    }
}

void text_frame(uint8_t frame[8], const wchar_t *text, size_t length, size_t offset)
{
    render(frame, text, length, offset, true);
}

void text_frame_once(uint8_t frame[8], const wchar_t *text, size_t length, size_t offset)
{
    render(frame, text, length, offset, false);
}
