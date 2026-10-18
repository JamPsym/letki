/* v3.1 communication qualification: display.c holds every row gate LOW.
 * Protocol/bus drivers reuse the preserved original interface demo. */
#include <string.h>
#include "ch32v00x.h"
#include "display.h"
#include "swio.h"
#include "uart.h"
#include "bus.h"
#include "protocol.h"

static volatile uint32_t milliseconds;
static struct line_input uart_input, swio_input;
#ifndef INTERFACE_BOOT_MODE
#define INTERFACE_BOOT_MODE BUS_OFF
#endif
static enum bus_mode role = INTERFACE_BOOT_MODE;
static uint32_t successes, failures;
static uint16_t last_counter;
static bool pixels_changed = true;
static char response[128];
/* Standalone controller image starts testing without a PC connection. */
static bool automatic = INTERFACE_BOOT_MODE == BUS_CONTROLLER;
static uint16_t next_counter = 1;
static uint32_t last_attempt;

static char *number(char *out, uint32_t value)
{
    char digits[10];
    unsigned length = 0;
    do { digits[length++] = (char)('0' + value % 10U); value /= 10U; } while (value);
    while (length) *out++ = digits[--length];
    return out;
}

static char *append(char *out, const char *text)
{
    while (*text) *out++ = *text++;
    return out;
}

static void emit(const char *text)
{
    uart_write(text);
    swio_write(text);
}

static const char *mode_name(void)
{
    return role == BUS_CONTROLLER ? "controller" : role == BUS_TARGET ? "target" : "uart";
}

static void status(void)
{
    char *out = append(response, "STATUS mode=");
    out = append(out, mode_name());
    out = append(out, " ok="); out = number(out, successes);
    out = append(out, " fail="); out = number(out, failures);
    out = append(out, " counter="); out = number(out, last_counter);
    out = append(out, " uart_errors="); out = number(out, uart_errors());
    out = append(out, " tx_dropped="); out = number(out, uart_dropped());
    out = append(out, " auto="); out = number(out, automatic);
    out = append(out, "\r\n"); *out = 0;
    emit(response);
}

static void report(bool success, uint16_t counter, const char *reason)
{
    if (success) { ++successes; last_counter = counter; pixels_changed = true; }
    else ++failures;
    pixels_changed = true;
    char *out = append(response, success ? "I2C OK counter=" : "I2C ERR counter=");
    out = number(out, counter);
    out = append(out, " reason="); out = append(out, reason);
    out = append(out, "\r\n"); *out = 0;
    emit(response);
}

static void command(const char *line)
{
    if (!strcmp(line, "ping")) emit("PONG\r\n");
    else if (!strncmp(line, "ping ", 5)) {
        char *out = append(response, "PONG ");
        out = append(out, line + 5); out = append(out, "\r\n"); *out = 0;
        emit(response);
    } else if (!strcmp(line, "hw"))
        emit("FW LETKI_V3_1_INTERFACE_LED_OFF expects=33R/3V3\r\n");
    else if (!strcmp(line, "status")) status();
    else if (!strcmp(line, "help")) {
        emit("ping [TOKEN]; hw; status; mode uart/controller/target; send 0..65535\r\n");
        emit("auto on/off: controller sends a counter every second\r\n");
    } else if (!strcmp(line, "auto on") || !strcmp(line, "auto off")) {
        if (role != BUS_CONTROLLER) { emit("ERR auto requires controller mode\r\n"); return; }
        automatic = !strcmp(line, "auto on");
        last_attempt = milliseconds;
        next_counter = (uint16_t)(last_counter + 1U);
        status();
    } else if (!strncmp(line, "mode ", 5)) {
        enum bus_mode next;
        if (!strcmp(line + 5, "uart")) next = BUS_OFF;
        else if (!strcmp(line + 5, "controller")) next = BUS_CONTROLLER;
        else if (!strcmp(line + 5, "target")) next = BUS_TARGET;
        else { emit("ERR mode must be uart/controller/target\r\n"); return; }
        if (bus_busy()) { emit("ERR busy; retry after transaction\r\n"); return; }
        bus_init(next);
        role = next;
        automatic = false;
        successes = failures = 0;
        pixels_changed = true;
        status();
    } else if (!strncmp(line, "send ", 5)) {
        uint16_t value;
        if (!parse_counter(line + 5, &value)) emit("ERR counter must be 0..65535\r\n");
        else if (!bus_send(value, milliseconds)) emit("ERR select controller mode or wait until idle\r\n");
        else emit("QUEUED\r\n");
    } else if (*line) emit("ERR unknown command; help\r\n");
}

static void automatic_poll(uint32_t now)
{
    if (!automatic || role != BUS_CONTROLLER || bus_busy() ||
        (uint32_t)(now-last_attempt) < 1000U) return;
    if (bus_send(next_counter, now)) {
        ++next_counter;
        last_attempt = now;
    }
}

static void update_pixels(void)
{
    if (!pixels_changed) return;
    uint8_t pixels[8] = {0};
    pixels[0] = 1;
    pixels[1] = role == BUS_CONTROLLER ? 1 : role == BUS_TARGET ? 3 : 0;
    /* Third row: a successful exchange; fourth row: any error since mode reset. */
    if (successes) pixels[0] |= 4;
    if (failures) pixels[0] |= 8;
    for (unsigned i = 0; i < 8; ++i) {
        if (last_counter & (1U << i)) pixels[i] |= 0x40;
        if (last_counter & (1U << (i + 8))) pixels[i] |= 0x80;
    }
    if (display_present(pixels)) pixels_changed = false;
}

static void feed(struct line_input *input, uint8_t byte)
{
    const enum line_result result = line_feed(input, byte);
    if (result == LINE_READY) command(input->text);
    if (result == LINE_INVALID) emit("ERR invalid or overlong line\r\n");
}
static void uart_receive(uint8_t byte) { feed(&uart_input, byte); }
static void swio_receive(char byte) { feed(&swio_input, (uint8_t)byte); }

#ifndef INTERFACE_INTERRUPT
#define INTERFACE_INTERRUPT __attribute__((interrupt("WCH-Interrupt-fast")))
#endif
void SysTick_Handler(void) INTERFACE_INTERRUPT;
void SysTick_Handler(void)
{
    SysTick->SR = 0;
    ++milliseconds;
    display_tick();
}

int main(void)
{
    SystemCoreClockUpdate();
    display_init();
    SysTick->CTLR = 0;
    SysTick->CNT = 0;
    SysTick->CMP = SystemCoreClock / 1000U - 1U;
    SysTick->SR = 0;
    NVIC_EnableIRQ(SysTick_IRQn);
    SysTick->CTLR = 0xFU;
    __enable_irq();
    swio_init();
    uart_init();
    bus_init(role);
    emit("FW LETKI_V3_1_INTERFACE_LED_OFF expects=33R/3V3\r\n");
    emit("LETKI interfaces ready; UART 115200 8N1; help + Enter\r\n");
    status();
    while (1) {
        /* Service I2C first so UART/SWIO formatting cannot starve clock stretching. */
        bus_poll(milliseconds, report);
        automatic_poll(milliseconds);
        uart_poll(uart_receive);
        swio_poll(swio_receive);
        update_pixels();
    }
}
