#include "pong.h"

unsigned pong_phase_count(unsigned tiles)
{
    if (!tiles || tiles > PONG_MAX_TILES) return 0;
    unsigned horizontal = 2U * (8U * tiles - 1U);
    unsigned a = horizontal, b = 14U;
    while (b) { unsigned r = a % b; a = b; b = r; }
    return horizontal / a * 14U;
}

bool pong_accept_tiles(struct pong_state *s, uint16_t packet, uint32_t now,
                       unsigned tiles)
{
    uint16_t phase = packet & ~PONG_PAUSED;
    unsigned count = pong_phase_count(tiles);
    if (!count || phase >= count) return false;
    s->phase = phase;
    s->paused = (packet & PONG_PAUSED) != 0;
    s->last_ms = now;
    ++s->accepted;
    s->seen = true;
    s->fault = false;
    return true;
}

bool pong_accept(struct pong_state *s, uint16_t packet, uint32_t now)
{
    return pong_accept_tiles(s, packet, now, 2U);
}

void pong_failed(struct pong_state *s) { ++s->failed; s->fault = true; }

bool pong_alive(const struct pong_state *s, uint32_t now)
{
    return s->seen && !s->fault && (uint32_t)(now - s->last_ms) < PONG_TIMEOUT_MS;
}

bool pong_frame_tiles(const struct pong_state *s, unsigned tile, unsigned tiles,
                      uint32_t now, uint8_t columns[8])
{
    unsigned count = pong_phase_count(tiles);
    if (!count || tile >= tiles || s->phase >= count) return false;
    for (unsigned i = 0; i < 8U; ++i) columns[i] = 0;
    if (s->seen) {
        unsigned width = 8U * tiles, span = 2U * (width - 1U);
        unsigned x = s->phase % span, y = s->phase % 14U;
        if (x >= width) x = span - x;
        if (y > 7U) y = 14U - y;
        if (x / 8U == tile) columns[x & 7U] |= (uint8_t)(1U << y);
    }
    /* This corner cannot intersect the diagonal ball's parity pattern.
     * Toggling derives from received/acknowledged exchanges, not a timer. */
    if (!pong_alive(s, now) || (s->accepted & 4U)) columns[7] |= 1U;
    return true;
}

bool pong_frame(const struct pong_state *s, unsigned tile, uint32_t now,
                uint8_t columns[8])
{
    return pong_frame_tiles(s, tile, 2U, now, columns);
}
