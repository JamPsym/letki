#include "ch32v00x.h"
#include "display.h"
#include "text.h"
#include "swio.h"
#include "message.h"
#include "speed.h"
#include "frame_input.h"
#include "uart.h"
#include "uart_line.h"
#include "brightness.h"
#include <string.h>

#define SCROLL_STEP_MS 75U
static const wchar_t message[] = L" ZOBACZ ADAŚ DZIAŁA ";
static volatile uint32_t milliseconds;
static uint8_t scan_fraction;
static uint32_t scroll_step_ms = SCROLL_STEP_MS;
static bool paused;
static bool message_changed;
static bool arm_pending, resume_clock;
static bool single_cycle, cycle_finished;
static bool host_frames;
static char response[128];

static void emit(const char *text)
{
    swio_write(text);
    uart_write(text);
}

static char *append(char *out, const char *text)
{
    while (*text) *out++ = *text++;
    return out;
}

static char *decimal(char *out, uint32_t value)
{
    char digits[10];
    unsigned count = 0;
    do {
        digits[count++] = (char)('0' + value % 10U);
        value /= 10U;
    } while (value);
    while (count) *out++ = digits[--count];
    return out;
}

static void status(void)
{
    /* Foreground-only formatter; keep the response off the small stack. */
    char *out = response;
    const char *label = "speed_ms=";
    while (*label) *out++ = *label++;
    out = decimal(out, scroll_step_ms);
    label = " paused=";
    while (*label) *out++ = *label++;
    *out++ = paused ? '1' : '0';
    label = " uptime_ms=";
    while (*label) *out++ = *label++;
    out = decimal(out, milliseconds);
    out = append(out, " uart_errors=");
    out = decimal(out, uart_errors());
    out = append(out, " tx_dropped=");
    out = decimal(out, uart_dropped());
    out = append(out, " brightness_pct=");
    out = decimal(out, display_brightness_get());
    *out++ = '\r';
    *out++ = '\n';
    *out = '\0';
    emit(response);
}

static void help(void)
{
    emit("+ faster; - slower; p pause; r resume; 0 reset; s status\r\n");
    emit("t TEXT; v MS; b 0..100; a arm; f 16hex; UART ping TOKEN\r\n");
}

static void command(char key)
{
    if (message_editing())
    {
        switch (message_feed((uint8_t)key))
        {
            case MESSAGE_APPLIED:
                message_changed = true;
                paused = false;
                host_frames = false;
                single_cycle = cycle_finished = false;
                emit("OK text updated\r\n");
                break;
            case MESSAGE_CANCELLED: emit("Text cancelled\r\n"); break;
            case MESSAGE_INVALID: emit("ERR invalid UTF-8; text unchanged\r\n"); break;
            case MESSAGE_TOO_LONG: emit("ERR max 64 characters; text unchanged\r\n"); break;
            default: break;
        }
        return;
    }
    if (speed_editing())
    {
        switch (speed_feed((uint8_t)key, &scroll_step_ms))
        {
            case SPEED_APPLIED: emit("OK speed updated\r\n"); break;
            case SPEED_INVALID: emit("ERR speed must be 10..500 ms\r\n"); break;
            case SPEED_CANCELLED: emit("Speed cancelled\r\n"); break;
            default: break;
        }
        return;
    }
    if (brightness_editing())
    {
        uint8_t percent = display_brightness_get();
        switch (brightness_feed((uint8_t)key, &percent)) {
            case BRIGHTNESS_APPLIED:
                display_brightness(percent); emit("OK brightness updated\r\n"); break;
            case BRIGHTNESS_INVALID: emit("ERR brightness must be 0..100; unchanged\r\n"); break;
            case BRIGHTNESS_CANCELLED: emit("Brightness cancelled\r\n"); break;
            default: break;
        }
        return;
    }
    if (frame_editing())
    {
        static uint8_t pixels[8];
        switch (frame_feed((uint8_t)key, pixels))
        {
            case FRAME_APPLIED:
                if (display_present(pixels))
                {
                    host_frames = true;
                    message_changed = arm_pending = resume_clock = false;
                    emit("FRAME\r\n");
                }
                else emit("BUSY\r\n");
                break;
            case FRAME_INVALID: emit("ERR frame needs 16 hex digits\r\n"); break;
            case FRAME_CANCELLED: emit("Frame cancelled\r\n"); break;
            default: break;
        }
        return;
    }
    switch (key)
    {
        case 'b': brightness_begin(); return;
        case 'f': frame_begin(); return;
        case 'v': speed_begin(); return;
        case 'a':
            host_frames = false;
            paused = single_cycle = true;
            cycle_finished = false;
            message_changed = arm_pending = true;
            return;
        case 't':
            message_begin();
            emit("Text: type UTF-8 then Enter (max 64); Esc cancels\r\n");
            return;
        case '+': if (scroll_step_ms > 10U) scroll_step_ms -= 5U; break;
        case '-': if (scroll_step_ms < 500U) scroll_step_ms += 5U; break;
        case 'p': paused = true; break;
        case 'r':
            if (cycle_finished) { message_changed = true; cycle_finished = false; }
            paused = false; resume_clock = true; break;
        case '0':
            display_brightness(100);
            scroll_step_ms = SCROLL_STEP_MS;
            paused = single_cycle = cycle_finished = false;
            host_frames = false;
            message_changed = resume_clock = true;
            break;
        case 's': break;
        case '?': case 'h':
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
    if (!strcmp(line, "ping") || !strncmp(line, "ping ", 5))
    {
        const size_t length = strlen(line);
        for (size_t i = 0; i < length; ++i)
            if ((uint8_t)line[i] > 126U || length > 79U)
            { emit("ERR ping needs at most 79 ASCII bytes\r\n"); return; }
        char *out = append(response, "PONG");
        out = append(out, line + 4);
        *out++ = '\r'; *out++ = '\n'; *out = 0;
        emit(response);
        return;
    }
    /* UART drafts never enter the SWIO byte parser. A completed UART command
       also cannot finish, cancel or corrupt an in-progress SWIO edit. */
    if (message_editing() || speed_editing() || frame_editing() || brightness_editing())
    { emit("ERR busy; finish or cancel SWIO edit\r\n"); return; }
    if (line[1] == 0 && strchr("+-pr0sah?", line[0]))
    { command(line[0]); return; }
    if ((line[0] == 't' && (line[1] == ' ' || line[1] == 0)) ||
        (line[0] == 'v' && (line[1] == ' ' || line[1] == 0)) ||
        (line[0] == 'b' && (line[1] == ' ' || line[1] == 0)) || line[0] == 'f')
    {
        for (size_t i = 0; line[i]; ++i) command(line[i]);
        command('\n');
        return;
    }
    emit("ERR unknown command; use t TEXT or h\r\n");
}

void SysTick_Handler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void SysTick_Handler(void)
{
    SysTick->SR = 0;
    if (++scan_fraction == 2U) { scan_fraction = 0; ++milliseconds; }
    display_tick();
}
void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void TIM2_IRQHandler(void) { display_unblank(); }

int main(void)
{
    SystemCoreClockUpdate();
    display_init();
    message_init(message);
    uint8_t frame[8];
    size_t offset = 0;
    text_frame(frame, message_text(), message_length(), offset);
    display_present(frame);
    /* Initialize UART before enabling scan interrupts: SDK setup has deeper
       calls than the bounded RX ISR and foreground transport operations. */
    uart_line_init();
    uart_init();

    SysTick->CTLR = 0;
    SysTick->CNT = 0;
    SysTick->CMP = SystemCoreClock / 2000U - 1U;
    SysTick->SR = 0;
    NVIC_EnableIRQ(SysTick_IRQn);
    NVIC_EnableIRQ(TIM2_IRQn);
    SysTick->CTLR = 0xFU;
    __enable_irq();
    swio_init();
    emit("Letki v3 SWIO ready. h=help\r\n");
    emit("Letki v3 USART ready. 115200 8N1; Enter sends\r\n");

    uint32_t previous = 0;
    uint32_t last_log = 0;
    while (1)
    {
        uart_poll();
        uint16_t received;
        if (uart_read(&received))
        {
            if (received & (UART_RX_INVALID | UART_RX_GAP)) uart_line_error();
            if (!(received & UART_RX_INVALID))
                switch (uart_line_feed((uint8_t)received))
                {
                    case UART_LINE_READY: uart_command(uart_line_text()); break;
                    case UART_LINE_INVALID: emit("ERR invalid UART line; unchanged\r\n"); break;
                    case UART_LINE_TOO_LONG: emit("ERR UART line too long; unchanged\r\n"); break;
                    case UART_LINE_CANCELLED: emit("UART draft cancelled\r\n"); break;
                    default: break;
                }
        }
        swio_poll(command);
        const uint32_t now = milliseconds;
        if (resume_clock)
        {
            previous = now;
            resume_clock = false;
        }
        if (message_changed)
        {
            if (single_cycle) text_frame_once(frame, message_text(), message_length(), 0);
            else text_frame(frame, message_text(), message_length(), 0);
            if (display_present(frame))
            {
                offset = 0;
                previous = now;
                message_changed = false;
                if (arm_pending)
                {
                    emit("ARMED\r\n");
                    arm_pending = false;
                }
            }
            continue;
        }
        if ((uint32_t)(now - last_log) >= 5000U)
        {
            status();
            last_log = now;
        }
        if (host_frames) continue;
        if (paused || (uint32_t)(now - previous) < scroll_step_ms)
            continue;
        const size_t columns = text_columns(message_text(), message_length());
        const size_t next = single_cycle ? offset + 1U :
                           (columns ? (offset + 1U) % columns : 0);
        if (single_cycle) text_frame_once(frame, message_text(), message_length(), next);
        else text_frame(frame, message_text(), message_length(), next);
        if (display_present(frame))
        {
            offset = next;
            previous = now;
            if (single_cycle && offset >= columns)
            {
                paused = cycle_finished = true;
            }
        }
    }
}
