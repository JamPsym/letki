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
int main(void)
{
    for(unsigned i=0;i<200;++i) SysTick_Handler();
    assert(milliseconds==100 && ticks==200); TIM2_IRQHandler(); assert(unblanks==1);
#if !STRIP_TILE
    scene_init(&scene); uart_line_init();
    controller(100); assert(sends==1 && pending.offset==0);
    struct scene before=scene; report(false,&sent); busy=false; assert(!memcmp(&before,&scene,sizeof scene));
    controller(200); assert(sends==2 && pending.offset==0);
    report(true,&sent); busy=false; assert(publish_pending);
    display_ready=false; publish(); assert(publish_pending);
    display_ready=true; publish(); assert(!publish_pending && !memcmp(shown,scene.pixels,8));
    milliseconds=300; controller(300); assert(pending.offset==1);
    uart_line("t NOWY TEKST\r\n"); assert(scene.offset==0);
    struct scene newer=scene; report(true,&sent); busy=false;
    assert(!memcmp(&newer,&scene,sizeof scene)); /* In-flight snapshot cannot undo a new command. */
    controller(310); assert(pending.offset==0); report(true,&sent); busy=false; publish();
    uart_line("m scroll\n"); assert(scene.mode==SCENE_SCROLL);
    uart_line("p\n"); assert(scene.paused);
    controller(320); assert(sent.flags==1); report(true,&sent); busy=false; publish();
    uart_line("b 25\n"); controller(330); assert(sent.brightness==25);
    report(true,&sent); busy=false; publish(); assert(brightness==25);
    uart_line("ping token\n"); assert(strstr(output,"PONG token\r\n"));
    before=scene; uart_line("words with a inside\n"); assert(!memcmp(&before,&scene,sizeof scene));
    command('t'); command(' '); command('s'); command('h'); command('\n');
    assert(wcsstr(message_text(),L"SH")); /* Status/help letters remain text inside SWIO edits. */
    uart_line("m fall\n"); uart_line("b 40\n");
    milliseconds=400; controller(400);
    assert(sent.brightness==scene_brightness(&pending) && sent.brightness<40);
    report(true,&sent); busy=false; publish(); assert(brightness==sent.brightness);
    before=scene; milliseconds=500; controller(500); report(false,&sent); busy=false;
    assert(!memcmp(&before,&scene,sizeof scene)); /* Failed transport freezes pulse too. */
    controller(510); uint8_t retry_brightness=sent.brightness;
    report(true,&sent); busy=false; publish(); assert(brightness==retry_brightness);
    uart_line("e off\n"); controller(520); assert(sent.brightness==40);
    report(true,&sent); busy=false; publish(); assert(brightness==40);
#else
    const char *reply_text="OK text updated\r\nPONG token\r\n";
    for(unsigned i=0;reply_text[i];++i) input[input_used++]=(uint8_t)reply_text[i];
    free_tx=0; controls(); assert(relay_valid && input_read==1 && !output_used);
    free_tx=127;
    while(input_read<input_used || relay_valid) controls();
    assert(!strcmp(output,reply_text));
    size_t n=output_used; command('s'); command('h'); assert(output_used==n);
    struct strip_frame frame={.sequence=22,.brightness=25,.pixels={1,2,3,4,5,6,7,8}};
    report(true,&frame); display_ready=false; publish(); assert(publish_pending);
    display_ready=true; publish(); assert(!publish_pending && brightness==25 && !memcmp(shown,frame.pixels,8));
    report(false,&frame); assert(!publish_pending && sequence==22);
    accepted=failed=UINT32_MAX; sequence=65535; command('s');
    assert(strlen(receiver_reply)<127 && strstr(receiver_reply,"4294967295"));
#endif
    printf("Strip app role=%d: timing, controls, snapshot/ack handling and receiver relay passed\n",STRIP_TILE);
}
