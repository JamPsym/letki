#include "uart.h"
#include "ch32v00x.h"

#define TX_CAPACITY 256U
static uint8_t tx[TX_CAPACITY];
static unsigned head, tail;
static uint32_t errors, dropped;

void uart_init(void)
{
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
    USART_Cmd(USART1, ENABLE);
}

bool uart_write(const char *text)
{
    unsigned length = 0;
    while (text[length]) {
        if (++length >= TX_CAPACITY) { ++dropped; return false; }
    }
    if (length > TX_CAPACITY - 1U - ((head - tail) & (TX_CAPACITY - 1U))) {
        ++dropped;
        return false;
    }
    while (length--) {
        tx[head] = (uint8_t)*text++;
        head = (head + 1U) & (TX_CAPACITY - 1U);
    }
    return true;
}

void uart_poll(void (*receive)(uint8_t))
{
    const uint16_t status = USART1->STATR;
    /* Reading STATR then DATAR clears receive/error flags. Bad bytes invalidate
       the command rather than executing a silently truncated line. */
    if (status & (USART_STATR_RXNE | USART_STATR_PE | USART_STATR_FE |
                  USART_STATR_NE | USART_STATR_ORE)) {
        const uint8_t byte = (uint8_t)USART1->DATAR;
        if (status & (USART_STATR_PE | USART_STATR_FE | USART_STATR_NE | USART_STATR_ORE)) {
            ++errors;
            receive(0);
        } else receive(byte);
    }
    if (head != tail && (USART1->STATR & USART_STATR_TXE)) {
        USART1->DATAR = tx[tail];
        tail = (tail + 1U) & (TX_CAPACITY - 1U);
    }
}

uint32_t uart_errors(void) { return errors; }
uint32_t uart_dropped(void) { return dropped; }
