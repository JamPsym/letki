#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define LG_VERSION 1
#define LG_PAYLOAD 48
#define LG_PACKET 58
#define LG_WIRE 60
#define LG_ARENA 752
#define LG_SLOT 80
#define LG_FLASH 4096
#define LG_SAFE 1984
#define LG_LARGE 4032
/* Little endian; CRC-16/CCITT-FALSE. Decoded header: version, op, node,
   session:u16, request:u16, payload length:u8. Payload, CRC16 follow. */
enum lg_op {
  LG_HELLO = 1,
  LG_STATUS,
  LG_TIME,
  LG_BEGIN,
  LG_WRITE,
  LG_COMMIT,
  LG_ABORT,
  LG_PLAY,
  LG_PAUSE,
  LG_SEEK,
  LG_FLUSH,
  LG_BRIGHTNESS,
  LG_FRAME_BEGIN,
  LG_FRAME_DATA,
  LG_FRAME_COMMIT,
  LG_QUEUE,
  LG_READ,
  LG_BAUD_PREPARE,
  LG_BAUD_CONFIRM
};
enum lg_error {
  LG_OK,
  LG_INVALID,
  LG_BUSY,
  LG_SPACE,
  LG_CRC,
  LG_ORDER,
  LG_UNSUPPORTED,
  LG_IO,
  LG_SESSION,
  LG_CONFLICT
};
enum lg_storage { LG_RAM, LG_FLASH_SAFE, LG_FLASH_LARGE };
struct lg_store {
  const uint8_t *base;
  uint16_t size;
  bool (*erase)(uint16_t offset, uint16_t length);
  bool (*write)(uint16_t offset, const uint8_t *page);
};
struct lg_node {
  uint8_t arena[LG_ARENA];
  uint8_t cached[LG_PACKET];
  uint8_t uid[8];
  uint32_t uart_errors, uart_drops;
  struct lg_store store;
  const uint8_t *program;
  uint32_t anchor, position, last_render, flash_generation;
  uint32_t late, local_ms;
  uint16_t length, session, last_request, request_crc, cached_length;
  uint16_t upload_length, upload_crc, upload_received, upload_base;
  uint16_t desired_generation, presented_generation;
  uint16_t pending_rate, clock_age;
  uint32_t rate_deadline, switch_at;
  uint8_t id, tiles, brightness, slots, queue_head, queue_count, queue_stride;
  uint8_t storage, upload_storage, flash_bank;
  bool connected, uploading, paused, looping, dirty, raw, maintenance,
      switch_pending;
  bool rate_prepared, rate_switched;
};
struct lg_router {
  uint8_t input[LG_WIRE], output[LG_WIRE];
  uint32_t last_byte;
  uint8_t used, output_length;
  bool damaged;
};
/* Same byte pump on MCU and simulator. Input flags 0x100/0x200 mark
   invalid/dropped RX bytes. Caller drains output before supplying more input.
 */
bool lg_receive(struct lg_router *r, struct lg_node *n, uint16_t byte,
                uint32_t now);
uint16_t lg_u16(const uint8_t *p);
uint32_t lg_u32(const uint8_t *p);
void lg_put16(uint8_t *p, uint16_t n);
void lg_put32(uint8_t *p, uint32_t n);
uint16_t lg_crc(const uint8_t *p, unsigned length);
unsigned lg_encode(uint8_t out[LG_WIRE], const uint8_t *packet,
                   unsigned length);
unsigned lg_decode(uint8_t *wire, unsigned length);
bool lg_valid_packet(const uint8_t *packet, unsigned length);
bool lg_program_valid(const uint8_t *program, unsigned length);
void lg_init(struct lg_node *n, unsigned id, unsigned tiles,
             struct lg_store store);
/* Valid addressed requests become responses in place. Other packets unchanged.
 */
unsigned lg_dispatch(struct lg_node *n, uint8_t p[LG_PACKET], unsigned length,
                     uint32_t now);
uint32_t lg_position(const struct lg_node *n, uint32_t now);
bool lg_render(struct lg_node *n, uint32_t now, uint8_t pixels[64]);
uint16_t lg_capacity(const struct lg_node *n);
uint32_t lg_rate_poll(struct lg_node *n, uint32_t now, bool transmit_idle);

struct lg_counter {
  uint32_t last, millis, fraction;
};
uint32_t lg_counter_update(struct lg_counter *c, uint32_t cycles,
                           uint32_t ticks_per_ms);
