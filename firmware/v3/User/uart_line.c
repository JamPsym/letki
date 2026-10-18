#include "uart_line.h"

static char line[UART_LINE_CAPACITY];
static unsigned used;
static enum uart_line_result failure;
static bool after_cr;

void uart_line_init(void)
{
    used = 0;
    failure = UART_LINE_PENDING;
    after_cr = false;
}
void uart_line_error(void) { failure = UART_LINE_INVALID; }
const char *uart_line_text(void) { return line; }

enum uart_line_result uart_line_feed(uint8_t byte)
{
    if (byte == '\n' && after_cr) { after_cr = false; return UART_LINE_PENDING; }
    after_cr = false;
    if (byte == 27U)
    {
        used = 0;
        failure = UART_LINE_PENDING;
        return UART_LINE_CANCELLED;
    }
    if (byte == '\r' || byte == '\n')
    {
        line[used] = 0;
        used = 0;
        after_cr = byte == '\r';
        const enum uart_line_result result = failure == UART_LINE_PENDING ?
                                            UART_LINE_READY : failure;
        failure = UART_LINE_PENDING;
        return result;
    }
    if (failure != UART_LINE_PENDING) return UART_LINE_PENDING;
    if (byte == 8U || byte == 127U)
    {
        while (used && ((uint8_t)line[used - 1U] & 0xc0U) == 0x80U) --used;
        if (used) --used;
        return UART_LINE_PENDING;
    }
    if (byte < 32U) { failure = UART_LINE_INVALID; return UART_LINE_PENDING; }
    if (used == UART_LINE_CAPACITY - 1U)
    {
        failure = UART_LINE_TOO_LONG;
        return UART_LINE_PENDING;
    }
    line[used++] = (char)byte;
    return UART_LINE_PENDING;
}
