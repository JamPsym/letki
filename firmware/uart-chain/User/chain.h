#pragma once
#include <stdbool.h>
#include <stdint.h>

#define CHAIN_PACKET_BYTES 14U
#define CHAIN_WIRE_LENGTH 31U
#define CHAIN_RX_INVALID 0x100U
#define CHAIN_RX_GAP 0x200U

struct chain_packet {
    uint32_t token, errors;
    uint16_t counter;
    uint8_t hops;
};
struct chain_node {
    uint8_t input[CHAIN_PACKET_BYTES], digits;
    bool collecting, damaged, after_cr, pending, dirty;
    char output[CHAIN_WIRE_LENGTH+1U];
    struct chain_packet last;
    uint32_t accepted, rejected, dropped;
};
uint16_t chain_crc(const uint8_t *data, unsigned length);
bool chain_decode(const uint8_t input[CHAIN_PACKET_BYTES], struct chain_packet *packet);
void chain_encode(char output[CHAIN_WIRE_LENGTH+1U], const struct chain_packet *packet);
/* Foreground only. RX flags have the same ordered-prefix semantics as uart.h. */
void chain_feed(struct chain_node *node, uint16_t received, uint32_t transport_errors);
