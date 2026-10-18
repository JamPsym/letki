#include "ch32v00x.h"
#include "display.h"
#include "swio.h"
#include "uart.h"
#include "frame_bus.h"
#include <string.h>
#ifndef STRIP_TILE
#define STRIP_TILE 0
#endif
#ifndef STRIP_TILES
#define STRIP_TILES 2
#endif
#if !STRIP_TILE
#include "scene.h"
#include "uart_line.h"
static struct scene scene, pending;
static uint32_t committed_revision, last_update;
static bool publish_pending;
static char reply[128];
#if STRIP_TILES>2
static uint8_t batch_tile;
static bool batch_active;
#endif
#else
static struct strip_frame received_frame;
static bool publish_pending;
static uint16_t relay_pending;
static bool relay_valid;
static char receiver_reply[128];
static uint32_t last_received;
#endif
static volatile uint32_t milliseconds;
static uint8_t scan_fraction;
static uint32_t accepted, failed;
static uint16_t sequence;
#if !STRIP_TILE
static uint32_t last_attempt;
#endif

static void emit(const char *s)
{
    swio_write(s);
#if !STRIP_TILE
    uart_write(s);
#endif
}
static void report(bool success, const struct strip_frame *frame)
{
    if (!success) {
        ++failed;
#if !STRIP_TILE && STRIP_TILES>2
        batch_active=false;
#endif
        return;
    }
    ++accepted;
#if STRIP_TILE
    received_frame=*frame;
    last_received=milliseconds;
    sequence=frame->sequence; publish_pending=true;
#else
    (void)frame;
#if STRIP_TILES>2
    /* A whole scene advances only after all receiver CRC replies match.
       Receivers publish on arrival; their scan clocks are not synchronized. */
    if (pending.revision!=scene.revision) { batch_active=false; return; }
    if (++batch_tile<STRIP_TILES) return;
    batch_active=false;
#endif
    /* A newer UART/SWIO command wins over an older in-flight snapshot. */
    if (pending.revision==scene.revision) {
        scene=pending; committed_revision=scene.revision;
        publish_pending=true;
    }
    last_update=milliseconds;
#endif
}
#if !STRIP_TILE
static void command(char key)
{
    if (!scene_editing() && (key=='s' || key=='h' || key=='?')) {
        char line[2]={key,0};
        const char *s=scene_command(&scene,line,milliseconds,uart_errors(),uart_dropped(),reply);
        if (s) emit(s);
        return;
    }
    uint32_t revision=scene.revision;
    const char *s=scene_key(&scene,(uint8_t)key);
    if (s) emit(s);
    else if (revision!=scene.revision) {
        scene_status(&scene,milliseconds,uart_errors(),uart_dropped(),reply); emit(reply);
    }
}
static void controls(void)
{
    uint16_t byte;
    if (uart_read(&byte)) {
        if (byte&(UART_RX_INVALID|UART_RX_GAP)) uart_line_error();
        if (!(byte&UART_RX_INVALID)) {
            enum uart_line_result result=uart_line_feed((uint8_t)byte);
            if (result==UART_LINE_READY) {
                const char *s=scene_command(&scene,uart_line_text(),milliseconds,uart_errors(),uart_dropped(),reply);
                if (s) emit(s);
            } else if (result==UART_LINE_INVALID || result==UART_LINE_TOO_LONG)
                emit("ERR invalid UART line; unchanged\r\n");
            else if (result==UART_LINE_CANCELLED) emit("UART draft cancelled\r\n");
        }
    }
    swio_poll(command);
}
static void controller(uint32_t now)
{
    if (frame_bus_busy() || publish_pending) return;
#if STRIP_TILES>2
    if (batch_active && pending.revision!=scene.revision) batch_active=false;
    if (!batch_active) {
#endif
    bool changed=scene.revision!=committed_revision;
    bool due=(uint32_t)(now-last_update)>=scene.interval;
    /* A held frame still refreshes the receiver heartbeat every 500 ms. */
    if (!changed && !due && (uint32_t)(now-last_attempt)<500) return;
    if ((uint32_t)(now-last_attempt)<10) return;
    pending=scene;
    if (!changed && due) scene_next(&pending);
    else scene_render(&pending);
#if STRIP_TILES>2
        batch_tile=1; batch_active=true; ++sequence;
    }
    struct strip_frame frame={.sequence=sequence,.brightness=scene_brightness(&pending),.flags=pending.paused};
    scene_tile(frame.pixels,&pending,batch_tile,STRIP_TILES*8U);
    if (frame_bus_send_to(&frame,now,(uint8_t)(0x31U+batch_tile))) last_attempt=now;
#else
    struct strip_frame frame={.sequence=++sequence,.brightness=scene_brightness(&pending),.flags=pending.paused};
    memcpy(frame.pixels,pending.pixels+8,8);
    if (frame_bus_send(&frame,now)) last_attempt=now;
#endif
}
#else
static char *append_receiver(char *p, const char *s) { while(*s) *p++=*s++; return p; }
static char *number_receiver(char *p, uint32_t n)
{
    char digits[10]; unsigned used=0;
    do { digits[used++]=(char)('0'+n%10); n/=10; } while(n);
    while(used) *p++=digits[--used];
    return p;
}
static void command(char key)
{
    if (key=='s') {
        char *p=append_receiver(receiver_reply,"strip_right seq="); p=number_receiver(p,sequence);
        p=append_receiver(p," ok="); p=number_receiver(p,accepted);
        p=append_receiver(p," fail="); p=number_receiver(p,failed);
        p=append_receiver(p," link="); p=number_receiver(p,accepted && (uint32_t)(milliseconds-last_received)<1500);
        p=append_receiver(p," uart_errors="); p=number_receiver(p,uart_errors());
        p=append_receiver(p," tx_dropped="); p=number_receiver(p,uart_dropped());
        p=append_receiver(p,"\r\n"); *p=0; swio_write(receiver_reply);
    }
    if (key=='h' || key=='?') swio_write("Control text/mode/speed/brightness through the left board UART\r\n");
}
static void controls(void)
{
    /* Retain one byte if the nonblocking TX queue is full. Never inject logs
       into the PC reply path and never interpret relayed ASCII as commands. */
    if (!relay_valid) relay_valid=uart_read(&relay_pending);
    if (relay_valid && uart_tx_free()) {
        if (!(relay_pending&(UART_RX_INVALID|UART_RX_GAP))) {
            char text[2]={(char)(uint8_t)relay_pending,0};
            if (text[0]) uart_write(text);
        }
        relay_valid=false;
    }
    swio_poll(command);
}
#endif
static void publish(void)
{
    if (!publish_pending) return;
#if STRIP_TILE
    display_brightness(received_frame.brightness);
    if (display_present(received_frame.pixels)) publish_pending=false;
#else
    display_brightness(scene_brightness(&scene));
    if (display_present(scene.pixels)) publish_pending=false;
#endif
}
#ifndef STRIP_INTERRUPT
#define STRIP_INTERRUPT __attribute__((interrupt("WCH-Interrupt-fast")))
#endif
void SysTick_Handler(void) STRIP_INTERRUPT;
void SysTick_Handler(void)
{
    SysTick->SR=0;
    if (++scan_fraction==2) { scan_fraction=0; ++milliseconds; }
    display_tick();
}
void TIM2_IRQHandler(void) STRIP_INTERRUPT;
void TIM2_IRQHandler(void) { display_unblank(); }
int main(void)
{
    SystemCoreClockUpdate(); display_init();
#if !STRIP_TILE
    scene_init(&scene); uart_line_init();
#endif
    uart_init(); frame_bus_init(STRIP_TILE!=0);
    SysTick->CTLR=0; SysTick->CNT=0; SysTick->CMP=SystemCoreClock/2000U-1U; SysTick->SR=0;
    NVIC_EnableIRQ(SysTick_IRQn); NVIC_EnableIRQ(TIM2_IRQn);
    SysTick->CTLR=0xfU; __enable_irq(); swio_init();
    emit(STRIP_TILE ? "LETKI interfaces ready. strip right; I2C pixels; UART reply relay\r\n" :
                     "Letki v3 SWIO ready. strip left; UART 115200 8N1\r\n");
    for (;;) {
        uart_poll(); controls(); frame_bus_poll(milliseconds,report); publish();
#if !STRIP_TILE
        controller(milliseconds);
#endif
    }
}
