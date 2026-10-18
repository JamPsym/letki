#include "general.h"
#include <string.h>
/* LGS1: total:u16, tracks:u8, flags:u8(loop), duration:u32, reserved:u32.
 32-byte tracks: op/fmt/flags/reserved; start/duration/period:u32;
 asset:u16,width:u16,height:u8,reserved; x0,y0,x1,y1:i16; level0,level1:u8.
 Motion flags: linear=1, triangle=2, repeat-x=4. Period max 60000 ms. */
bool lg_program_valid(const uint8_t *p, unsigned len) {
  if (len < 16 || memcmp(p, "LGS1", 4) || lg_u16(p + 4) != len || p[6] > 16 ||
      p[7] > 1 || !lg_u32(p + 8) || lg_u32(p + 8) > 0x7fffffff ||
      lg_u32(p + 12) || 16U + 32U * p[6] > len)
    return false;
  for (unsigned i = 0; i < p[6]; ++i) {
    const uint8_t *r = p + 16 + 32 * i;
    unsigned op = r[0], fmt = r[1], flags = r[2];
    uint32_t start = lg_u32(r + 4), duration = lg_u32(r + 8),
             period = lg_u32(r + 12);
    if ((op != 1 && op != 2) || fmt > 2 || (flags & ~7U) || (flags & 3) == 3 ||
        r[3] || r[21] || !duration || start >= lg_u32(p + 8) ||
        duration > lg_u32(p + 8) - start || period > 60000 ||
        ((flags & 3) && !period) || r[30] > 100 || r[31] > 100)
      return false;
    if (op == 2) {
      unsigned width = lg_u16(r + 18), height = r[20], offset = lg_u16(r + 16);
      uint32_t bytes = (uint32_t)width * height;
      if (!width || !height || width > 4096)
        return false;
      if (fmt == 0)
        bytes = (bytes + 7) / 8;
      else if (fmt == 1)
        bytes = (bytes + 1) / 2;
      if (offset < 16U + 32U * p[6] || offset > len || bytes > len - offset)
        return false;
      if (fmt == 2)
        for (unsigned j = 0; j < bytes; ++j)
          if (p[offset + j] > 100)
            return false;
    }
  }
  return true;
}
static uint8_t sample(const uint8_t *p, unsigned fmt, unsigned pixel) {
  if (fmt == 0)
    return (p[pixel / 8] & (1U << (pixel % 8))) ? 100 : 0;
  if (fmt == 1)
    return (uint8_t)(((p[pixel / 2] >> ((pixel & 1) * 4)) & 15) * 100 / 15);
  return p[pixel];
}
static uint8_t *slot(struct lg_node *n, unsigned index) {
  return n->arena + LG_ARENA - n->slots * n->queue_stride +
         (index % n->slots) * n->queue_stride;
}
uint32_t lg_position(const struct lg_node *n, uint32_t now) {
  if (n->paused || (int32_t)(now - n->anchor) < 0)
    return n->position;
  return n->position + (uint32_t)(now - n->anchor);
}
bool lg_render(struct lg_node *n, uint32_t now, uint8_t pixels[64]) {
  if (n->switch_pending && (int32_t)(now - n->switch_at) >= 0) {
    memmove(n->arena, n->arena + n->upload_base, n->upload_length);
    n->program = n->arena;
    n->length = n->upload_length;
    n->storage = LG_RAM;
    n->position = 0;
    n->anchor = n->switch_at;
    n->paused = false;
    n->looping = (n->program[7] & 1) != 0;
    n->raw = false;
    n->dirty = true;
    n->switch_pending = false;
  }
  if (n->maintenance) {
    if (!n->dirty)
      return false;
    memset(pixels, 0, 64);
    n->dirty = false;
    return true;
  }
  bool changed = false;
  while (n->queue_count) {
    uint8_t *q = slot(n, n->queue_head);
    if (!q[9] || (int32_t)(now - lg_u32(q + 2)) < 0)
      break;
    for (unsigned i = 0; i < 64; ++i)
      pixels[i] = sample(q + 10, q[6], i);
    n->desired_generation = lg_u16(q);
    if ((uint32_t)(now - lg_u32(q + 2)) > 20)
      ++n->late;
    n->queue_head = (n->queue_head + 1) % n->slots;
    --n->queue_count;
    n->raw = true;
    changed = true;
  }
  if (n->raw) {
    changed = changed || n->dirty;
    n->dirty = false;
    return changed;
  }
  if (!n->program || !n->length)
    return false;
  if (!n->paused && (int32_t)(now - n->anchor) < 0)
    return false;
  if (!n->dirty && (uint32_t)(now - n->last_render) < 20)
    return false;
  n->dirty = false;
  n->last_render = now;
  const uint8_t *p = n->program;
  uint32_t time = lg_position(n, now), duration = lg_u32(p + 8);
  /* Keep a continuously running show inside the signed clock horizon even
     when left powered for weeks. Preserve phase through millisecond wrap. */
  if (!n->paused && (int32_t)(now - n->anchor) >= 60000) {
    n->position = n->looping         ? time % duration
                  : time >= duration ? duration - 1
                                     : time;
    n->anchor = now;
    time = n->position;
  }
  if (n->looping)
    time %= duration;
  else if (time >= duration)
    time = duration - 1;
  memset(pixels, 0, 64);
  for (unsigned i = 0; i < p[6]; ++i) {
    const uint8_t *r = p + 16 + 32 * i;
    uint32_t start = lg_u32(r + 4), length = lg_u32(r + 8),
             period = lg_u32(r + 12);
    if (time < start || time - start >= length)
      continue;
    unsigned f = 0;
    if (r[2] & 3) {
      uint32_t t = time - start;
      if (r[2] & 2)
        t %= period;
      else if (t > period)
        t = period;
      f = (unsigned)(t * 1000 / period);
      if (r[2] & 2)
        f = f <= 500 ? f * 2 : (1000 - f) * 2;
    }
    int x0 = (int16_t)lg_u16(r + 22), y0 = (int16_t)lg_u16(r + 24);
    int x = x0 + ((int32_t)(int16_t)lg_u16(r + 26) - x0) * (int)f / 1000;
    int y = y0 + ((int32_t)(int16_t)lg_u16(r + 28) - y0) * (int)f / 1000;
    unsigned level =
        (unsigned)((int)r[30] + ((int)r[31] - (int)r[30]) * (int)f / 1000);
    if (r[0] == 1) {
      memset(pixels, (int)level, 64);
      continue;
    }
    unsigned width = lg_u16(r + 18), height = r[20];
    const uint8_t *asset = p + lg_u16(r + 16);
    for (unsigned py = 0; py < 8; ++py)
      for (unsigned px = 0; px < 8; ++px) {
        int sx = (int)(n->id * 8 + px) - x, sy = (int)py - y;
        if (r[2] & 4) {
          sx %= (int)width;
          if (sx < 0)
            sx += (int)width;
        }
        if (sx < 0 || sy < 0 || (unsigned)sx >= width || (unsigned)sy >= height)
          continue;
        unsigned v =
            (sample(asset, r[1], (unsigned)sy * width + (unsigned)sx) * level +
             50) /
            100;
        if (v)
          pixels[py * 8 + px] = (uint8_t)v;
      }
  }
  return true;
}
