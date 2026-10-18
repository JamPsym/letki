#include "ch32v00x.h"
#include "pwm_display.h"
#include "uart.h"
#include "uart_line.h"
#include "swio.h"
#include <string.h>

static volatile uint32_t milliseconds;
static volatile uint8_t ticks_per_ms = 2, fraction;
static volatile uint32_t scan_hz = 2000;
static uint8_t level = 25, row_select;
static bool fading = true, gradient, changed = true, ascending = true;
static uint32_t high_counts[8], low_counts[8], mismatches[8];
static uint8_t report_row = 8;
static uint32_t last_report;
static char response[128], swio_line[80];
static uint8_t next_frame[8], next_levels[8];
static unsigned swio_used;
static bool swio_invalid, swio_cr;

static void emit(const char *text) { swio_write(text); uart_write(text); }
static char *append(char *out, const char *text) { while (*text) *out++ = *text++; return out; }
static char *number(char *out, uint32_t n)
{
    char digits[10]; unsigned used = 0;
    do { digits[used++] = '0'+n%10U; n /= 10U; } while (n);
    while (used) *out++ = digits[--used];
    return out;
}
static void reset_counts(void)
{
    for (unsigned i = 0; i < 8; ++i) high_counts[i] = low_counts[i] = mismatches[i] = 0;
}
static void status(void)
{
    char *p = append(response, "PWM mode=");
    p = append(p, gradient ? "rows" : fading ? "fade" : "manual");
    p = append(p, " duty="); p = number(p, level);
    p = append(p, " row="); p = number(p, row_select);
    p = append(p, " ms="); p = number(p, milliseconds);
    p = append(p, " scans="); p = number(p, pwm_display_scans());
    p = append(p, " scan_hz="); p = number(p, scan_hz);
    p = append(p, " errors="); p = number(p, uart_errors());
    p = append(p, " drops="); p = number(p, uart_dropped());
    *p++ = '\n'; *p = 0; emit(response);
}
static void samples(void)
{
    report_row = 0;
}
static void report_sample(void)
{
    if (report_row < 8 && milliseconds-last_report >= 15U) {
        last_report = milliseconds;
        const unsigned i = report_row++;
        char *p = append(response, "PAD row="); p = number(p, i+1U);
        p = append(p, " high="); p = number(p, high_counts[i]);
        p = append(p, " low="); p = number(p, low_counts[i]);
        p = append(p, " mismatch="); p = number(p, mismatches[i]);
        *p++ = '\n'; *p = 0;
        emit(response);
    }
}
static bool parse(const char *s, unsigned max, uint8_t *value)
{
    if (!*s) return false;
    unsigned n = 0;
    for (; *s; ++s) {
        if (*s < '0' || *s > '9') return false;
        n = n*10U+(*s-'0');
        if (n > max) return false;
    }
    *value = n; return true;
}
static void set_scan(uint32_t hz)
{
    __disable_irq();
    SysTick->CTLR = 0;
    ticks_per_ms = hz/1000U; fraction = 0; scan_hz = hz;
    SysTick->CNT = 0; SysTick->CMP = SystemCoreClock/hz-1U; SysTick->SR = 0;
    SysTick->CTLR = 0xfU;
    __enable_irq();
}
static void command(const char *s)
{
    if (!*s) return;
    if (!strcmp(s,"s") || !strcmp(s,"status")) { status(); return; }
    if (!strcmp(s,"h") || !strcmp(s,"help")) {
        emit("PWM 10kHz; scan 1/2kHz; sparse patterns\n");
        emit("d 0..100; fade; rows; row 1..8; diag; clear; samples; ping TOKEN\n");
        emit("scan 1000/2000; blank 0/1; 100us blank enabled at startup\n");
        return;
    }
    if (!strncmp(s,"ping ",5) && strlen(s) < 80U) {
        char *p = append(response,"PONG "); p = append(p,s+5);
        *p++ = '\n'; *p = 0; emit(response); return;
    }
    if (!strcmp(s,"samples")) { samples(); return; }
    if (!strcmp(s,"clear")) { reset_counts(); emit("OK counters cleared\n"); return; }
    if (!strcmp(s,"scan 1000") || !strcmp(s,"scan 2000")) {
        set_scan(s[5]=='1' ? 1000U : 2000U); emit("OK PWM updated\n"); return;
    }
    if (!strcmp(s,"blank 0") || !strcmp(s,"blank 1")) {
        pwm_display_blank_period(s[6]=='1'); emit("OK PWM updated\n"); return;
    }
    uint8_t value;
    if (!strncmp(s,"d ",2) && parse(s+2,100,&value)) {
        level = value; fading = gradient = false;
    } else if (!strcmp(s,"fade")) {
        fading = true; gradient = false; row_select = 0;
    } else if (!strcmp(s,"rows")) {
        gradient = true; fading = false; row_select = 0;
    } else if (!strcmp(s,"diag")) row_select = 0;
    else if (!strncmp(s,"row ",4) && parse(s+4,8,&value) && value) row_select = value;
    else { emit("ERR invalid command; h=help\n"); return; }
    changed = true;
    emit("OK PWM updated\n");
}
static void swio_receive(char c)
{
    const uint8_t b = (uint8_t)c;
    if (b == '\n' && swio_cr) { swio_cr = false; return; }
    swio_cr = false;
    if (b == 27U) { swio_used = 0; swio_invalid = false; return; }
    if (b == '\n' || b == '\r') {
        swio_line[swio_used] = 0; swio_used = 0; swio_cr = b == '\r';
        if (swio_invalid) emit("ERR invalid SWIO line\n"); else command(swio_line);
        swio_invalid = false; return;
    }
    if (b < 32U || b > 126U || swio_used >= sizeof(swio_line)-1U) swio_invalid = true;
    if (!swio_invalid) swio_line[swio_used++] = c;
}
void SysTick_Handler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void SysTick_Handler(void)
{
    SysTick->SR = 0;
    if (++fraction == ticks_per_ms) { fraction = 0; ++milliseconds; }
    pwm_display_tick();
}
void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void TIM2_IRQHandler(void) { pwm_display_unblank(); }

int main(void)
{
    SystemCoreClockUpdate();
    uart_line_init(); uart_init();
    pwm_display_init();
    SysTick->CTLR = 0; SysTick->CNT = 0;
    SysTick->CMP = SystemCoreClock/scan_hz-1U; SysTick->SR = 0;
    NVIC_EnableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(SysTick_IRQn); SysTick->CTLR = 0xfU;
    __enable_irq(); swio_init();
    emit("Letki v3 SWIO ready. PWM experiment; h + Enter\n");
    emit("Letki v3 PWM ready. 10kHz; UART 115200 8N1\n");
    uint32_t previous = 0, last_log = 0;
    for (;;) {
        uart_poll();
        uint16_t received;
        if (uart_read(&received)) {
            if (received & (UART_RX_INVALID|UART_RX_GAP)) uart_line_error();
            if (received & UART_RX_GAP) continue;
            const enum uart_line_result result = uart_line_feed((uint8_t)received);
            if (result == UART_LINE_READY) command(uart_line_text());
            else if (result == UART_LINE_INVALID || result == UART_LINE_TOO_LONG)
                emit("ERR damaged UART line\n");
        }
        swio_poll(swio_receive);
        report_sample();
        uint8_t row, duty; bool high, expected;
        if (pwm_display_sample(&row,&duty,&high,&expected)) {
            if (high) ++high_counts[row]; else ++low_counts[row];
            if (high != expected) ++mismatches[row];
        }
        const uint32_t now = milliseconds;
        if (fading && now-previous >= 30U) {
            previous = now;
            if (level >= 100U) ascending = false;
            if (!level) ascending = true;
            level = ascending ? level+1U : level-1U;
            changed = true;
        }
        if (changed) {
            for (unsigned i = 0; i < 8; ++i) {
                next_frame[i] = row_select ? 1U << (row_select-1U) : 1U << i;
                next_levels[i] = gradient ? (i*100U)/7U : level;
            }
            if (pwm_display_present(next_frame,next_levels)) changed = false;
        }
        if (now-last_log >= 2000U) { last_log = now; status(); }
    }
}
