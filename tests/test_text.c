#include "font.h"
#include "text.h"
#include <assert.h>
#include <stdio.h>

int main(void)
{
    const wchar_t message[] = L" ZOBACZ ADAŚ DZIAŁA ";
    const size_t length = sizeof(message) / sizeof(message[0]) - 1;
    uint8_t frame[8], next[8];
    text_frame(frame, NULL, 0, 99);
    for (unsigned x = 0; x < 8; ++x)
        assert(frame[x] == 0);
    assert(text_columns(L"A A", 3) == 18);
    assert(text_columns(L" ", 1) == 2);
    text_frame(frame, message, length, 0);
    assert(frame[0] == 0 && frame[1] == 0);

    for (size_t offset = 0; offset < text_columns(message, length); ++offset)
    {
        text_frame(frame, message, length, offset);
        text_frame(next, message, length, offset + 1);
        for (unsigned x = 0; x < 7; ++x)
            assert(next[x] == frame[x + 1]); /* Including glyph and loop seams. */
    }
    text_frame_once(frame, message, length, text_columns(message, length));
    for (unsigned x = 0; x < 8; ++x)
        assert(frame[x] == 0);
    text_frame_once(frame, L"A", 1, 7);
    for (unsigned x = 1; x < 8; ++x) assert(frame[x] == 0);
    unsigned acute = 0, stroke = 0;
    for (unsigned x = 0; x < 8; ++x)
    {
        acute |= font_column(L'Ś', x) ^ font_column(L'S', x);
        stroke |= font_column(L'Ł', x) ^ font_column(L'L', x);
        assert(font_column(L'?', x) == 0);
    }
    assert(acute != 0 && stroke != 0);
    assert(font_column(L'A', 8) == 0);
    puts("Text tests passed: Unicode, blanking, scrolling and wraparound.");
}
