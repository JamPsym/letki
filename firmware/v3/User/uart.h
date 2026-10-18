#pragma once
#include <stdbool.h>
#include <stdint.h>

#define UART_RX_INVALID 0x100U
#define UART_RX_GAP 0x200U

void uart_init(void);
/* Foreground only; RX ISR only publishes bytes/flags into the fixed queue. */
bool uart_read(uint16_t *received);
void uart_poll(void);
bool uart_write(const char *text);
/* Foreground-only free space; useful for retaining a relay packet until it fits. */
uint8_t uart_tx_free(void);
uint32_t uart_errors(void);
uint32_t uart_dropped(void);
/* Binary foreground transport; atomic enqueue, including NUL bytes. */
bool uart_write_bytes(const uint8_t *bytes, unsigned length);
void uart_set_baud(uint32_t baud);
