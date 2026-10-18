#pragma once
#include <stdint.h>
#include "message.h"

/* A command prefix plus 64 four-byte UTF-8 characters and the final NUL. */
#define UART_LINE_CAPACITY (2U + 4U * MESSAGE_MAX_CHARS + 1U)
enum uart_line_result { UART_LINE_PENDING, UART_LINE_READY,
                        UART_LINE_INVALID, UART_LINE_TOO_LONG, UART_LINE_CANCELLED };
void uart_line_init(void);
void uart_line_error(void);
enum uart_line_result uart_line_feed(uint8_t byte);
const char *uart_line_text(void);
