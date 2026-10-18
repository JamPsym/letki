#include "frame_input.h"

static uint8_t pending[8], count;
static bool editing, invalid;
void frame_begin(void)
{
    editing = true; invalid = false; count = 0;
    for (unsigned i = 0; i < 8; ++i) pending[i] = 0;
}
bool frame_editing(void) { return editing; }
enum frame_result frame_feed(uint8_t byte, uint8_t pixels[8])
{
    if (!editing) return FRAME_PENDING;
    if (byte == 27U) { editing = false; return FRAME_CANCELLED; }
    if (byte == '\r' || byte == '\n')
    {
        editing = false;
        if (invalid || count != 16) return FRAME_INVALID;
        for (unsigned i = 0; i < 8; ++i) pixels[i] = pending[i];
        return FRAME_APPLIED;
    }
    if (invalid) return FRAME_PENDING;
    int value = -1;
    if (byte >= '0' && byte <= '9') value = byte - '0';
    else if (byte >= 'a' && byte <= 'f') value = byte - 'a' + 10;
    else if (byte >= 'A' && byte <= 'F') value = byte - 'A' + 10;
    if (value < 0 || count >= 16) { invalid = true; return FRAME_PENDING; }
    pending[count / 2] |= (uint8_t)(value << ((count & 1U) ? 0 : 4));
    ++count;
    return FRAME_PENDING;
}
