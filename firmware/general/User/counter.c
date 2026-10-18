#include "general.h"
/* Free-running HCLK counter keeps wall time through flash maintenance while
 * scan interrupts are suspended. Poll at least once per 32-bit hardware wrap
 * (about 89 seconds at 48 MHz); ordinary bounded operations are much shorter.
 */
uint32_t lg_counter_update(struct lg_counter *c, uint32_t cycles,
                           uint32_t ticks_per_ms) {
  uint32_t delta = cycles - c->last;
  c->last = cycles;
  uint32_t fraction = c->fraction + delta % ticks_per_ms;
  c->millis += delta / ticks_per_ms;
  if (fraction >= ticks_per_ms) {
    ++c->millis;
    fraction -= ticks_per_ms;
  }
  c->fraction = fraction;
  return c->millis;
}
