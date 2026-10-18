#include "ch32v00x.h"
#include "display.h"
#include "wave.h"
#include "swio.h"
#include "uart.h"
#include "uart_line.h"
#include "brightness.h"
#include "speed.h"
#include <string.h>

static volatile uint32_t milliseconds;
static uint8_t fraction, phase;
static uint32_t interval = 45, previous;
static bool paused, dirty;
static uint8_t levels[64];
static char response[128];

static void emit(const char *s) { swio_write(s); uart_write(s); }
static char *append(char *p, const char *s) { while (*s) *p++ = *s++; return p; }
static char *decimal(char *p, uint32_t n)
{
    char digits[10]; unsigned used = 0;
    do { digits[used++] = '0'+n%10U; n /= 10U; } while (n);
    while (used) *p++ = digits[--used];
    return p;
}
static void status(void)
{
    char *p = append(response, "speed_ms="); p = decimal(p, interval);
    p = append(p, " paused="); *p++ = paused ? '1' : '0';
    p = append(p, " uptime_ms="); p = decimal(p, milliseconds);
    p = append(p, " uart_errors="); p = decimal(p, uart_errors());
    p = append(p, " tx_dropped="); p = decimal(p, uart_dropped());
    p = append(p, " brightness_pct="); p = decimal(p, display_brightness_get());
    p = append(p, "\r\n"); *p = 0; emit(response);
}
static void help(void)
{
    emit("Radial wave: b 0..100; v 10..500 ms; + / - speed\r\n");
    emit("p pause; r resume; 0 reset; s status; UART ping TOKEN\r\n");
}
static void command(char key)
{
    if (brightness_editing()) {
        uint8_t percent = display_brightness_get();
        switch (brightness_feed((uint8_t)key, &percent)) {
            case BRIGHTNESS_APPLIED:
                display_brightness(percent); dirty = true;
                emit("OK brightness updated\r\n"); break;
            case BRIGHTNESS_INVALID: emit("ERR brightness must be 0..100; unchanged\r\n"); break;
            case BRIGHTNESS_CANCELLED: emit("Brightness cancelled\r\n"); break;
            default: break;
        }
        return;
    }
    if (speed_editing()) {
        switch (speed_feed((uint8_t)key, &interval)) {
            case SPEED_APPLIED: emit("OK speed updated\r\n"); break;
            case SPEED_INVALID: emit("ERR speed must be 10..500 ms\r\n"); break;
            case SPEED_CANCELLED: emit("Speed cancelled\r\n"); break;
            default: break;
        }
        return;
    }
    switch (key) {
        case 'b': brightness_begin(); return;
        case 'v': speed_begin(); return;
        case 'p': paused = true; break;
        case 'r': paused = false; previous = milliseconds; break;
        case '+': if (interval > 10) interval = interval >= 15 ? interval-5 : 10; break;
        case '-': if (interval < 500) interval = interval <= 495 ? interval+5 : 500; break;
        case '0': interval = 45; paused = false; phase = 0;
                  display_brightness(100); dirty = true; break;
        case 's': break;
        case 'h': case '?':
            help();
            return;
        default: return;
    }
    status();
}
static void uart_command(const char *line)
{
    if (!*line) return;
    if (!strcmp(line, "status")) { status(); return; }
    if (!strcmp(line, "help")) { help(); return; }
    if (!strcmp(line, "ping") || !strncmp(line, "ping ", 5)) {
        if (strlen(line) > 79) { emit("ERR ping too long\r\n"); return; }
        char *p = append(response, "PONG"); p = append(p, line+4);
        p = append(p, "\r\n"); *p = 0; emit(response); return;
    }
    if (brightness_editing() || speed_editing()) {
        emit("ERR busy; finish or cancel SWIO edit\r\n"); return;
    }
    if (line[1] == 0 && strchr("+-pr0sh?", line[0])) { command(line[0]); return; }
    if ((line[0] == 'b' || line[0] == 'v') && (line[1] == 0 || line[1] == ' ')) {
        for (unsigned i = 0; line[i]; ++i) command(line[i]);
        command('\n'); return;
    }
    emit("ERR visual demo supports b/v/p/r/0/s/h\r\n");
}
#ifndef VISUAL_INTERRUPT
#define VISUAL_INTERRUPT __attribute__((interrupt("WCH-Interrupt-fast")))
#endif
void SysTick_Handler(void) VISUAL_INTERRUPT;
void SysTick_Handler(void)
{
    SysTick->SR = 0;
    if (++fraction == 2) { fraction = 0; ++milliseconds; }
    display_tick();
}
void TIM2_IRQHandler(void) VISUAL_INTERRUPT;
void TIM2_IRQHandler(void) { display_unblank(); }
int main(void)
{
    SystemCoreClockUpdate(); display_init();
    uart_line_init(); uart_init();
    wave_frame(levels, 0); display_present_levels(levels);
    SysTick->CTLR = 0; SysTick->CNT = 0;
    SysTick->CMP = SystemCoreClock/2000U-1U; SysTick->SR = 0;
    NVIC_EnableIRQ(SysTick_IRQn); NVIC_EnableIRQ(TIM2_IRQn);
    SysTick->CTLR = 0xfU; __enable_irq(); swio_init();
    emit("Letki v3 SWIO ready. radial wave; h=help\r\n");
    emit("Letki v3 VISUAL ready. gamma 2.2; UART 115200 8N1\r\n");
    uint32_t last_log = 0;
    for (;;) {
        uart_poll();
        uint16_t received;
        if (uart_read(&received)) {
            if (received & (UART_RX_INVALID|UART_RX_GAP)) uart_line_error();
            if (!(received & UART_RX_INVALID))
                switch (uart_line_feed((uint8_t)received)) {
                    case UART_LINE_READY: uart_command(uart_line_text()); break;
                    case UART_LINE_INVALID: case UART_LINE_TOO_LONG:
                        emit("ERR invalid UART line; unchanged\r\n"); break;
                    case UART_LINE_CANCELLED: emit("UART draft cancelled\r\n"); break;
                    default: break;
                }
        }
        swio_poll(command);
        const uint32_t now = milliseconds;
        if (dirty || (!paused && now-previous >= interval)) {
            const uint8_t next = dirty ? phase : ((phase+1U)&31U);
            wave_frame(levels, next);
            if (display_present_levels(levels)) {
                phase = next; dirty = false; previous = now;
            }
        }
        if (now-last_log >= 5000U) { status(); last_log = now; }
    }
}
