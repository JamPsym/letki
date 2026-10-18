#include "ch32v00x.h"
#include "display.h"
#include <cassert>
#include <cstdio>

GPIO_TypeDef gpio_a, gpio_c, gpio_d;
RCC_TypeDef rcc;
TIM_TypeDef timer_1, timer_2;
AFIO_TypeDef afio;
uint32_t SystemCoreClock = 48000000;

void WriteRegister::operator=(uint32_t value)
{
    /* Every driver write must clear pins; none may assert a row gate. */
    assert((value & 0xffffU) == 0);
    gpio->OUTDR = (gpio->OUTDR & ~(value >> 16)) | (value & 0xffffU);
}

int main()
{
    gpio_a.OUTDR = gpio_c.OUTDR = gpio_d.OUTDR = 0xffff;
    gpio_a.CFGLR = gpio_c.CFGLR = gpio_d.CFGLR = 0xa5a5a5a5U;
    const uint32_t old_a = gpio_a.CFGLR;
    const uint32_t old_c = gpio_c.CFGLR;
    const uint32_t old_d = gpio_d.CFGLR;
    timer_1.CTLR1 = timer_2.CTLR1 = TIM_CEN;
    timer_1.CCER = timer_2.CCER = 0xffff;
    timer_1.BDTR = TIM_MOE;
    timer_1.DMAINTENR = timer_2.DMAINTENR = 0xffff;
    display_init();
    const uint8_t all_on[8] = {255,255,255,255,255,255,255,255};
    for (unsigned i = 0; i < 1000; ++i) {
        assert(display_present(all_on));
        display_tick();
        assert((gpio_a.OUTDR & 0x02) == 0);
        assert((gpio_c.OUTDR & 0xf9) == 0);
        assert((gpio_d.OUTDR & 0x9c) == 0);
        assert(timer_1.CCER == 0 && timer_2.CCER == 0);
        assert(timer_1.CTLR1 == 0 && timer_2.CTLR1 == 0 && timer_1.BDTR == 0);
    }
    assert((gpio_a.CFGLR & ~0xf0U) == (old_a & ~0xf0U));
    assert((gpio_c.CFGLR & ~0xfffff00fU) == (old_c & ~0xfffff00fU));
    assert((gpio_d.CFGLR & ~0xf00fff00U) == (old_d & ~0xf00fff00U));
    assert((gpio_a.OUTDR & ~0x02U) == (0xffffU & ~0x02U));
    assert((gpio_c.OUTDR & ~0xf9U) == (0xffffU & ~0xf9U));
    assert((gpio_d.OUTDR & ~0x9cU) == (0xffffU & ~0x9cU));
    assert(timer_1.DMAINTENR == 0 && timer_2.DMAINTENR == 0);
    puts("v3.1 interface driver: all row gates remain LOW; reserved pins preserved");
}
