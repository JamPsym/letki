#include <assert.h>
#include <stdio.h>
#include <string.h>
#define main pong_firmware_main
#define PONG_INTERRUPT
#include "../firmware/pingpong-demo/User/main.c"
#undef main

MockSysTick fake_systick;
uint32_t SystemCoreClock = 48000000;
static bool busy, accept_display = true;
static uint16_t sent;
static unsigned sends, ticks, unblanks;
static uint8_t displayed[8];
static char output[128];
void SystemCoreClockUpdate(void) {}
void NVIC_EnableIRQ(unsigned i) { (void)i; }
void __enable_irq(void) {}
void display_init(void) {}
void display_tick(void) { ++ticks; }
void display_unblank(void) { ++unblanks; }
void display_brightness(uint8_t b) { (void)b; }
uint8_t display_brightness_get(void) { return 100; }
bool display_present(const uint8_t p[8]) { if (!accept_display) return false; memcpy(displayed,p,8); return true; }
void swio_init(void) {}
void swio_poll(void (*fn)(char)) { (void)fn; }
bool swio_write(const char *s) { assert(strlen(s) < sizeof output); strcpy(output,s); return true; }
void bus_init(enum bus_mode mode) { (void)mode; }
bool bus_busy(void) { return busy; }
bool bus_send(uint16_t p, uint32_t now) { (void)now; if (busy) return false; sent=p; ++sends; busy=true; return true; }
void bus_poll(uint32_t now, void (*fn)(bool,uint16_t,const char *)) { (void)now; (void)fn; }

int main(void)
{
    for (unsigned i=0;i<200;i++) SysTick_Handler();
    assert(milliseconds==100 && ticks==200);
    TIM2_IRQHandler(); assert(unblanks==1);
    if (!PONG_TILE) {
        controller_poll(99); assert(!sends);
        controller_poll(100); assert(sends==1 && sent==0 && !state.seen);
        controller_poll(500); assert(sends==1); /* Pending request never overlaps. */
        report(true,0,"reply CRC"); busy=false; assert(next_phase==1);
        controller_poll(200); assert(sent==1);
        report(false,1,"NACK"); busy=false;
        assert(state.phase==0 && next_phase==1 && state.failed==1);
        controller_poll(300); assert(sent==1); /* Retry the same phase. */
        report(true,1,"reply CRC"); busy=false;
        command('p'); controller_poll(400); assert(sent & PONG_PAUSED);
        report(true,sent,"reply CRC"); busy=false; uint16_t held=state.phase;
        controller_poll(500); assert((sent & ~PONG_PAUSED)==held);
        report(true,sent,"reply CRC"); busy=false;
        command('r'); controller_poll(600); assert(!(sent & PONG_PAUSED));
        report(true,sent,"reply CRC"); busy=false; assert(next_phase==held+1);
        busy=true; command('0'); controller_poll(700); assert(reset_requested);
        busy=false; controller_poll(700); assert(sent==0 && !reset_requested);
        for(unsigned i=0;i<40;i++) command('+');
        assert(interval==50);
        for(unsigned i=0;i<40;i++) command('-');
        assert(interval==500);
    } else {
        controller_poll(10000); assert(!sends);
        command('p'); command('0'); command('+'); assert(!paused && !reset_requested && interval==100);
        report(true,PONG_PAUSED|9,"received"); assert(state.paused && state.phase==9);
        uint16_t held=state.phase; report(true,PONG_PHASES,"received"); assert(state.phase==held && state.fault);
    }
    report(true,8,"received"); accept_display=false; publish_frame(milliseconds); assert(dirty);
    accept_display=true; publish_frame(milliseconds); assert(!dirty);
    uint8_t before[8]; memcpy(before,displayed,8);
    publish_frame(milliseconds+PONG_TIMEOUT_MS); assert(displayed[7]&1U);
    for(unsigned x=0;x<7;x++) assert(displayed[x]==before[x]);
    state.accepted=state.failed=UINT32_MAX; command('s'); assert(strstr(output,"4294967295"));
    command('h'); assert(strstr(output,"left controls"));
    printf("Pong app tile=%d: IRQ timing, acknowledgement/retry/pause/reset/speed and display backpressure passed\n",PONG_TILE);
}
