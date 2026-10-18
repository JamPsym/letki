#include "ch32v00x.h"
#include "display.h"
#include "swio.h"
#include "bus.h"
#include "pong.h"

#ifndef PONG_TILE
#define PONG_TILE 0
#endif

static volatile uint32_t milliseconds;
static uint8_t fraction, frame[8];
static struct pong_state state;
static uint16_t next_phase, interval = 100;
static uint32_t last_attempt;
static bool paused, reset_requested, dirty = true, event, was_alive;
static char line[100];

static char *append(char *p, const char *s) { while (*s) *p++ = *s++; return p; }
static char *number(char *p, uint32_t n)
{
    char digits[10]; unsigned used = 0;
    do { digits[used++] = '0' + n % 10U; n /= 10U; } while (n);
    while (used) *p++ = digits[--used];
    return p;
}

static void status(void)
{
    char *p = append(line, PONG_TILE ? "PONG role=right phase=" : "PONG role=left phase=");
    p = number(p, state.phase);
    p = append(p, " ok="); p = number(p, state.accepted);
    p = append(p, " bad="); p = number(p, state.failed);
    p = append(p, " link="); p = number(p, pong_alive(&state, milliseconds));
    p = append(p, " paused="); p = number(p, PONG_TILE ? state.paused : paused);
    p = append(p, " ms="); p = number(p, interval);
    p = append(p, "\r\n"); *p = 0;
    swio_write(line);
}

static void command(char key)
{
    if (key == 's') { status(); return; }
    if (key == 'h' || key == '?') {
        swio_write("Ping-pong: s status; left controls p pause, r resume, 0 reset, +/- speed\r\n");
        return;
    }
    if (PONG_TILE) return;
    if (key == 'p') paused = true;
    else if (key == 'r') paused = false;
    else if (key == '0') { reset_requested = true; paused = false; }
    else if (key == '+' && interval > 50U) interval -= 25U;
    else if (key == '-' && interval < 500U) interval += 25U;
    else return;
    status();
}

static void report(bool success, uint16_t packet, const char *reason)
{
    (void)reason;
    if (success && pong_accept(&state, packet, milliseconds)) {
        if (!PONG_TILE) {
            next_phase = (state.phase + 1U) % PONG_PHASES;
            if (paused) next_phase = state.phase;
        }
    } else pong_failed(&state);
    dirty = event = true;
}

static void trace(void)
{
    char *p = append(line, state.fault ? "PONG ERR phase=" : PONG_TILE ? "PONG RX phase=" : "PONG TX phase=");
    p = number(p, state.phase);
    p = append(p, state.fault ? "\r\n" : " CRC\r\n"); *p = 0;
    swio_write(line);
}

static void controller_poll(uint32_t now)
{
    if (PONG_TILE || bus_busy() || (uint32_t)(now - last_attempt) < interval) return;
    if (reset_requested) { next_phase = 0; reset_requested = false; }
    uint16_t packet = next_phase | (paused ? PONG_PAUSED : 0);
    if (bus_send(packet, now)) last_attempt = now;
}

static void publish_frame(uint32_t now)
{
    bool alive = pong_alive(&state, now);
    if (alive != was_alive) { was_alive = alive; dirty = true; }
    if (dirty) {
        pong_frame(&state, PONG_TILE, now, frame);
        if (display_present(frame)) dirty = false;
    }
}

#ifndef PONG_INTERRUPT
#define PONG_INTERRUPT __attribute__((interrupt("WCH-Interrupt-fast")))
#endif
void SysTick_Handler(void) PONG_INTERRUPT;
void SysTick_Handler(void)
{
    SysTick->SR = 0;
    if (++fraction == 2U) { fraction = 0; ++milliseconds; }
    display_tick();
}
void TIM2_IRQHandler(void) PONG_INTERRUPT;
void TIM2_IRQHandler(void) { display_unblank(); }

int main(void)
{
    SystemCoreClockUpdate();
    display_init(); display_brightness(100);
    bus_init(PONG_TILE ? BUS_TARGET : BUS_CONTROLLER);
    SysTick->CTLR = 0; SysTick->CNT = 0;
    SysTick->CMP = SystemCoreClock / 2000U - 1U; SysTick->SR = 0;
    NVIC_EnableIRQ(SysTick_IRQn); NVIC_EnableIRQ(TIM2_IRQn);
    SysTick->CTLR = 0xfU; __enable_irq(); swio_init();
    swio_write(PONG_TILE ? "LETKI PINGPONG right ready; I2C target 0x32\r\n" :
                          "LETKI PINGPONG left ready; I2C controller\r\n");
    uint32_t last_status = 0;
    for (;;) {
        uint32_t now = milliseconds;
        bus_poll(now, report);
        swio_poll(command);
        now = milliseconds;
        controller_poll(now);
        publish_frame(now);
        /* Logging is outside the bus callback and interrupt paths. */
        if (event) { event = false; trace(); }
        if ((uint32_t)(now - last_status) >= 2000U) { last_status = now; status(); }
    }
}
