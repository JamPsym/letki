#include "general.h"
bool lg_receive(struct lg_router *r, struct lg_node *n, uint16_t byte,
                uint32_t now) {
  if (r->output_length)
    return false;
  if (r->used && (uint32_t)(now - r->last_byte) > 250) {
    r->used = 0;
    r->damaged = true;
  }
  r->last_byte = now;
  if (byte & 0x300)
    r->damaged = true;
  if (!(byte & 0x100) && !(uint8_t)byte) {
    unsigned length = r->damaged ? 0 : lg_decode(r->input, r->used);
    r->used = 0;
    r->damaged = false;
    if (length) {
      length = lg_dispatch(n, r->input, length, now);
      r->output_length = (uint8_t)lg_encode(r->output, r->input, length);
    }
  } else if (r->used < LG_WIRE - 1)
    r->input[r->used++] = (uint8_t)byte;
  else
    r->damaged = true;
  return true;
}
