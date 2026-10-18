#include <assert.h>
#include <string.h>
#define main interface_firmware_main
#ifdef V3_1_INTERFACE_TEST
#include "../firmware/v3_1-interface/User/main.c"
#else
#include "../firmware/interface-demo/User/main.c"
#endif
#undef main

MockSysTick fake_systick;
uint32_t SystemCoreClock = 48000000;
static bool busy, accept_frame = true;
static unsigned sends;
static uint16_t sent_counter;
static uint8_t displayed[8];
static char output[4096];
void SystemCoreClockUpdate(void) {}
void NVIC_EnableIRQ(unsigned irq) { (void)irq; }
void __enable_irq(void) {}
void display_init(void) {}
void display_tick(void) {}
bool display_present(const uint8_t p[8]) {
    if (!accept_frame) return false;
    memcpy(displayed, p, 8); return true;
}
void swio_init(void) {}
void swio_poll(void (*receive)(char)) { (void)receive; }
bool swio_write(const char *s) { (void)s; return true; }
void uart_init(void) {}
void uart_poll(void (*receive)(uint8_t)) { (void)receive; }
bool uart_write(const char *s) { strcat(output, s); return true; }
uint32_t uart_errors(void) { return 0; }
uint32_t uart_dropped(void) { return 0; }
void bus_init(enum bus_mode m) { (void)m; busy = false; }
bool bus_busy(void) { return busy; }
bool bus_send(uint16_t c, uint32_t now) {
    (void)now;
    if (busy) return false;
    sent_counter = c; ++sends; busy = true; return true;
}
void bus_poll(uint32_t now, void (*callback)(bool, uint16_t, const char *)) {
    (void)now; (void)callback;
}

int main(void)
{
    assert(automatic && role == BUS_CONTROLLER);
#ifdef V3_1_INTERFACE_TEST
    command("hw");
    assert(!strcmp(output, "FW LETKI_V3_1_INTERFACE_LED_OFF expects=33R/3V3\r\n"));
    output[0] = 0;
#endif
    automatic_poll(999); assert(!sends);
    automatic_poll(1000); assert(sends == 1 && sent_counter == 1);
    automatic_poll(2000); assert(sends == 1); /* No overlap while bus is busy. */
    report(false, 1, "NACK"); busy = false;
    update_pixels(); assert(displayed[0] == 9 && displayed[1] == 1);
    automatic_poll(2000); assert(sends == 2 && sent_counter == 2);
    report(true, 2, "reply CRC"); busy = false;
    update_pixels(); assert(displayed[0] == 13 && displayed[1] == 0x41);
    assert(last_counter == 2 && successes == 1 && failures == 1);
    command("auto off"); automatic_poll(5000); assert(sends == 2);
    milliseconds = 5000; command("auto on");
    automatic_poll(5999); assert(sends == 2);
    automatic_poll(6000); assert(sends == 3 && sent_counter == 3);
    busy = false;
    next_counter = 65535; automatic_poll(7000);
    assert(sent_counter == 65535); busy = false;
    automatic_poll(8000); assert(sent_counter == 0); busy = false;
    last_attempt = UINT32_MAX-499U;
    const unsigned before = sends;
    automatic_poll(499); assert(sends == before);
    automatic_poll(500); assert(sends == before+1); busy = false;
    command("mode target"); assert(!automatic && role == BUS_TARGET);
    command("auto on"); assert(!automatic && strstr(output, "ERR auto requires"));
    const unsigned target_sends = sends;
    automatic_poll(10000); assert(sends == target_sends);
    report(true, 0x1234, "received");
    accept_frame = false; update_pixels(); assert(pixels_changed);
    accept_frame = true; update_pixels(); assert(!pixels_changed);
    assert(displayed[1] == 0x83); /* Target role plus bit 9 of counter. */
    command("mode controller"); assert(!automatic);
    command("send 42"); assert(sent_counter == 42 && strstr(output, "QUEUED"));
    return 0;
}
