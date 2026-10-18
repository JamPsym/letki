#include "ch32v00x.h"
#include "display.h"
#include <cassert>
GPIO_TypeDef gpio_a, gpio_c, gpio_d;
RCC_TypeDef rcc;
TIM_TypeDef timer_1, timer_2;
AFIO_TypeDef afio;
uint32_t SystemCoreClock = 48000000;
void WriteRegister::operator=(uint32_t value) {
  const unsigned old = gpio_c.OUTDR & 0xe0;
  gpio->OUTDR = (gpio->OUTDR & ~(value >> 16)) | (value & 0xffff);
  if ((gpio_c.OUTDR & 0xe0) != old) {
    assert(timer_1.CHCTLR1 == 0x4040 && timer_2.CHCTLR1 == 0x4040);
    assert((gpio_d.CFGLR & 0xf00fff00U) == 0x30033300U);
  }
}
int main() {
  display_init();
  uint8_t pixels[64] = {0};
  pixels[0] = 100;
  assert(display_present_tagged(pixels, 33));
  assert(display_presented_generation() == 0);
  display_tick();
  assert(display_presented_generation() == 33);
  timer_2.INTFR = TIM_UIF;
  display_unblank();
  assert((gpio_d.CFGLR >> 28) == 11);
  assert(display_present_tagged(pixels, 44));
  for (unsigned i = 0; i < 7; ++i) {
    display_tick();
    assert(display_presented_generation() == 33);
  }
  display_tick();
  assert(display_presented_generation() == 44);
  timer_2.INTFR = TIM_UIF;
  display_suspend();
  assert(!timer_2.INTFR && !timer_2.DMAINTENR && !timer_1.CTLR1 &&
         !timer_2.CTLR1);
  assert((gpio_d.CFGLR & 0xf00fff00U) == 0x30033300U);
  display_unblank();
  assert((gpio_d.CFGLR & 0xf00fff00U) == 0x30033300U);
  display_tick();
  assert(timer_2.CH4CVR == 0 && timer_1.CH4CVR == 0);
  return 0;
}
