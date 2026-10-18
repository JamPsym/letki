#include "general.h"
#include <assert.h>
#include <string.h>
/* Deterministic mutation corpus under ASan/UBSan; no hardware mocks are
 * involved. */
static struct lg_node node;
static struct lg_router router;
static uint32_t random_state = 7;
static unsigned random_byte(void) {
  random_state ^= random_state << 13;
  random_state ^= random_state >> 17;
  random_state ^= random_state << 5;
  return random_state & 255;
}
int main(void) {
  struct lg_store storage = {0};
  lg_init(&node, 0, 5, storage);
  uint8_t packet[LG_PACKET] = {1, LG_HELLO, 0, 1, 0, 1, 0, 0};
  lg_put16(packet + 8, lg_crc(packet, 8));
  uint8_t wire[LG_WIRE];
  unsigned size = lg_encode(wire, packet, 10);
  for (unsigned i = 0; i < size; ++i)
    assert(lg_receive(&router, &node, wire[i], 0));
  assert(router.output_length);
  router.output_length = 0;
  // Baud recovery uses monotonic local time, never the adjustable show clock.
  uint8_t rate_packet[LG_PACKET] = {1, LG_BAUD_PREPARE, 0, 1, 0, 2, 0, 2};
  lg_put16(rate_packet + 8, 4608);
  lg_put16(rate_packet + 10, lg_crc(rate_packet, 10));
  node.local_ms = 1000;
  lg_dispatch(&node, rate_packet, 12, 0x70000000);
  assert(node.rate_deadline == 2000 &&
         lg_rate_poll(&node, 2000, true) == 460800);
  uint8_t confirm[LG_PACKET] = {1, LG_BAUD_CONFIRM, 0, 1, 0, 3, 0, 0};
  lg_put16(confirm + 8, lg_crc(confirm, 8));
  node.local_ms = 2100;
  lg_dispatch(&node, confirm, 10, 1);
  assert(node.rate_deadline == 12100 &&
         lg_rate_poll(&node, 12100, true) == 115200);
  uint8_t program[128] = {0}, pixels[64] = {0};
  memcpy(program, "LGS1", 4);
  lg_put16(program + 4, 48);
  program[6] = 1;
  lg_put32(program + 8, 1000);
  program[16] = 1;
  lg_put32(program + 24, 1000);
  program[46] = 100;
  program[47] = 100;
  assert(lg_program_valid(program, 48));
  for (unsigned trial = 0; trial < 100000; ++trial) {
    uint8_t mutation[128];
    memcpy(mutation, program, sizeof program);
    for (unsigned j = 0; j < 1 + trial % 8; ++j)
      mutation[random_byte() % 128] = (uint8_t)random_byte();
    unsigned candidate_length = trial % 2 ? 48 : random_byte() % 129;
    if (lg_program_valid(mutation, candidate_length)) {
      node.program = mutation;
      node.length = candidate_length;
      node.dirty = true;
      node.raw = false;
      (void)lg_render(&node, trial, pixels);
      node.program = 0;
      node.length = 0;
    }
    for (unsigned i = 0; i < LG_PACKET; ++i)
      packet[i] = (uint8_t)random_byte();
    packet[0] = 1;
    packet[1] = (uint8_t)(1 + trial % 19);
    packet[2] = 0;
    lg_put16(packet + 3, 1);
    lg_put16(packet + 5, (uint16_t)trial);
    packet[7] = (uint8_t)(trial % 49);
    lg_put16(packet + 8 + packet[7], lg_crc(packet, 8 + packet[7]));
    unsigned length = lg_dispatch(&node, packet, 10 + packet[7], trial);
    assert(!length || length <= LG_PACKET);
    if (trial % 32 == 0) {
      struct lg_store empty = {0};
      lg_init(&node, 0, 5, empty);
      node.connected = true;
      node.session = 1;
    }
    (void)lg_render(&node, trial, pixels);
  }
  for (unsigned trial = 0; trial < 100000; ++trial) {
    router.output_length = 0;
    (void)lg_receive(
        &router, &node,
        (uint16_t)(random_byte() | ((trial % 47 == 0) ? 0x200 : 0)), trial);
  }
  return 0;
}
