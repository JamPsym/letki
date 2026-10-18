#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ch32v00x.h"
#include "uart.h"
#include "uart_line.h"

USART_TypeDef fake_usart;
void USART1_IRQHandler(void);
static unsigned tx_pin, rx_pin, enabled_irq;
void RCC_APB2PeriphClockCmd(unsigned p, int e) { (void)p; assert(e == ENABLE); }
void GPIO_PinRemapConfig(unsigned p, int e) { (void)p; assert(e == DISABLE); }
void GPIO_Init(void *p, GPIO_InitTypeDef *c)
{
    assert(p == GPIOD);
    if (c->GPIO_Mode == GPIO_Mode_AF_PP) tx_pin = c->GPIO_Pin;
    else { assert(c->GPIO_Mode == GPIO_Mode_IPU); rx_pin = c->GPIO_Pin; }
}
void USART_Init(USART_TypeDef *p, USART_InitTypeDef *c)
{
    assert(p == USART1 && c->USART_BaudRate == 115200);
    assert(c->USART_WordLength == USART_WordLength_8b);
    assert(c->USART_StopBits == USART_StopBits_1 && c->USART_Parity == USART_Parity_No);
    assert(c->USART_HardwareFlowControl == USART_HardwareFlowControl_None);
    assert(c->USART_Mode == (USART_Mode_Tx | USART_Mode_Rx));
}
void USART_ITConfig(USART_TypeDef *p, unsigned i, int e)
{ assert(p == USART1 && i == USART_IT_RXNE && e == ENABLE); }
void USART_Cmd(USART_TypeDef *p, int e) { assert(p == USART1 && e == ENABLE); }
void NVIC_EnableIRQ(unsigned i) { enabled_irq = i; }

static enum uart_line_result feed(const char *text)
{
    enum uart_line_result result = UART_LINE_PENDING;
    for (unsigned i = 0; text[i]; ++i) result = uart_line_feed((uint8_t)text[i]);
    return result;
}
static void receive(uint8_t byte, uint16_t flags)
{
    fake_usart.STATR = USART_STATR_RXNE | flags;
    fake_usart.DATAR = byte;
    USART1_IRQHandler();
}

int main(void)
{
    uart_init(); uart_line_init();
    assert(tx_pin == GPIO_Pin_5 && rx_pin == GPIO_Pin_6 && enabled_irq == USART1_IRQn);
    assert(feed("t zażółć") == UART_LINE_PENDING);
    assert(uart_line_feed('\r') == UART_LINE_READY);
    assert(!strcmp(uart_line_text(), "t zażółć"));
    assert(uart_line_feed('\n') == UART_LINE_PENDING);
    assert(feed("t ą\x7f" "a\n") == UART_LINE_READY);
    assert(!strcmp(uart_line_text(), "t a"));
    assert(feed("t incomplete\x1b") == UART_LINE_CANCELLED);
    assert(feed("s\n") == UART_LINE_READY && !strcmp(uart_line_text(), "s"));
    assert(feed("t bad\x01") == UART_LINE_PENDING);
    assert(uart_line_feed('\n') == UART_LINE_INVALID);
    for (unsigned i = 0; i < UART_LINE_CAPACITY + 10; ++i)
        assert(uart_line_feed('x') == UART_LINE_PENDING);
    assert(uart_line_feed('\n') == UART_LINE_TOO_LONG);
    /* All 64 four-byte characters fit. Character/UTF-8 validation belongs
       to the real message parser, whose original tests remain authoritative. */
    assert(feed("t ") == UART_LINE_PENDING);
    for (unsigned i = 0; i < MESSAGE_MAX_CHARS; ++i)
        assert(feed("\xf0\x9f\x98\x80") == UART_LINE_PENDING);
    assert(uart_line_feed('\n') == UART_LINE_READY);
    assert(strlen(uart_line_text()) == UART_LINE_CAPACITY - 1U);

    uint16_t value;
    assert(!uart_read(&value));
    receive(0xc4, 0);
    assert(uart_read(&value) && value == 0xc4 && !uart_read(&value));
    receive('x', USART_STATR_FE);
    assert(uart_read(&value) && value == ('x' | UART_RX_INVALID));
    assert(uart_errors() == 1);
    /* Overflow markers follow queued prefix bytes; they cannot be cleared
       by a newline that predates the loss. Wrap the FIFO repeatedly. */
    for (unsigned round = 0; round < 3; ++round)
    {
        for (unsigned i = 0; i < 63; ++i) receive((uint8_t)i, 0);
        receive('z', 0);
        for (unsigned i = 0; i < 63; ++i)
            assert(uart_read(&value) && value == i);
        assert(!uart_read(&value));
        receive('\n', 0);
        assert(uart_read(&value) && value == ('\n' | UART_RX_GAP));
        uart_line_error();
        assert(uart_line_feed((uint8_t)value) == UART_LINE_INVALID);
        assert(feed("s\n") == UART_LINE_READY);
    }
    assert(uart_errors() == 4);
    fake_usart.STATR = 0;
    char full[128]; memset(full, 'x', 127); full[127] = 0;
    assert(uart_tx_free() == 127);
    assert(uart_write(full));
    assert(uart_tx_free() == 0);
    assert(!uart_write("BAD") && uart_dropped() == 1);
    uart_poll(); /* Disconnected/busy TX never waits or consumes queued data. */
    assert(uart_tx_free() == 0);
    fake_usart.STATR = USART_STATR_TXE;
    for (unsigned i = 0; i < 127; ++i) { uart_poll(); assert(fake_usart.DATAR == 'x'); }
    assert(uart_tx_free() == 127);
    assert(uart_write("OK\n"));
    uart_poll(); assert(fake_usart.DATAR == 'O');
    uart_poll(); assert(fake_usart.DATAR == 'K');
    uart_poll(); assert(fake_usart.DATAR == '\n');
    assert(uart_dropped() == 1);
    puts("Text UART tests passed: wiring, UTF-8 lines, CRLF, cancellation, RX errors/overflow and nonblocking TX.");
}
