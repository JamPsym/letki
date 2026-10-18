#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <wchar.h>

#define MESSAGE_MAX_CHARS 64U
enum message_result { MESSAGE_PENDING, MESSAGE_APPLIED, MESSAGE_CANCELLED,
                      MESSAGE_INVALID, MESSAGE_TOO_LONG };

void message_init(const wchar_t *initial);
void message_begin(void);
bool message_editing(void);
enum message_result message_feed(uint8_t byte);
const wchar_t *message_text(void);
size_t message_length(void);
