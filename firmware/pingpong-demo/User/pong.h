#pragma once
#include <stdbool.h>
#include <stdint.h>

#define PONG_PHASES 210U
#define PONG_PAUSED 0x8000U
#define PONG_TIMEOUT_MS 1500U

/* Configurable strips retain the existing 15-bit phase/paused wire format.
 * 1..256 tiles fit every complete diagonal trajectory in that phase field. */
#define PONG_MAX_TILES 256U
unsigned pong_phase_count(unsigned tiles);

struct pong_state {
    uint32_t last_ms, accepted, failed;
    uint16_t phase;
    bool seen, fault, paused;
};

/* Only a validated transport callback may commit a communicated phase. */
bool pong_accept(struct pong_state *state, uint16_t packet, uint32_t now);
bool pong_accept_tiles(struct pong_state *state, uint16_t packet, uint32_t now,
                       unsigned tiles);
void pong_failed(struct pong_state *state);
bool pong_alive(const struct pong_state *state, uint32_t now);
/* Render one half of the same 16x8 scene; bit zero is the top pixel. */
bool pong_frame(const struct pong_state *state, unsigned tile, uint32_t now,
                uint8_t columns[8]);
bool pong_frame_tiles(const struct pong_state *state, unsigned tile, unsigned tiles,
                      uint32_t now, uint8_t columns[8]);
