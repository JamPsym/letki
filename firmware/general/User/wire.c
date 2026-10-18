#include "general.h"
#include <string.h>
uint16_t lg_u16(const uint8_t *p) { return p[0] | ((uint16_t)p[1] << 8); }
uint32_t lg_u32(const uint8_t *p) {
  return lg_u16(p) | ((uint32_t)lg_u16(p + 2) << 16);
}
void lg_put16(uint8_t *p, uint16_t n) {
  p[0] = n;
  p[1] = n >> 8;
}
void lg_put32(uint8_t *p, uint32_t n) {
  lg_put16(p, n);
  lg_put16(p + 2, n >> 16);
}
uint16_t lg_crc(const uint8_t *p, unsigned length) {
  uint16_t crc = 0xffff;
  while (length--) {
    crc ^= (uint16_t)*p++ << 8;
    for (unsigned b = 0; b < 8; ++b)
      crc = (uint16_t)((crc << 1) ^ ((crc & 0x8000) ? 0x1021 : 0));
  }
  return crc;
}
bool lg_valid_packet(const uint8_t *p, unsigned len) {
  return len >= 10 && len <= LG_PACKET && p[7] <= LG_PAYLOAD &&
         len == 10U + p[7] && lg_u16(p + len - 2) == lg_crc(p, len - 2);
}
unsigned lg_encode(uint8_t out[LG_WIRE], const uint8_t *p, unsigned len) {
  if (len > LG_PACKET)
    return 0;
  unsigned code_at = 0, used = 1, code = 1;
  for (unsigned i = 0; i < len; ++i) {
    if (!p[i]) {
      out[code_at] = (uint8_t)code;
      code_at = used++;
      code = 1;
    } else {
      out[used++] = p[i];
      ++code;
    }
  }
  out[code_at] = (uint8_t)code;
  out[used++] = 0;
  return used;
}
unsigned lg_decode(uint8_t *p, unsigned len) {
  if (!len || len >= LG_WIRE)
    return 0;
  unsigned read = 0, write = 0;
  while (read < len) {
    unsigned count = p[read++];
    if (!count || read + count - 1 > len)
      return 0;
    for (unsigned j = 1; j < count; ++j)
      p[write++] = p[read++];
    if (count != 255 && read < len)
      p[write++] = 0;
  }
  return lg_valid_packet(p, write) ? write : 0;
}
