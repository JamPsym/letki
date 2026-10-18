#include "uart.h"
#include "ch32v00x.h"

#define RX_CAPACITY 64U
#define TX_CAPACITY 128U
static uint16_t rx[RX_CAPACITY];
static volatile uint8_t rx_head, rx_tail;
static bool rx_gap;
static volatile uint32_t errors;
static uint8_t tx[TX_CAPACITY], tx_head, tx_tail;
static uint32_t dropped;

void uart_init(void)
{
    rx_head = rx_tail = tx_head = tx_tail = 0;
    rx_gap = false;
    errors = dropped = 0;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOD | RCC_APB2Periph_USART1 |
                          RCC_APB2Periph_AFIO, ENABLE);
    GPIO_PinRemapConfig(GPIO_PartialRemap1_USART1, DISABLE);
    GPIO_PinRemapConfig(GPIO_PartialRemap2_USART1, DISABLE);
    GPIO_InitTypeDef gpio = {0};
    gpio.GPIO_Pin = GPIO_Pin_5;
    gpio.GPIO_Speed = GPIO_Speed_30MHz;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOD, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_6;
    gpio.GPIO_Mode = GPIO_Mode_IPU;
    GPIO_Init(GPIOD, &gpio);
    USART_InitTypeDef config = {0};
    config.USART_BaudRate = 115200;
    config.USART_WordLength = USART_WordLength_8b;
    config.USART_StopBits = USART_StopBits_1;
    config.USART_Parity = USART_Parity_No;
    config.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    config.USART_Mode = USART_Mode_Tx | USART_Mode_Rx;
    USART_Init(USART1, &config);
    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);
    NVIC_EnableIRQ(USART1_IRQn);
    USART_Cmd(USART1, ENABLE);
}

#ifndef UART_INTERRUPT
#define UART_INTERRUPT __attribute__((interrupt("WCH-Interrupt-fast")))
#endif
void USART1_IRQHandler(void) UART_INTERRUPT;
void USART1_IRQHandler(void)
{
    const uint16_t status = USART1->STATR;
    if (!(status & (USART_STATR_RXNE | USART_STATR_PE | USART_STATR_FE |
                    USART_STATR_NE | USART_STATR_ORE))) return;
    /* STATR then DATAR clears receive/error flags. Never parse or print here. */
    uint16_t received = (uint8_t)USART1->DATAR;
    if (status & (USART_STATR_PE | USART_STATR_FE | USART_STATR_NE | USART_STATR_ORE))
    {
        ++errors;
        received |= UART_RX_INVALID;
    }
    const uint8_t next = (rx_head + 1U) & (RX_CAPACITY - 1U);
    if (next == rx_tail)
    {
        ++errors;
        rx_gap = true;
        return;
    }
    /* Attach any lost-byte marker to the next queued byte, after the older
       prefix. It poisons that whole line rather than executing a truncation. */
    if (rx_gap) { received |= UART_RX_GAP; rx_gap = false; }
    rx[rx_head] = received;
    __asm__ volatile ("" ::: "memory");
    rx_head = next;
}

bool uart_read(uint16_t *received)
{
    if (rx_tail == rx_head) return false;
    __asm__ volatile ("" ::: "memory");
    *received = rx[rx_tail];
    __asm__ volatile ("" ::: "memory");
    rx_tail = (rx_tail + 1U) & (RX_CAPACITY - 1U);
    return true;
}

uint8_t uart_tx_free(void)
{
    return TX_CAPACITY - 1U - ((tx_head - tx_tail) & (TX_CAPACITY - 1U));
}

bool uart_write(const char *text)
{
    unsigned length = 0;
    while (text[length])
        if (++length >= TX_CAPACITY) { ++dropped; return false; }
    if (length > uart_tx_free())
    {
        ++dropped;
        return false;
    }
    while (length--)
    {
        tx[tx_head] = (uint8_t)*text++;
        tx_head = (tx_head + 1U) & (TX_CAPACITY - 1U);
    }
    return true;
}

void uart_poll(void)
{
    if (tx_head != tx_tail && (USART1->STATR & USART_STATR_TXE))
    {
        USART1->DATAR = tx[tx_tail];
        tx_tail = (tx_tail + 1U) & (TX_CAPACITY - 1U);
    }
}

uint32_t uart_errors(void) { return errors; }
uint32_t uart_dropped(void) { return dropped; }

bool uart_write_bytes(const uint8_t *bytes, unsigned length)
{
    if (length > uart_tx_free()) return false;
    while (length--) {
        tx[tx_head] = *bytes++;
        tx_head = (tx_head + 1U) & (TX_CAPACITY - 1U);
    }
    return true;
}

void uart_set_baud(uint32_t baud)
{
    USART_InitTypeDef config = {0};
    config.USART_BaudRate = baud;
    config.USART_WordLength = USART_WordLength_8b;
    config.USART_StopBits = USART_StopBits_1;
    config.USART_Parity = USART_Parity_No;
    config.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    config.USART_Mode = USART_Mode_Tx | USART_Mode_Rx;
    USART_Init(USART1, &config);
}
