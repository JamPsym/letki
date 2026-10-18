#include "general.h"
#include <string.h>
uint16_t lg_capacity(const struct lg_node *n) {
  return LG_ARENA - n->slots * n->queue_stride;
}
static unsigned stride(const struct lg_node *n) {
  return (n->store.size / 128U) * 64U;
}
static unsigned safe_size(const struct lg_node *n) {
  return n->store.size >= 128 ? stride(n) - 64 : 0;
}
static unsigned large_size(const struct lg_node *n) {
  return n->store.size >= 128 ? n->store.size - 64 : 0;
}
static const uint8_t *manifest(struct lg_node *n, unsigned bank) {
  const uint8_t *p = n->store.base + bank * stride(n);
  unsigned len = lg_u16(p + 8), mode = p[12],
           max = mode == LG_FLASH_LARGE ? large_size(n) : safe_size(n);
  if (memcmp(p, "LGF1", 4) ||
      (mode != LG_FLASH_SAFE && mode != LG_FLASH_LARGE) ||
      (mode == LG_FLASH_LARGE && bank) || !len || len > max ||
      lg_u16(p + 16) != lg_crc(p, 16) ||
      lg_crc(p + 64, len) != lg_u16(p + 10) || !lg_program_valid(p + 64, len))
    return 0;
  return p;
}
void lg_init(struct lg_node *n, unsigned id, unsigned tiles,
             struct lg_store store) {
  memset(n, 0, sizeof *n);
  n->id = id;
  n->tiles = tiles;
  n->store = store;
  n->brightness = 100;
  n->paused = true;
  n->slots = 2;
  n->queue_stride = LG_SLOT;
  n->flash_bank = 255;
  if (!store.base || store.size < 128)
    return;
  const uint8_t *a = manifest(n, 0), *b = manifest(n, 1), *p = a;
  if (b && (!a || (int32_t)(lg_u32(b + 4) - lg_u32(a + 4)) > 0))
    p = b;
  if (p) {
    n->program = p + 64;
    n->length = lg_u16(p + 8);
    n->flash_generation = lg_u32(p + 4);
    n->flash_bank = (uint8_t)((p - store.base) / stride(n));
    n->storage = p[12];
    n->looping = (n->program[7] & 1) != 0;
    n->paused = false;
    n->dirty = true;
  }
}
static uint8_t *queue(struct lg_node *n, unsigned index) {
  return n->arena + lg_capacity(n) + (index % n->slots) * n->queue_stride;
}
static unsigned info(struct lg_node *n, uint8_t *out, uint32_t now) {
  out[0] = LG_VERSION;
  out[1] = n->id;
  out[2] = n->tiles;
  out[3] = n->slots;
  lg_put16(out + 4, lg_capacity(n));
  lg_put16(out + 6, n->length);
  lg_put16(out + 8, n->store.base ? safe_size(n) : 0);
  lg_put16(out + 10, n->store.base ? large_size(n) : 0);
  lg_put32(out + 12, now);
  lg_put32(out + 16, lg_position(n, now));
  out[20] = (n->paused ? 1 : 0) | (n->raw ? 2 : 0);
  out[21] = n->storage;
  out[22] = n->queue_count;
  out[23] = (n->uploading ? 1 : 0) | (n->switch_pending ? 2 : 0);
  lg_put16(out + 24, n->presented_generation);
  lg_put16(out + 26, n->desired_generation);
  lg_put32(out + 28, n->late);
  out[32] = n->brightness;
  out[33] = n->maintenance;
  return 34;
}
static bool flash_page(struct lg_node *n, unsigned used) {
  if (used < 64)
    memset(n->arena + used, 255, 64 - used);
  unsigned base = n->upload_base + 64 + ((n->upload_received - 1) / 64) * 64;
  return n->store.write((uint16_t)base, n->arena);
}
static unsigned execute(struct lg_node *n, unsigned op, uint8_t *d,
                        unsigned len, uint8_t *out, unsigned *used,
                        uint32_t now) {
  *used = 0;
  if (op == LG_HELLO || op == LG_STATUS) {
    if (len)
      return LG_INVALID;
    *used = info(n, out, now);
    if (op == LG_HELLO)
      memcpy(out + 34, n->uid, 8);
    else {
      lg_put32(out + 34, n->uart_errors);
      lg_put32(out + 38, n->uart_drops);
    }
    unsigned occupied = n->storage == LG_RAM ? n->length : 0;
    if ((n->uploading || n->switch_pending) && n->upload_storage == LG_RAM)
      occupied += n->upload_length;
    if (n->maintenance)
      occupied += 64;
    lg_put16(out + 42,
             occupied < lg_capacity(n) ? lg_capacity(n) - occupied : 0);
    lg_put16(out + 44, LG_ARENA);
    out[46] = (uint8_t)(n->slots - n->queue_count);
    *used = 47;
    return LG_OK;
  }
  if (op == LG_TIME) {
    if (len)
      return LG_INVALID;
    lg_put32(out, now);
    lg_put32(out + 4, lg_position(n, now));
    lg_put16(out + 8, n->clock_age);
    *used = 10;
    return LG_OK;
  }
  if (op == LG_ABORT) {
    if (len)
      return LG_INVALID;
    n->uploading = false;
    n->switch_pending = false;
    n->maintenance = false;
    n->dirty = true;
    return LG_OK;
  }
  if (op == LG_BEGIN) {
    if (len != 6 || d[0] > LG_FLASH_LARGE || d[1] > 1)
      return LG_INVALID;
    if (n->uploading || n->queue_count || n->switch_pending)
      return LG_BUSY;
    unsigned size = lg_u16(d + 2);
    if (size < 16)
      return LG_INVALID;
    unsigned base = 0;
    if (d[0] == LG_RAM) {
      base = (!d[1] && n->storage == LG_RAM) ? n->length : 0;
      if (size > lg_capacity(n) || base > lg_capacity(n) - size)
        return LG_SPACE;
    } else {
      if (!n->store.base || !n->store.erase || !n->store.write)
        return LG_UNSUPPORTED;
      if (d[0] == LG_FLASH_LARGE && !d[1])
        return LG_CONFLICT;
      if (d[0] == LG_FLASH_SAFE && n->flash_bank != 255 &&
          manifest(n, n->flash_bank) &&
          manifest(n, n->flash_bank)[12] == LG_FLASH_LARGE)
        return LG_SPACE;
      if (size > (d[0] == LG_FLASH_SAFE ? safe_size(n) : large_size(n)))
        return LG_SPACE;
      if (n->length && n->storage == LG_RAM && !d[1])
        return LG_SPACE;
      base = d[0] == LG_FLASH_SAFE && n->flash_bank == 0 ? stride(n) : 0;
    }
    if (d[1] || d[0] != LG_RAM) {
      n->paused = true;
      n->dirty = true;
      n->raw = false;
    }
    if (d[1] || (d[0] != LG_RAM && n->storage == LG_RAM)) {
      n->length = 0;
      n->program = 0;
    }
    n->upload_storage = d[0];
    n->upload_base = base;
    n->upload_length = size;
    n->upload_crc = lg_u16(d + 4);
    n->upload_received = 0;
    n->uploading = true;
    if (d[0] != LG_RAM) {
      n->maintenance = true;
      if (!n->store.erase((uint16_t)base,
                          d[0] == LG_FLASH_SAFE ? stride(n) : n->store.size)) {
        n->uploading = false;
        return LG_IO;
      }
    }
    return LG_OK;
  }
  if (op == LG_WRITE) {
    if (!n->uploading)
      return LG_ORDER;
    if (len < 3 || lg_u16(d) != n->upload_received)
      return LG_ORDER;
    unsigned count = len - 2;
    if (count > (unsigned)(n->upload_length - n->upload_received))
      return LG_SPACE;
    if (n->upload_storage == LG_RAM) {
      memcpy(n->arena + n->upload_base + n->upload_received, d + 2, count);
      n->upload_received += count;
    } else
      for (unsigned i = 0; i < count; ++i) {
        n->arena[n->upload_received % 64] = d[2 + i];
        ++n->upload_received;
        if (!(n->upload_received % 64) && !flash_page(n, 64))
          return LG_IO;
      }
    return LG_OK;
  }
  if (op == LG_COMMIT) {
    if ((len != 0 && len != 4) || !n->uploading ||
        n->upload_received != n->upload_length)
      return LG_ORDER;
    if (len == 4 && n->upload_storage != LG_RAM)
      return LG_UNSUPPORTED;
    if (n->upload_storage != LG_RAM && n->upload_received % 64 &&
        !flash_page(n, n->upload_received % 64))
      return LG_IO;
    const uint8_t *p = n->upload_storage == LG_RAM
                           ? n->arena + n->upload_base
                           : n->store.base + n->upload_base + 64;
    if (lg_crc(p, n->upload_length) != n->upload_crc)
      return LG_CRC;
    if (!lg_program_valid(p, n->upload_length))
      return LG_INVALID;
    if (len == 4) {
      n->switch_at = lg_u32(d);
      n->switch_pending = true;
      n->uploading = false;
      return LG_OK;
    }
    if (n->upload_storage == LG_RAM) {
      memmove(n->arena, p, n->upload_length);
      n->program = n->arena;
    } else {
      memset(n->arena, 255, 64);
      memcpy(n->arena, "LGF1", 4);
      lg_put32(n->arena + 4, n->flash_generation + 1);
      lg_put16(n->arena + 8, n->upload_length);
      lg_put16(n->arena + 10, n->upload_crc);
      n->arena[12] = n->upload_storage;
      lg_put16(n->arena + 16, lg_crc(n->arena, 16));
      if (!n->store.write(n->upload_base, n->arena))
        return LG_IO;
      if (!manifest(n, n->upload_base / stride(n)))
        return LG_IO;
      n->program = p;
      n->flash_bank = n->upload_base / stride(n);
      ++n->flash_generation;
    }
    n->length = n->upload_length;
    n->storage = n->upload_storage;
    n->uploading = false;
    n->maintenance = false;
    n->position = 0;
    n->paused = true;
    n->looping = (n->program[7] & 1) != 0;
    n->raw = false;
    n->dirty = true;
    return LG_OK;
  }
  if (op == LG_READ) {
    if (len != 3 || !n->program || d[2] > 47 || lg_u16(d) > n->length ||
        d[2] > n->length - lg_u16(d))
      return LG_INVALID;
    *used = d[2];
    memcpy(out, n->program + lg_u16(d), *used);
    return LG_OK;
  }
  if (op == LG_PAUSE) {
    if (len)
      return LG_INVALID;
    n->position = lg_position(n, now);
    n->paused = true;
    n->uploading = n->switch_pending = n->maintenance = false;
    n->queue_count = n->queue_head = 0;
    n->dirty = true;
    return LG_OK;
  }
  if (n->uploading || n->maintenance || n->switch_pending)
    return LG_BUSY;
  if (op == LG_PLAY) {
    if (len != 9 || !n->program || d[8] > 1)
      return LG_INVALID;
    n->anchor = lg_u32(d);
    n->position = lg_u32(d + 4);
    n->looping = d[8];
    n->queue_count = n->queue_head = 0;
    n->paused = false;
    n->raw = false;
    n->dirty = true;
    return LG_OK;
  }
  if (op == LG_SEEK) {
    if (len != 4 || !n->program)
      return LG_INVALID;
    n->position = lg_u32(d);
    n->queue_count = n->queue_head = 0;
    n->anchor = now;
    n->dirty = true;
    n->raw = false;
    return LG_OK;
  }
  if (op == LG_FLUSH) {
    if (len)
      return LG_INVALID;
    n->queue_count = 0;
    n->queue_head = 0;
    return LG_OK;
  }
  if (op == LG_BRIGHTNESS) {
    if (len != 1 || d[0] > 100)
      return LG_INVALID;
    n->brightness = d[0];
    n->dirty = true;
    return LG_OK;
  }
  if (op == LG_QUEUE) {
    if ((len != 1 && len != 2) || d[0] > 16 || (len == 2 && d[1] > 2))
      return LG_INVALID;
    unsigned bytes = len == 1    ? LG_SLOT
                     : d[1] == 0 ? 24
                     : d[1] == 1 ? 48
                                 : LG_SLOT;
    if (d[0] * bytes > LG_ARENA)
      return LG_SPACE;
    if (n->queue_count || !n->paused)
      return LG_BUSY;
    if (n->storage == LG_RAM && n->length > LG_ARENA - d[0] * bytes)
      return LG_SPACE;
    n->slots = d[0];
    n->queue_stride = bytes;
    n->queue_head = 0;
    return LG_OK;
  }
  if (op == LG_FRAME_BEGIN) {
    if (len < 7 || d[6] > 2)
      return LG_INVALID;
    unsigned bytes = d[6] == 0 ? 8 : d[6] == 1 ? 32 : 64;
    uint32_t deadline = lg_u32(d + 2);
    if ((uint32_t)(deadline - now) > 60000 &&
        (uint32_t)(now - deadline) > 60000)
      return LG_INVALID;
    if (bytes + 10 > n->queue_stride)
      return LG_SPACE;
    if (len - 7 > bytes)
      return LG_INVALID;
    if (d[6] == 2)
      for (unsigned i = 7; i < len; ++i)
        if (d[i] > 100)
          return LG_INVALID;
    if (n->queue_count == n->slots)
      return LG_BUSY;
    uint8_t *q = queue(n, n->queue_head + n->queue_count);
    if (n->queue_count) {
      uint8_t *last = queue(n, n->queue_head + n->queue_count - 1);
      if (!last[9] || (int32_t)(lg_u32(d + 2) - lg_u32(last + 2)) < 0)
        return LG_ORDER;
    }
    memset(q, 0, n->queue_stride);
    memcpy(q, d, 7);
    q[7] = d[6] == 0 ? 8 : d[6] == 1 ? 32 : 64;
    q[8] = (uint8_t)(len - 7);
    memcpy(q + 10, d + 7, len - 7);
    ++n->queue_count;
    return LG_OK;
  }
  if (op == LG_FRAME_DATA || op == LG_FRAME_COMMIT) {
    if (len < 2 || !n->queue_count)
      return LG_ORDER;
    uint8_t *q = queue(n, n->queue_head + n->queue_count - 1);
    if (lg_u16(d) != lg_u16(q) || q[9])
      return LG_ORDER;
    if (op == LG_FRAME_DATA) {
      if (len < 4 || d[2] != q[8] || len - 3U > (unsigned)(q[7] - q[8]))
        return LG_ORDER;
      if (q[6] == 2)
        for (unsigned i = 3; i < len; ++i)
          if (d[i] > 100)
            return LG_INVALID;
      memcpy(q + 10 + q[8], d + 3, len - 3);
      q[8] += (uint8_t)(len - 3);
      return LG_OK;
    }
    if (len != 2 || q[8] != q[7])
      return LG_ORDER;
    q[9] = 1;
    return LG_OK;
  }
  /* Rates are represented in 100-baud units, reset/recovery is always 115200.
   */
  if (op == LG_BAUD_PREPARE) {
    if (len != 2 || n->queue_count)
      return LG_INVALID;
    unsigned rate = lg_u16(d);
    if (rate != 1152 && rate != 2304 && rate != 4608 && rate != 9216)
      return LG_UNSUPPORTED;
    n->pending_rate = rate;
    n->rate_deadline = n->local_ms + 1000;
    n->rate_prepared = true;
    n->rate_switched = false;
    return LG_OK;
  }
  if (op == LG_BAUD_CONFIRM) {
    if (len || !n->rate_switched)
      return LG_ORDER;
    n->rate_prepared = n->pending_rate != 1152;
    n->rate_switched = n->rate_prepared;
    n->rate_deadline = n->local_ms + 10000;
    return LG_OK;
  }
  return LG_UNSUPPORTED;
}
unsigned lg_dispatch(struct lg_node *n, uint8_t p[LG_PACKET], unsigned length,
                     uint32_t now) {
  if (!lg_valid_packet(p, length))
    return 0;
  if ((p[1] & 0x80) || p[2] != n->id)
    return length;
  uint16_t session = lg_u16(p + 3), request = lg_u16(p + 5),
           digest = lg_u16(p + length - 2);
  unsigned op = p[1], used = 0, error;
  if (n->rate_switched && n->rate_prepared && session == n->session &&
      p[0] == LG_VERSION)
    n->rate_deadline = n->local_ms + 10000;
  if (op == LG_HELLO && p[0] == LG_VERSION && session != n->session) {
    n->session = session;
    n->connected = true;
    n->cached_length = 0;
  }
  if (p[0] != LG_VERSION)
    error = LG_UNSUPPORTED;
  else if (!n->connected || session != n->session)
    error = LG_SESSION;
  else if (n->cached_length && request == n->last_request) {
    if (digest == n->request_crc) {
      memcpy(p, n->cached, n->cached_length);
      return n->cached_length;
    }
    error = LG_CONFLICT;
  } else if (n->cached_length && (int16_t)(request - n->last_request) <= 0)
    error = LG_ORDER;
  else {
    /* Preserve input while execute writes its reply. A small bounded scratch is
       supplied by the unused response area in cached, not a packet-sized stack.
     */
    memcpy(n->cached, p + 8, p[7]);
    error = execute(n, op, n->cached, p[7], p + 9, &used, now);
  }
  p[0] = LG_VERSION;
  p[1] = (uint8_t)(op | 0x80);
  p[7] = (uint8_t)(used + 1);
  p[8] = (uint8_t)error;
  length = 11 + used;
  lg_put16(p + length - 2, lg_crc(p, length - 2));
  /* Errors for stale/conflicting requests must not evict the retry cache. */
  if (n->connected && session == n->session &&
      (!n->cached_length || (int16_t)(request - n->last_request) > 0)) {
    n->last_request = request;
    n->request_crc = digest;
    n->cached_length = length;
    memcpy(n->cached, p, length);
  }
  return length;
}

uint32_t lg_rate_poll(struct lg_node *n, uint32_t now, bool transmit_idle) {
  if (!n->rate_prepared || !transmit_idle ||
      (int32_t)(now - n->rate_deadline) < 0)
    return 0;
  if (!n->rate_switched) {
    n->rate_switched = true;
    n->rate_deadline = now + 2000;
    return (uint32_t)n->pending_rate * 100;
  }
  n->rate_prepared = false;
  n->rate_switched = false;
  return 115200;
}
