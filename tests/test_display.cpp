#include "ch32v00x.h"
#include "display.h"
#include <cassert>
#include <cstdio>
#include <cmath>

GPIO_TypeDef gpio_a, gpio_c, gpio_d;
RCC_TypeDef rcc;
TIM_TypeDef timer_1, timer_2;
AFIO_TypeDef afio;
uint32_t SystemCoreClock = 48000000;

static uint32_t row_outputs()
{
    return (gpio_a.OUTDR & 0x02) | (gpio_c.OUTDR & 0x19) |
           (gpio_d.OUTDR & 0x9c);
}

void WriteRegister::operator=(uint32_t value)
{
    const uint32_t old_address = gpio_c.OUTDR & 0xe0;
    gpio->OUTDR = (gpio->OUTDR & ~(value >> 16)) | (value & 0xffff);
    if ((gpio_c.OUTDR & 0xe0) != old_address)
    {
        assert(timer_1.CHCTLR1 == 0x4040 && timer_1.CHCTLR2 == 0x4040 &&
               timer_2.CHCTLR1 == 0x4040 && timer_2.CHCTLR2 == 0x4040);
        assert((gpio_a.CFGLR & 0xf0U) == 0x30U);
        assert((gpio_c.CFGLR & 0xff00fU) == 0x33003U);
        assert((gpio_d.CFGLR & 0xf00fff00U) == 0x30033300U);
    }
}

static unsigned expected_duty(unsigned percent)
{
    if (!percent) return 0;
    const unsigned rounded = unsigned(std::floor(1200 * std::pow(percent / 100.0, 2.2) + .5));
    return rounded ? rounded : 1;
}

static void check_column(unsigned column, uint8_t pixels, unsigned percent = 101)
{
    if (percent == 101) percent = display_brightness_get();
    const unsigned decoded = ((gpio_c.OUTDR >> 7) & 1) |
                             ((gpio_c.OUTDR >> 5) & 2) |
                             ((gpio_c.OUTDR >> 3) & 4);
    assert(decoded == column);
    const uint32_t actual[8] = {timer_2.CH4CVR, timer_2.CH3CVR, timer_2.CH2CVR, timer_2.CH1CVR,
                               timer_1.CH4CVR, timer_1.CH3CVR, timer_1.CH2CVR, timer_1.CH1CVR};
    for (unsigned row = 0; row < 8; ++row)
        assert(actual[row] == ((pixels & (1U<<row)) ? expected_duty(percent) : 0U));
    assert(timer_2.DMAINTENR == TIM_UIE);
    timer_2.INTFR = TIM_UIF;
    display_unblank();
    assert(timer_2.DMAINTENR == 0 && timer_1.CHCTLR1 == 0x6060U);
    GPIO_TypeDef *ports[8] = {GPIOD, GPIOC, GPIOD, GPIOD, GPIOC, GPIOC, GPIOA, GPIOD};
    const unsigned pins[8] = {7,0,3,4,4,3,1,2};
    for (unsigned i=0;i<8;++i)
        assert(((ports[i]->CFGLR>>(pins[i]*4U))&0xfU) ==
               ((pixels&(1U<<i)) && percent ? 0xbU : 3U));
    assert((gpio_a.OUTDR & 0x04) == 0x04);
    assert((gpio_c.OUTDR & 0x06) == 0x06);
    assert((gpio_d.OUTDR & 0x02) == 0x02); /* Preserve SWIO and other lines. */
}

int main()
{
    gpio_a.OUTDR = 0x04;
    gpio_c.OUTDR = 0x06;
    gpio_d.OUTDR = 0x02;
    display_init();
    assert(row_outputs() == 0);
    assert(timer_1.PSC == 3 && timer_2.PSC == 3);
    assert(timer_1.ATRLR == 1199 && timer_2.ATRLR == 1199);
    assert((gpio_d.CFGLR & 0xf0) == 0x40); /* SWIO pin config untouched. */
    const uint8_t diagonal[8] = {1, 2, 4, 8, 16, 32, 64, 128};
    const uint8_t blank[8] = {};
    assert(display_present(diagonal));
    assert(!display_present(blank));
    display_tick();
    check_column(0, diagonal[0]);
    assert(display_present(blank));
    assert(!display_present(diagonal));
    for (unsigned column = 1; column < 8; ++column)
    {
        display_tick();
        check_column(column, diagonal[column]); /* Old frame lasts all 8 slots. */
    }
    for (unsigned column = 0; column < 8; ++column)
    {
        display_tick();
        check_column(column, 0);
    }
    display_brightness(25);
    assert(display_brightness_get() == 25);
    display_brightness(101);
    assert(display_brightness_get() == 25);
    assert(display_present(diagonal));
    for (unsigned column = 0; column < 8; ++column) {
        display_tick(); check_column(column, diagonal[column]);
    }
    display_brightness(0);
    for (unsigned column = 0; column < 8; ++column) {
        display_tick(); check_column(column, 0);
    }
    const uint8_t all[8] = {255,255,255,255,255,255,255,255};
    assert(display_present(all));
    unsigned previous = 0;
    for (unsigned percent = 0; percent <= 100; ++percent) {
        display_brightness(percent);
        for (unsigned column = 0; column < 8; ++column) {
            display_tick(); check_column(column, 255, percent);
        }
        assert(timer_1.CH1CVR >= previous && timer_1.CH1CVR <= 1200);
        previous = timer_1.CH1CVR;
        assert(display_brightness_get() == percent);
    }
    /* New brightness cannot split an eight-column scan. */
    display_brightness(25);
    display_tick(); check_column(0, 255, 25);
    display_brightness(75);
    for (unsigned column = 1; column < 8; ++column) {
        display_tick(); check_column(column, 255, 25);
    }
    display_tick(); check_column(0, 255, 75);
    std::puts("Display tests passed: gamma curve/endpoints, scan-boundary brightness, pin map, ghost blanking and frame handoff.");
}
