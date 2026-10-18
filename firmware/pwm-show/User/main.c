#include "ch32v00x.h"
#include "display.h"
#include "pwm_show.h"
#include "swio.h"
#include "uart.h"
#include "frame_bus.h"
#include <string.h>
#ifndef STRIP_TILE
#define STRIP_TILE 0
#endif
static volatile uint32_t milliseconds;
static uint8_t fraction, levels[64];
static uint32_t accepted, failed;
static bool publish_pending, generated;
static struct strip_frame local_frame;
#if !STRIP_TILE
#include "uart_line.h"
#include "brightness.h"
#include "speed.h"
static uint32_t interval=40, tick, last_update, last_attempt;
static uint32_t revision=1, committed_revision, batch_revision;
static int8_t choice=-1;
static uint8_t brightness_goal=100, batch_tile;
static bool paused, batch_active;
static bool phase_reply;
static struct strip_frame batch;
static uint16_t sequence;
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
    p = append(p, " brightness_pct="); p = decimal(p, brightness_goal);
    p = append(p, "\r\n"); *p = 0; emit(response);
}
static void help(void)
{
    emit("PWM show: b 0..100; v 10..500; n next; a auto\r\n");
    emit("p/r/0/s; m auto/silk/ripples/comets/lanterns/ladder/daisy; k 0..959; ping TOKEN\r\n");
}
static void command(char key)
{
    if (brightness_editing()) {
        uint8_t percent = brightness_goal;
        switch (brightness_feed((uint8_t)key, &percent)) {
            case BRIGHTNESS_APPLIED:
                brightness_goal=percent; ++revision;
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
        case 'r': paused = false; last_update = milliseconds; break;
        case '+': if (interval > 10) interval = interval >= 15 ? interval-5 : 10; break;
        case '-': if (interval < 500) interval = interval <= 495 ? interval+5 : 500; break;
        case '0': interval = 40; paused = false; tick = 0;
                  brightness_goal=100; ++revision; break;
        case 'n': choice=(int8_t)((pwm_show_scene(tick,choice)+1)%PWM_SHOW_SCENES); tick=0; break;
        case 'a': choice=-1; tick=0; break;
        case 's': status(); return;
        case 'h': case '?':
            help();
            return;
        default: return;
    }
    ++revision; status();
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
    if (!strncmp(line,"k ",2)) {
        const char *p=line+2; unsigned value=0;
        if (!*p) { emit("ERR tick must be 0..959\r\n"); return; }
        for (;*p;++p) {
            if (*p<'0' || *p>'9' || value>95) {
                emit("ERR tick must be 0..959\r\n"); return;
            }
            value=value*10U+(unsigned)(*p-'0');
        }
        if(value>=960) { emit("ERR tick must be 0..959\r\n"); return; }
        tick=value; choice=-1; paused=true; ++revision; phase_reply=true;
        return;
    }
    if (!strncmp(line,"m ",2)) {
        static const char *const names[]={"auto","silk","ripples","comets","lanterns","ladder","daisy"};
        for(unsigned n=0;n<7;++n) if(!strcmp(line+2,names[n])) {
            choice=(int8_t)n-1; tick=0; ++revision; emit("OK mode updated\r\n"); return;
        }
        emit("ERR mode\r\n"); return;
    }
    if (line[1] == 0 && strchr("+-pr0sh?na", line[0])) { command(line[0]); return; }
    if ((line[0] == 'b' || line[0] == 'v') && (line[1] == 0 || line[1] == ' ')) {
        for (unsigned i = 0; line[i]; ++i) command(line[i]);
        command('\n'); return;
    }
    emit("ERR visual demo supports b/v/p/r/0/s/h\r\n");
}

static void controls(void)
{
    uint16_t received;
    if (uart_read(&received)) {
        if(received&(UART_RX_INVALID|UART_RX_GAP)) uart_line_error();
        if(!(received&UART_RX_INVALID)) switch(uart_line_feed((uint8_t)received)) {
            case UART_LINE_READY: uart_command(uart_line_text()); break;
            case UART_LINE_INVALID: case UART_LINE_TOO_LONG: emit("ERR invalid UART line; unchanged\r\n"); break;
            case UART_LINE_CANCELLED: emit("UART draft cancelled\r\n"); break;
            default: break;
        }
    }
    swio_poll(command);
}
#else
static uint16_t relay_byte;
static bool relay_valid;
static void command(char key)
{
    if(key=='s') swio_write("PWM receiver ready; tick/scene packets; UART relay\r\n");
}
static void controls(void)
{
    if(!relay_valid) relay_valid=uart_read(&relay_byte);
    if(relay_valid && uart_tx_free()) {
        if(!(relay_byte&(UART_RX_INVALID|UART_RX_GAP))) {
            char text[2]={(char)(uint8_t)relay_byte,0}; if(text[0]) uart_write(text);
        }
        relay_valid=false;
    }
    swio_poll(command);
}
#endif
static uint32_t frame_tick(const struct strip_frame *f)
{
    return (uint32_t)f->pixels[0]|((uint32_t)f->pixels[1]<<8)|((uint32_t)f->pixels[2]<<16)|((uint32_t)f->pixels[3]<<24);
}
static void report(bool success, const struct strip_frame *frame)
{
    if(!success) {
        ++failed;
#if !STRIP_TILE
        batch_active=false;
#endif
        return;
    }
    ++accepted;
#if !STRIP_TILE
    if(batch_revision!=revision) { batch_active=false; return; }
    if(++batch_tile<5) return;
    tick=frame_tick(frame); committed_revision=revision;
    last_update=milliseconds; batch_active=false;
    if(phase_reply) {
        char *p=append(response,"OK tick "); p=decimal(p,tick);
        p=append(p,"\r\n"); *p=0; emit(response); phase_reply=false;
    }
#endif
    local_frame=*frame; generated=false; publish_pending=true;
}
#if !STRIP_TILE
static void controller(uint32_t now)
{
    if(frame_bus_busy() || publish_pending) return;
    if(batch_active && batch_revision!=revision) batch_active=false;
    if(!batch_active) {
        bool changed=revision!=committed_revision;
        if(!changed && (uint32_t)(now-last_update)<(paused?500U:interval)) return;
        if((uint32_t)(now-last_attempt)<10) return;
        uint32_t next=changed || paused?tick:tick+1;
        memset(&batch,0,sizeof batch); batch.sequence=++sequence;
        batch.brightness=brightness_goal; batch.flags=paused;
        for(unsigned n=0;n<4;++n) batch.pixels[n]=(uint8_t)(next>>(8*n));
        batch.pixels[4]=(uint8_t)(choice+1);
        batch_revision=revision; batch_tile=1; batch_active=true;
    }
    if(frame_bus_send_to(&batch,now,(uint8_t)(0x31U+batch_tile))) last_attempt=now;
}
#endif
static void publish(void)
{
    if(!publish_pending) return;
    if(!generated) {
        pwm_show_tile(levels,frame_tick(&local_frame),STRIP_TILE,5,(int)local_frame.pixels[4]-1);
        generated=true;
    }
    display_brightness(local_frame.brightness);
    if(display_present_levels(levels)) publish_pending=false;
}
#ifndef PWM_SHOW_INTERRUPT
#define PWM_SHOW_INTERRUPT __attribute__((interrupt("WCH-Interrupt-fast")))
#endif
void SysTick_Handler(void) PWM_SHOW_INTERRUPT;
void SysTick_Handler(void)
{
    SysTick->SR=0;
    if(++fraction==2) { fraction=0; ++milliseconds; }
    display_tick();
}
void TIM2_IRQHandler(void) PWM_SHOW_INTERRUPT;
void TIM2_IRQHandler(void) { display_unblank(); }
int main(void)
{
    SystemCoreClockUpdate(); display_init(); uart_init();
#if !STRIP_TILE
    uart_line_init();
#endif
    frame_bus_init(STRIP_TILE!=0);
    SysTick->CTLR=0; SysTick->CNT=0; SysTick->CMP=SystemCoreClock/2000U-1U; SysTick->SR=0;
    NVIC_EnableIRQ(SysTick_IRQn); NVIC_EnableIRQ(TIM2_IRQn);
    SysTick->CTLR=0xfU; __enable_irq(); swio_init();
    swio_write("Letki PWM show ready; phase chain; preview candidate\r\n");
    for(;;) {
        uart_poll(); controls(); frame_bus_poll(milliseconds,report); publish();
#if !STRIP_TILE
        controller(milliseconds);
#endif
    }
}
