#include "chain.h"

uint16_t chain_crc(const uint8_t *data, unsigned length)
{
    uint16_t crc = 0xffffU;
    while (length--) {
        crc ^= (uint16_t)*data++ << 8;
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = crc & 0x8000U ? (uint16_t)((crc << 1) ^ 0x1021U) : (uint16_t)(crc << 1);
    }
    return crc;
}
static uint32_t load32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static void store32(uint8_t *p, uint32_t n)
{
    for (unsigned i = 0; i < 4; ++i) { p[i] = n; n >>= 8; }
}
bool chain_decode(const uint8_t in[CHAIN_PACKET_BYTES], struct chain_packet *p)
{
    const uint16_t crc = (uint16_t)in[12] | ((uint16_t)in[13]<<8);
    if (in[0] != 1U || chain_crc(in,12) != crc) return false;
    p->hops = in[1];
    p->counter = (uint16_t)in[2] | ((uint16_t)in[3]<<8);
    p->token = load32(in+4);
    p->errors = load32(in+8);
    return true;
}
void chain_encode(char out[CHAIN_WIRE_LENGTH+1U], const struct chain_packet *p)
{
    static const char hex[] = "0123456789ABCDEF";
    uint8_t bytes[CHAIN_PACKET_BYTES];
    bytes[0] = 1; bytes[1] = p->hops;
    bytes[2] = p->counter; bytes[3] = p->counter>>8;
    store32(bytes+4,p->token); store32(bytes+8,p->errors);
    const uint16_t crc = chain_crc(bytes,12);
    bytes[12] = crc; bytes[13] = crc>>8;
    out[0] = '@';
    for (unsigned i = 0; i < CHAIN_PACKET_BYTES; ++i) {
        out[1+2*i] = hex[bytes[i]>>4]; out[2+2*i] = hex[bytes[i]&15U];
    }
    out[29] = '\r'; out[30] = '\n'; out[31] = 0;
}
static uint32_t add(uint32_t a, uint32_t b) { return UINT32_MAX-a < b ? UINT32_MAX : a+b; }

void chain_feed(struct chain_node *n, uint16_t received, uint32_t transport_errors)
{
    const uint8_t byte = received;
    if (received & (CHAIN_RX_INVALID|CHAIN_RX_GAP)) n->damaged = true;
    if (received & CHAIN_RX_INVALID) return;
    if (byte == '@') {
        if (n->collecting) ++n->rejected;
        n->collecting = true; n->digits = 0; n->after_cr = false; n->damaged = false;
        return;
    }
    if (!n->collecting) return;
    if (byte == '\r') {
        if (n->digits != 28U || n->after_cr) n->damaged = true;
        n->after_cr = true; return;
    }
    if (byte == '\n') {
        n->collecting = false;
        struct chain_packet p;
        if (n->damaged || n->digits != 28U || !chain_decode(n->input,&p) || p.hops == 255U) {
            ++n->rejected; return;
        }
        if (n->pending) { ++n->dropped; return; }
        ++p.hops;
        p.errors = add(p.errors,add(transport_errors,add(n->rejected,n->dropped)));
        chain_encode(n->output,&p);
        n->last = p; ++n->accepted; n->pending = n->dirty = true;
        return;
    }
    unsigned digit;
    if (byte >= '0' && byte <= '9') digit = byte-'0';
    else if (byte >= 'a' && byte <= 'f') digit = byte-'a'+10U;
    else if (byte >= 'A' && byte <= 'F') digit = byte-'A'+10U;
    else { n->damaged = true; return; }
    if (n->after_cr || n->digits >= 28U) { n->damaged = true; return; }
    if (!(n->digits&1U)) n->input[n->digits/2U] = digit<<4;
    else n->input[n->digits/2U] |= digit;
    ++n->digits;
}
