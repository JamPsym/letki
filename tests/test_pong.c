#include "pong.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned bits(unsigned x) { unsigned n = 0; for (; x; x >>= 1) n += x & 1U; return n; }

int main(void)
{
    struct pong_state s = {0}; uint8_t a[8], b[8];
    assert(!pong_alive(&s, 0));
    assert(pong_frame(&s, 0, 0, a));
    for (unsigned x = 0; x < 7; ++x) assert(!a[x]);
    assert(a[7] == 1); /* No fabricated animation before the first exchange. */
    int old_x = -1, old_y = -1;
    for (unsigned phase = 0; phase < PONG_PHASES * 2; ++phase) {
        unsigned t = phase % PONG_PHASES, now = phase * 100;
        assert(pong_accept(&s, t, now));
        assert(pong_frame(&s, 0, now, a)); assert(pong_frame(&s, 1, now, b));
        a[7] &= ~1U; b[7] &= ~1U;
        unsigned count = 0; int px = -1, py = -1;
        for (unsigned tile = 0; tile < 2; ++tile) for (unsigned x = 0; x < 8; ++x) {
            unsigned v = tile ? b[x] : a[x]; count += bits(v);
            for (unsigned y = 0; y < 8; ++y) if (v & (1U << y)) { px = tile*8+x; py = y; }
        }
        assert(count == 1); assert(px >= 0 && px < 16 && py >= 0 && py < 8);
        if (old_x >= 0) { assert(px-old_x == 1 || px-old_x == -1); assert(py-old_y == 1 || py-old_y == -1); }
        old_x = px; old_y = py;
        struct pong_state before = s;
        assert(!pong_accept(&s, PONG_PHASES, now)); assert(!memcmp(&s, &before, sizeof s));
    }
    /* Timeout and transport failure preserve the last ball phase. */
    uint16_t phase = s.phase;
    assert(!pong_alive(&s, s.last_ms + PONG_TIMEOUT_MS)); assert(s.phase == phase);
    pong_failed(&s); assert(!pong_alive(&s, s.last_ms)); assert(s.phase == phase);
    assert(pong_accept(&s, PONG_PAUSED | 7U, UINT32_MAX - 10U)); assert(s.paused);
    assert(pong_alive(&s, 5)); /* Millisecond wrap. */
    assert(!pong_accept(&s, 0x4000, 0));
    memset(a, 0x5a, sizeof a); assert(!pong_frame(&s, 2, 0, a));
    for (unsigned i = 0; i < 8; ++i) assert(a[i] == 0x5a);
    puts("Pong: one global ball, continuous seam/bounces/wrap, communication-gated frames, timeout/failure and invalid phase checks passed");
}
