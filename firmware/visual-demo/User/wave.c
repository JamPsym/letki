#include "wave.h"
/* Quarter-pixel radii and one cosine period live in flash. No sqrt, float,
 * heap allocation or frame synthesis in the interrupts. */
static const uint8_t radius[64] = {
    20, 17, 15, 14, 14, 15, 17, 20,
    17, 14, 12, 10, 10, 12, 14, 17,
    15, 12, 8, 6, 6, 8, 12, 15,
    14, 10, 6, 3, 3, 6, 10, 14,
    14, 10, 6, 3, 3, 6, 10, 14,
    15, 12, 8, 6, 6, 8, 12, 15,
    17, 14, 12, 10, 10, 12, 14, 17,
    20, 17, 15, 14, 14, 15, 17, 20,
};
static const uint8_t wave[32] = {
    100, 99, 96, 92, 85, 78, 69, 60,
    50, 40, 31, 22, 15, 8, 4, 1,
    0, 1, 4, 8, 15, 22, 31, 40,
    50, 60, 69, 78, 85, 92, 96, 99,
};
void wave_frame(uint8_t levels[64], uint8_t phase)
{
    for (unsigned i = 0; i < 64; ++i)
        levels[i] = wave[(phase-radius[i]) & 31U];
}
