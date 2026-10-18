#include "ch32v00x.h"
#include "clock.h"
#include "display.h"
#include "general.h"
#include "uart.h"
#include <string.h>
#ifndef GENERAL_TILE
#define GENERAL_TILE 0
#endif
static struct lg_node node;
static struct lg_counter counter;
static uint8_t levels[64];
static struct lg_router router;
static bool publish_pending;
extern uint8_t __content_start[], __content_end[];

#include "content_flash.h"
void SysTick_Handler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void SysTick_Handler(void) {
  SysTick->SR = 0;
  uint32_t next = SysTick->CMP + SystemCoreClock / 2000U;
  if ((int32_t)(next - SysTick->CNT) <= 0)
    next = SysTick->CNT + SystemCoreClock / 2000U;
  SysTick->CMP = next;
  display_tick();
}
void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void TIM2_IRQHandler(void) { display_unblank(); }
static void __attribute__((noinline)) initialize(void) {
  SystemCoreClockUpdate();
  display_init();
  uart_init();
  lg_clock_init(GENERAL_TILE == 0);
  struct lg_store storage = {__content_start,
                             (uint16_t)(__content_end - __content_start),
                             erase_content, write_content};
  lg_init(&node, GENERAL_TILE, 5, storage);
  for (unsigned word = 0; word < 2; ++word) {
    uint32_t value = *(const volatile uint32_t *)(0x1ffff7e8U + word * 4);
    for (unsigned b = 0; b < 4; ++b)
      node.uid[word * 4 + b] = (uint8_t)(value >> (24 - b * 8));
  }
  SysTick->CTLR = 0;
  SysTick->CNT = 0;
  SysTick->CMP = SystemCoreClock / 2000U - 1U;
  SysTick->SR = 0;
  NVIC_EnableIRQ(SysTick_IRQn);
  NVIC_EnableIRQ(TIM2_IRQn);
  SysTick->CTLR = 7;
  __enable_irq();
}
int main(void) {
  initialize();
  for (;;) {
    uart_poll();
    lg_clock_session(node.session);
    uint32_t local =
        lg_counter_update(&counter, SysTick->CNT, SystemCoreClock / 1000U);
    node.local_ms = local;
    uint32_t now = lg_clock_poll(local);
    node.clock_age = lg_clock_age(local);
    if (!node.maintenance && !(SysTick->CTLR & 2)) {
      SysTick->CMP = SysTick->CNT + SystemCoreClock / 2000U;
      SysTick->SR = 0;
      SysTick->CTLR = 7;
    }
    if (router.output_length &&
        uart_write_bytes(router.output, router.output_length))
      router.output_length = 0;
    uint16_t byte;
    if (!router.output_length && uart_read(&byte))
      lg_receive(&router, &node, byte, now);
    uint32_t rate =
        lg_rate_poll(&node, local,
                     !router.output_length && uart_tx_free() == 127 &&
                         (USART1->STATR & USART_STATR_TC));
    if (rate) {
      uart_set_baud(rate);
      router.used = 0;
      router.damaged = false;
    }
    node.uart_errors = uart_errors();
    node.uart_drops = uart_dropped();
    node.presented_generation = display_presented_generation();
    if (!publish_pending && lg_render(&node, now, levels))
      publish_pending = true;
    if (publish_pending) {
      /* Core is row-major. Driver buffers are column-major. Convert in place,
         undo after enqueue so held raw levels keep canonical coordinates. */
      for (unsigned y = 0; y < 8; ++y)
        for (unsigned x = y + 1; x < 8; ++x) {
          uint8_t v = levels[y * 8 + x];
          levels[y * 8 + x] = levels[x * 8 + y];
          levels[x * 8 + y] = v;
        }
      display_brightness(node.brightness);
      bool accepted = display_present_tagged(levels, node.desired_generation);
      for (unsigned y = 0; y < 8; ++y)
        for (unsigned x = y + 1; x < 8; ++x) {
          uint8_t v = levels[y * 8 + x];
          levels[y * 8 + x] = levels[x * 8 + y];
          levels[x * 8 + y] = v;
        }
      if (accepted)
        publish_pending = false;
    }
  }
}
