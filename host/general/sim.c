#include "general.h"
#include <stdlib.h>
#include <string.h>
struct simulation {
  struct lg_node nodes[5];
  struct lg_router routers[5];
  uint8_t flash[5][LG_FLASH], pixels[5][64];
  unsigned selected, fail_after, operations;
};
static __thread struct simulation *current;
static bool erase(uint16_t offset, uint16_t length) {
  struct simulation *s = current;
  if (offset + length > LG_FLASH || offset % 64 || length % 64)
    return false;
  for (unsigned at = offset; at < offset + length; at += 64) {
    if (s->operations++ == s->fail_after)
      return false;
    memset(s->flash[s->selected] + at, 255, 64);
  }
  return true;
}
static bool write_page(uint16_t offset, const uint8_t *p) {
  struct simulation *s = current;
  if (offset + 64 > LG_FLASH || offset % 64)
    return false;
  for (unsigned i = 0; i < 64; ++i) {
    if (s->operations++ == s->fail_after)
      return false;
    s->flash[s->selected][offset + i] &= p[i];
  }
  return true;
}
void lg_sim_reset(struct simulation *s, int erase_flash) {
  s->fail_after = ~0U;
  s->operations = 0;
  if (erase_flash)
    memset(s->flash, 255, sizeof s->flash);
  for (unsigned i = 0; i < 5; ++i) {
    struct lg_store storage = {s->flash[i], LG_FLASH, erase, write_page};
    lg_init(&s->nodes[i], i, 5, storage);
  }
  memset(s->pixels, 0, sizeof s->pixels);
  memset(s->routers, 0, sizeof s->routers);
}
void *lg_sim_create(void) {
  struct simulation *s = calloc(1, sizeof *s);
  if (s)
    lg_sim_reset(s, 1);
  return s;
}
void lg_sim_destroy(struct simulation *s) { free(s); }
unsigned lg_sim_exchange(struct simulation *s, unsigned id, uint8_t *wire,
                         unsigned length, uint32_t now) {
  if (id >= 5)
    return 0;
  current = s;
  s->selected = id;
  s->nodes[id].local_ms = now;
  struct lg_router *r = &s->routers[id];
  for (unsigned i = 0; i < length + 1; ++i)
    lg_receive(r, &s->nodes[id], wire[i], now);
  unsigned used = r->output_length;
  if (used)
    memcpy(wire, r->output, used);
  r->output_length = 0;
  return used;
}
const uint8_t *lg_sim_render(struct simulation *s, unsigned id, uint32_t now) {
  if (id >= 5)
    return 0;
  if (lg_render(&s->nodes[id], now, s->pixels[id]))
    s->nodes[id].presented_generation = s->nodes[id].desired_generation;
  return s->pixels[id];
}
void lg_sim_fault(struct simulation *s, unsigned count) {
  s->operations = 0;
  s->fail_after = count;
}
unsigned lg_sim_operations(struct simulation *s) { return s->operations; }
unsigned lg_sim_node_size(void) { return sizeof(struct lg_node); }

unsigned lg_sim_byte(struct simulation *s, unsigned id, unsigned byte,
                     uint32_t now) {
  if (id >= 5)
    return 0;
  current = s;
  s->selected = id;
  s->nodes[id].local_ms = now;
  return lg_receive(&s->routers[id], &s->nodes[id], (uint16_t)byte, now);
}
unsigned lg_sim_output(struct simulation *s, unsigned id, uint8_t *out) {
  if (id >= 5)
    return 0;
  unsigned length = s->routers[id].output_length;
  memcpy(out, s->routers[id].output, length);
  s->routers[id].output_length = 0;
  return length;
}

unsigned lg_sim_rate(struct simulation *s, unsigned id, unsigned now,
                     unsigned idle) {
  if (id >= 5)
    return 0;
  return lg_rate_poll(&s->nodes[id], now, idle != 0);
}

/* PC streaming source: same interpreter, host-owned validated assets. This is
 * not a device command or an enlargement of advertised MCU storage. */
unsigned lg_sim_source(struct simulation *s, const uint8_t *program,
                       unsigned length) {
  if (!lg_program_valid(program, length))
    return 0;
  for (unsigned i = 0; i < 5; ++i) {
    struct lg_node *n = &s->nodes[i];
    n->program = program;
    n->length = (uint16_t)length;
    n->position = n->anchor = 0;
    n->paused = false;
    n->looping = (program[7] & 1) != 0;
    n->raw = false;
    n->dirty = true;
    n->queue_count = 0;
  }
  return 1;
}
