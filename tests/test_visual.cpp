#include "ch32v00x.h"
#include "display.h"
#include "wave.h"
#include <cassert>
#include <cstdio>
#include <cmath>
#include <initializer_list>
#include <string>
#include "uart.h"
#include "swio.h"

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


static unsigned gamma(unsigned n)
{
    if (!n) return 0;
    unsigned value = unsigned(std::floor(1200*std::pow(n/100.0, 2.2)+.5));
    return value ? value : 1;
}
static void column(unsigned x, const uint8_t *frame, unsigned percent)
{
    display_tick();
    const uint32_t actual[8] = {timer_2.CH4CVR,timer_2.CH3CVR,timer_2.CH2CVR,timer_2.CH1CVR,
        timer_1.CH4CVR,timer_1.CH3CVR,timer_1.CH2CVR,timer_1.CH1CVR};
    assert((((gpio_c.OUTDR>>7)&1)|((gpio_c.OUTDR>>5)&2)|((gpio_c.OUTDR>>3)&4)) == x);
    timer_2.INTFR = TIM_UIF; display_unblank();
    GPIO_TypeDef *ports[8] = {GPIOD,GPIOC,GPIOD,GPIOD,GPIOC,GPIOC,GPIOA,GPIOD};
    unsigned pins[8] = {7,0,3,4,4,3,1,2};
    for (unsigned y=0;y<8;++y) {
        assert(actual[y] == gamma((frame[x*8+y]*percent+50)/100));
        assert(((ports[y]->CFGLR>>(pins[y]*4))&15) == (actual[y] ? 11U : 3U));
    }
}
/* Exercise the actual foreground command paths with mocked transport only. */
static std::string output;
bool swio_write(const char *s) { output += s; return true; }
void swio_init(void) {}
void swio_poll(void (*)(char)) {}
void uart_init(void) {}
void uart_poll(void) {}
bool uart_write(const char *) { return true; }
bool uart_read(uint16_t *) { return false; }
uint32_t uart_errors(void) { return 0; }
uint32_t uart_dropped(void) { return 0; }
struct FakeSysTick { uint32_t SR, CTLR, CNT, CMP; } fake_systick;
#define SysTick (&fake_systick)
#define SysTick_IRQn 0
#define TIM2_IRQn 1
static void SystemCoreClockUpdate(void) {}
static void NVIC_EnableIRQ(unsigned) {}
static void __enable_irq(void) {}
#define VISUAL_INTERRUPT
#define main visual_firmware_main
#include "../firmware/visual-demo/User/main.c"
#undef main

int main()
{
    display_init(); assert(row_outputs() == 0);
    uint8_t a[64], b[64];
    for (unsigned phase=0;phase<32;++phase) {
        wave_frame(a, phase); wave_frame(b, phase+32);
        for (unsigned x=0;x<8;++x) for (unsigned y=0;y<8;++y) {
            unsigned i=x*8+y;
            assert(a[i] <= 100 && a[i] == b[i]);
            assert(a[i] == a[(7-x)*8+y] && a[i] == a[x*8+7-y] && a[i] == a[y*8+x]);
        }
    }
    wave_frame(a, 0); wave_frame(b, 8);
    assert(display_present_levels(a)); assert(!display_present_levels(b));
    column(0,a,100);
    assert(display_present_levels(b));
    for (unsigned x=1;x<8;++x) column(x,a,100);
    for (unsigned x=0;x<8;++x) column(x,b,100);
    for (unsigned percent : {0U,1U,25U,50U,75U,100U}) {
        display_brightness(percent); assert(display_present_levels(a));
        for (unsigned x=0;x<8;++x) column(x,a,percent);
    }
    b[63]=101; assert(!display_present_levels(b));
    for (unsigned x=0;x<8;++x) column(x,a,100);
    command('b'); command(' '); command('2');
    assert(brightness_editing());
    output.clear(); uart_command("help");
    assert(output.find("Radial wave") != std::string::npos && brightness_editing());
    uart_command("v 50"); assert(output.find("ERR busy") != std::string::npos);
    command('5'); command('\n');
    assert(!brightness_editing() && display_brightness_get() == 25);
    uart_command("p"); assert(paused);
    uart_command("b 50"); assert(display_brightness_get() == 50 && dirty);
    uart_command("b 101"); assert(display_brightness_get() == 50);
    uart_command("r"); assert(!paused);
    uart_command("v 100"); assert(interval == 100);
    uart_command("0"); assert(interval == 45 && display_brightness_get() == 100 && phase == 0);
    std::puts("Visual tests passed: radial symmetry, period, bounds, per-pixel gamma, blanking and atomic frames.");
}
