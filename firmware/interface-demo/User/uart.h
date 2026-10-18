#pragma once
#include <stdbool.h>
#include <stdint.h>
void uart_init(void);
void uart_poll(void (*receive)(uint8_t));
bool uart_write(const char *text);
uint32_t uart_errors(void);
uint32_t uart_dropped(void);
