#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "message.h"
#define main strip_firmware_main
#define STRIP_INTERRUPT
#include "../firmware/strip-text/User/main.c"
#undef main

MockSysTick fake_systick;
uint32_t SystemCoreClock=48000000;
static bool busy, display_ready=true;
static unsigned sends, ticks, unblanks;
static uint8_t sent_address;
static uint8_t shown[8], brightness=100;
static struct strip_frame sent;
static uint16_t input[512];
static unsigned input_used, input_read;
static unsigned free_tx=127;
static char output[4096];
static size_t output_used;
void SystemCoreClockUpdate(void) {}
void NVIC_EnableIRQ(unsigned irq) { (void)irq; }
void __enable_irq(void) {}
void display_init(void) {}
void display_tick(void) { ++ticks; }
void display_unblank(void) { ++unblanks; }
void display_brightness(uint8_t value) { brightness=value; }
uint8_t display_brightness_get(void) { return brightness; }
bool display_present(const uint8_t p[8]) { if(!display_ready) return false; memcpy(shown,p,8); return true; }
void swio_init(void) {}
void swio_poll(void (*callback)(char)) { (void)callback; }
bool swio_write(const char *s) { (void)s; return true; }
void uart_init(void) {}
void uart_poll(void) {}
uint32_t uart_errors(void) { return 0; }
uint32_t uart_dropped(void) { return 0; }
uint8_t uart_tx_free(void) { return (uint8_t)free_tx; }
bool uart_write(const char *s) {
    assert(strlen(s)<=free_tx); assert(output_used+strlen(s)<sizeof output);
    strcpy(output+output_used,s); output_used+=strlen(s); return true;
}
bool uart_read(uint16_t *value) { if(input_read==input_used) return false; *value=input[input_read++]; return true; }
void frame_bus_init(bool target) { (void)target; }
bool frame_bus_busy(void) { return busy; }
bool frame_bus_send(const struct strip_frame *frame, uint32_t now) {
    (void)now; if(busy) return false; sent=*frame; busy=true; ++sends; return true;
}
void frame_bus_poll(uint32_t now, void (*callback)(bool,const struct strip_frame *)) { (void)now; (void)callback; }
#if !STRIP_TILE
static void uart_line(const char *s) {
    input_used=input_read=0;
    for(unsigned i=0;s[i];++i) input[input_used++]=(uint8_t)s[i];
    while(input_read<input_used) controls();
}
#endif
bool frame_bus_send_to(const struct strip_frame *frame, uint32_t now, uint8_t address) {
    sent_address=address; return frame_bus_send(frame,now);
}
static void ack(void) { report(true,&sent); busy=false; }
int main(void)
{
    scene_init(&scene); uart_line_init();
    uart_line("t LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM\n"); uart_line("m fall\n");
    for(unsigned tile=1;tile<5;++tile) {
        controller(100+tile); assert(sent_address==0x31+tile);
        uint8_t expected[8]; scene_tile(expected,&pending,tile,40);
        assert(!memcmp(sent.pixels,expected,8));
        assert(sent.brightness==scene_brightness(&pending));
        ack(); assert(publish_pending==(tile==4));
    }
    display_ready=false; publish(); assert(publish_pending);
    display_ready=true; publish(); assert(!publish_pending);
    uint32_t revision=scene.revision;
    milliseconds=200; controller(200); assert(batch_tile==1); ack();
    controller(201); assert(batch_tile==2);
    struct scene held=scene; report(false,&sent); busy=false;
    assert(!memcmp(&held,&scene,sizeof scene) && !batch_active);
    /* Retry all four from the same next phase, never skip the failed tile. */
    for(unsigned tile=1;tile<5;++tile) {
        controller(220+tile); assert(sent_address==0x31+tile && pending.offset==1); ack();
    }
    publish(); assert(scene.offset==1 && scene.revision==revision);
    milliseconds=300; controller(300); ack();
    uart_line("b 20\n");
    controller(320); assert(sent_address==0x32 && pending.brightness==20);
    assert(pending.offset==scene.offset); ack();
    for(unsigned tile=2;tile<5;++tile) { controller(320+tile); ack(); }
    publish(); assert(scene.brightness==20 && brightness==scene_brightness(&scene));
    /* Commands during a last-tile exchange cannot be overwritten by its ACK. */
    milliseconds=400;
    for(unsigned tile=1;tile<5;++tile) {
        controller(400+tile);
        if(tile==4) uart_line("t NOWY TEKST\n");
        ack();
    }
    assert(scene.offset==0 && wcsstr(message_text(),L"NOWY TEKST"));
    assert(!batch_active && !publish_pending);
    puts("Five tiles: addressing, pixel/brightness snapshots, all-ACK commit, failed batch retry, command races and display backpressure passed");
}
