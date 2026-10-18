#include "message.h"

/* Two buffers let malformed or overlong input leave the current text intact. */
static wchar_t active[MESSAGE_MAX_CHARS + 3U];
static wchar_t pending[MESSAGE_MAX_CHARS + 3U];
static size_t active_length, input_length;
static uint32_t codepoint, minimum;
static uint8_t remaining;
static bool editing, first_byte;
static enum message_result failure;

static wchar_t uppercase(uint32_t value)
{
    if (value >= 'a' && value <= 'z') return (wchar_t)(value - 'a' + 'A');
    switch (value)
    {
        case 0x0105: return L'Ą'; case 0x0107: return L'Ć';
        case 0x0119: return L'Ę'; case 0x0142: return L'Ł';
        case 0x0144: return L'Ń'; case 0x00f3: return L'Ó';
        case 0x015b: return L'Ś'; case 0x017a: return L'Ź';
        case 0x017c: return L'Ż';
        default: return (wchar_t)value;
    }
}

void message_init(const wchar_t *initial)
{
    active_length = 0;
    while (initial[active_length] && active_length < MESSAGE_MAX_CHARS + 2U)
    {
        active[active_length] = initial[active_length];
        ++active_length;
    }
    active[active_length] = 0;
    editing = false;
}

void message_begin(void)
{
    pending[0] = L' ';
    input_length = 0;
    remaining = 0;
    codepoint = minimum = 0;
    failure = MESSAGE_PENDING;
    editing = first_byte = true;
}

bool message_editing(void) { return editing; }
const wchar_t *message_text(void) { return active; }
size_t message_length(void) { return active_length; }

enum message_result message_feed(uint8_t byte)
{
    if (!editing) return MESSAGE_PENDING;
    if (byte == 27U)
    {
        editing = false;
        return MESSAGE_CANCELLED;
    }
    if (byte == '\r' || byte == '\n')
    {
        editing = false;
        if (failure != MESSAGE_PENDING) return failure;
        if (remaining) return MESSAGE_INVALID;
        pending[input_length + 1U] = L' ';
        pending[input_length + 2U] = 0;
        active_length = input_length + 2U;
        for (size_t i = 0; i <= active_length; ++i) active[i] = pending[i];
        return MESSAGE_APPLIED;
    }
    if (failure != MESSAGE_PENDING) return MESSAGE_PENDING;
    if (first_byte)
    {
        first_byte = false;
        if (byte == ' ') return MESSAGE_PENDING; /* Optional command separator. */
    }
    if (byte == 8U || byte == 127U)
    {
        if (remaining) remaining = 0;
        else if (input_length) --input_length;
        return MESSAGE_PENDING;
    }

    if (remaining)
    {
        if ((byte & 0xc0U) != 0x80U)
        {
            failure = MESSAGE_INVALID;
            return MESSAGE_PENDING;
        }
        codepoint = (codepoint << 6) | (byte & 0x3fU);
        if (--remaining) return MESSAGE_PENDING;
        if (codepoint < minimum || codepoint > 0x10ffffU ||
            (codepoint >= 0xd800U && codepoint <= 0xdfffU))
        {
            failure = MESSAGE_INVALID;
            return MESSAGE_PENDING;
        }
    }
    else if (byte < 0x80U)
    {
        if (byte < 32U) return MESSAGE_PENDING;
        codepoint = byte;
    }
    else if (byte >= 0xc2U && byte <= 0xdfU)
    {
        codepoint = byte & 0x1fU; remaining = 1; minimum = 0x80U;
        return MESSAGE_PENDING;
    }
    else if (byte >= 0xe0U && byte <= 0xefU)
    {
        codepoint = byte & 0x0fU; remaining = 2; minimum = 0x800U;
        return MESSAGE_PENDING;
    }
    else if (byte >= 0xf0U && byte <= 0xf4U)
    {
        codepoint = byte & 7U; remaining = 3; minimum = 0x10000U;
        return MESSAGE_PENDING;
    }
    else
    {
        failure = MESSAGE_INVALID;
        return MESSAGE_PENDING;
    }
    if (input_length == MESSAGE_MAX_CHARS)
    {
        failure = MESSAGE_TOO_LONG;
        return MESSAGE_PENDING;
    }
    pending[++input_length] = uppercase(codepoint);
    return MESSAGE_PENDING;
}
