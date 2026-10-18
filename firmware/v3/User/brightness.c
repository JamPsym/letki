#include "brightness.h"
static bool editing, invalid, digits;
static uint16_t value;
void brightness_begin(void) { editing = true; invalid = digits = false; value = 0; }
bool brightness_editing(void) { return editing; }
enum brightness_result brightness_feed(uint8_t byte, uint8_t *percent)
{
    if (byte == 27U) { editing = false; return BRIGHTNESS_CANCELLED; }
    if (byte == '\n' || byte == '\r') {
        editing = false;
        if (invalid || !digits) return BRIGHTNESS_INVALID;
        *percent = value; return BRIGHTNESS_APPLIED;
    }
    if (byte == ' ' && !digits) return BRIGHTNESS_PENDING;
    if (invalid) return BRIGHTNESS_PENDING;
    if (byte < '0' || byte > '9') { invalid = true; return BRIGHTNESS_PENDING; }
    digits = true; value = value*10U+byte-'0';
    if (value > 100U) invalid = true;
    return BRIGHTNESS_PENDING;
}
