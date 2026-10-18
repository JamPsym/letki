#include "speed.h"

static bool editing, invalid, digits;
static uint16_t value;

void speed_begin(void) { editing = true; invalid = digits = false; value = 0; }
bool speed_editing(void) { return editing; }
enum speed_result speed_feed(uint8_t byte, uint32_t *milliseconds)
{
    if (!editing) return SPEED_PENDING;
    if (byte == 27U) { editing = false; return SPEED_CANCELLED; }
    if (byte == '\n' || byte == '\r')
    {
        editing = false;
        if (invalid || !digits || value < 10U || value > 500U) return SPEED_INVALID;
        *milliseconds = value;
        return SPEED_APPLIED;
    }
    if (byte == ' ' && !digits) return SPEED_PENDING;
    if (invalid) return SPEED_PENDING;
    if (byte < '0' || byte > '9') { invalid = true; return SPEED_PENDING; }
    digits = true;
    value = value * 10U + byte - '0';
    if (value > 500U) invalid = true;
    return SPEED_PENDING;
}
