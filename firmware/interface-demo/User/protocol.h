#pragma once
#include <stdbool.h>
#include <stdint.h>

#define LINE_CAPACITY 80U
struct line_input { char text[LINE_CAPACITY]; unsigned used; bool invalid; };
enum line_result { LINE_WAIT, LINE_READY, LINE_INVALID };
enum line_result line_feed(struct line_input *input, unsigned char byte);
bool parse_counter(const char *text, uint16_t *value);
uint8_t packet_crc(const uint8_t *bytes, unsigned length);
void packet_encode(uint8_t packet[4], uint16_t value);
bool packet_decode(const uint8_t *packet, unsigned length, uint16_t *value);
