#include "frame_input.h"
#include "font.h"
#include <assert.h>
#include <stdio.h>

static uint8_t pixels[8];
static enum frame_result send(const char *text)
{
    frame_begin();
    enum frame_result result = FRAME_PENDING;
    for (unsigned i = 0; text[i]; ++i) result = frame_feed((uint8_t)text[i], pixels);
    return result;
}
int main(void)
{
    assert(send("001122334455aaFF\n") == FRAME_APPLIED);
    assert(pixels[0] == 0 && pixels[6] == 0xaa && pixels[7] == 0xff);
    assert(send("bad\n") == FRAME_INVALID && pixels[7] == 0xff);
    assert(send("00000000000000000\n") == FRAME_INVALID);
    assert(send("000000000000000x\n") == FRAME_INVALID);
    assert(send("00\x1b") == FRAME_CANCELLED);
    assert(font_compact_column(L'Ś', 2) & 1);
    assert(font_compact_column(L'Ą', 2) & 0x40);
    assert(font_compact_column(L'Ł', 1) != font_compact_column(L'L', 1));
    assert(font_compact_column(L'A', 3) == 0);
    puts("Live frame tests passed: packets, cancellation and Polish compact glyphs.");
}
