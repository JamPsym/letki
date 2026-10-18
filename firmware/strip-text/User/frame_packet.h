#pragma once
#include <stdbool.h>
#include <stdint.h>
#define STRIP_PACKET_BYTES 14U
struct strip_frame { uint16_t sequence; uint8_t brightness, flags, pixels[8]; };
void strip_encode(uint8_t packet[STRIP_PACKET_BYTES], const struct strip_frame *frame);
bool strip_decode(const uint8_t *packet, unsigned length, struct strip_frame *frame);
