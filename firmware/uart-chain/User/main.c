#include "ch32v00x.h"
#include "chain.h"
#include "display.h"
#include "swio.h"
#include "uart.h"

static struct chain_node node;
static volatile uint32_t milliseconds;
static uint8_t fraction, frame[8];
static char response[128];

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
    char *p = append(response,"CHAIN position="); p = decimal(p,node.last.hops);
    p = append(p," counter="); p = decimal(p,node.last.counter);
    p = append(p," ok="); p = decimal(p,node.accepted);
    p = append(p," bad="); p = decimal(p,node.rejected);
    p = append(p," drop="); p = decimal(p,node.dropped);
    p = append(p," uart="); p = decimal(p,uart_errors());
    p = append(p," txdrop="); p = decimal(p,uart_dropped());
    p = append(p,"\r\n"); *p = 0;
    swio_write(response);
}
static void command(char key)
{
    if (key == 's') status();
    else if (key == 'h') swio_write("UART chain: PC TX -> left RX; right TX -> PC RX. s=status\r\n");
}
void SysTick_Handler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void SysTick_Handler(void)
{
    SysTick->SR = 0;
    if (++fraction == 2U) { fraction = 0; ++milliseconds; }
    display_tick();
}
void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void TIM2_IRQHandler(void) { display_unblank(); }

int main(void)
{
    SystemCoreClockUpdate();
    display_init(); uart_init();
    frame[0] = 1; display_present(frame);
    SysTick->CTLR = 0; SysTick->CNT = 0;
    SysTick->CMP = SystemCoreClock/2000U-1U; SysTick->SR = 0;
    NVIC_EnableIRQ(SysTick_IRQn); NVIC_EnableIRQ(TIM2_IRQn);
    SysTick->CTLR = 0xfU; __enable_irq(); swio_init();
    /* Only framed traffic goes on UART; no boot/help/status logs between nodes. */
    swio_write("Letki v3 SWIO ready. Identical UART chain demo\r\n");
    uint32_t previous = 0;
    for (;;) {
        uart_poll();
        if (node.pending && uart_tx_free() >= CHAIN_WIRE_LENGTH && uart_write(node.output))
            node.pending = false;
        uint16_t received;
        if (uart_read(&received)) chain_feed(&node,received,uart_errors()+uart_dropped());
        swio_poll(command);
        if (node.dirty) {
            for (unsigned col = 0; col < 8; ++col) {
                frame[col] = (col == 0 ? 1U : 0U) |
                    ((node.last.hops & (1U<<col)) ? 2U : 0U) |
                    ((node.last.counter & (1U<<col)) ? 0x40U : 0U) |
                    ((node.last.counter & (1U<<(col+8))) ? 0x80U : 0U);
            }
            if (display_present(frame)) node.dirty = false;
        }
        if ((uint32_t)(milliseconds-previous) >= 2000U) {
            previous = milliseconds; status();
        }
    }
}
