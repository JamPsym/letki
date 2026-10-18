#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "pwm_show.h"
#define main strip_firmware_main
#define PWM_SHOW_INTERRUPT
#include "../firmware/pwm-show/User/main.c"
#undef main

MockSysTick fake_systick;
uint32_t SystemCoreClock=48000000;
static bool busy, display_ready=true;
static unsigned sends, ticks, unblanks;
static uint8_t sent_address;
static uint8_t shown[64], brightness=100;
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
bool display_present_levels(const uint8_t p[64]) { if(!display_ready) return false; memcpy(shown,p,64); return true; }
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
#if !STRIP_TILE
static void ack(void) { report(true,&sent); busy=false; }
#endif
int main(void)
{
    for(unsigned n=0;n<200;++n) SysTick_Handler();
    assert(milliseconds==100);TIM2_IRQHandler();assert(unblanks==1);
#if !STRIP_TILE
    uart_line_init();
    for(unsigned tile=1;tile<5;++tile) {
        controller(100+tile);assert(sent_address==0x31+tile && frame_tick(&sent)==0);ack();
        assert(publish_pending==(tile==4));
    }
    display_ready=false;publish();assert(publish_pending);
    display_ready=true;publish();assert(!publish_pending);
    uint8_t expected[64];pwm_show_tile(expected,0,0,5,-1);assert(!memcmp(shown,expected,64));
    uart_line("m daisy\n");assert(choice==5);
    uart_line("b 70\n");
    for(unsigned tile=1;tile<5;++tile) {controller(200+tile);assert(sent.pixels[4]==6 && sent.brightness==70);ack();}
    publish();pwm_show_tile(expected,0,0,5,5);assert(!memcmp(shown,expected,64) && brightness==70);
    milliseconds=300;controller(300);uint32_t held=tick;report(false,&sent);busy=false;
    assert(tick==held && !batch_active);
    for(unsigned tile=1;tile<5;++tile) {controller(320+tile);assert(frame_tick(&sent)==1);ack();}publish();assert(tick==1);
    controller(400);ack();uart_line("m silk\n");controller(420);assert(batch_tile==1 && sent.pixels[4]==1);ack();
    for(unsigned tile=2;tile<5;++tile) {controller(420+tile);ack();}publish();
    uart_line("p\n");held=tick;
    for(unsigned tile=1;tile<5;++tile) {controller(500+tile);ack();}publish();assert(tick==held);
    uart_line("ping TOKEN\n");assert(strstr(output,"PONG TOKEN"));
    uart_line("b 101\n");assert(brightness_goal==70);
    uart_line("m wrong\n");assert(choice==0);
    uart_line("k 959\n");assert(tick==959 && paused && choice==-1 && phase_reply);
    for(unsigned tile=1;tile<5;++tile) {
        controller(600+tile);assert(frame_tick(&sent)==959);ack();
        assert(phase_reply==(tile<4));
    }
    publish();assert(strstr(output,"OK tick 959\r\n"));
    uart_line("k 960\n");assert(tick==959 && !phase_reply);
    uart_line("k -1\n");assert(tick==959);
    uart_line("k 99999999999\n");assert(tick==959);
    uart_line("k \n");assert(tick==959);
    uart_line("k 0\n");controller(700);ack();
    report(false,&sent);busy=false;assert(phase_reply);
    for(unsigned tile=1;tile<5;++tile) {controller(720+tile);ack();}
    publish();assert(!phase_reply && tick==0);
#else
    struct strip_frame receiver={.brightness=70,.pixels={19,0,0,0,6}};
    report(true,&receiver);publish();uint8_t expected[64];pwm_show_tile(expected,19,STRIP_TILE,5,5);
    assert(!memcmp(shown,expected,64) && brightness==70);
#endif
    struct strip_frame f={.sequence=65535,.brightness=70,.pixels={1,2,3,4,6}},decoded={0};
    uint8_t packet[14];strip_encode(packet,&f);assert(strip_decode(packet,14,&decoded));
    assert(!memcmp(&f,&decoded,sizeof f));
    for(unsigned n=0;n<14;++n) for(unsigned bit=0;bit<8;++bit) {
        packet[n]^=(uint8_t)(1U<<bit);assert(!strip_decode(packet,14,&decoded));packet[n]^=(uint8_t)(1U<<bit);
    }
    puts("PWM firmware: phase batches, six scenes, display handoff, CRC, failed-transfer retry and controls passed");
}
