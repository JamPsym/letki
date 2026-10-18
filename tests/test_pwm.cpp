#include "ch32v00x.h"
#include "pwm_display.h"
#include <cassert>
#include <cstdio>
GPIO_TypeDef gpio_a, gpio_c, gpio_d;
TIM_TypeDef timer_1, timer_2;
RCC_TypeDef rcc;
AFIO_TypeDef afio;
uint32_t SystemCoreClock = 48000000;
void WriteRegister::operator=(uint32_t value)
{
    const uint32_t address = gpio_c.OUTDR & 0xe0U;
    gpio->OUTDR = (gpio->OUTDR & ~(value>>16)) | (value&0xffffU);
    if ((gpio_c.OUTDR&0xe0U) != address) {
        assert(timer_1.CHCTLR1 == 0x4040U && timer_1.CHCTLR2 == 0x4040U);
        assert(timer_2.CHCTLR1 == 0x4040U && timer_2.CHCTLR2 == 0x4040U);
        assert((gpio_a.CFGLR & 0xf0U) == 0x30U);
        assert((gpio_c.CFGLR & 0xff00fU) == 0x33003U);
        assert((gpio_d.CFGLR & 0xf00fff00U) == 0x30033300U);
    }
}
static void check(unsigned column, unsigned duty)
{
    const unsigned address = ((gpio_c.OUTDR>>7)&1U) | ((gpio_c.OUTDR>>5)&2U) | ((gpio_c.OUTDR>>3)&4U);
    assert(address == column);
    const uint32_t actual[8] = {timer_2.CH4CVR,timer_2.CH3CVR,timer_2.CH2CVR,timer_2.CH1CVR,
                               timer_1.CH4CVR,timer_1.CH3CVR,timer_1.CH2CVR,timer_1.CH1CVR};
    for (unsigned i=0; i<8; ++i) assert(actual[i] == (i==column ? duty : 0U));
    assert(timer_1.CCER == 0x1111U && timer_2.CCER == 0x1111U);
    assert(timer_1.CHCTLR1 == 0x6060U && timer_2.CHCTLR2 == 0x6060U);
}
int main()
{
    gpio_d.CFGLR = 0x48b44444U;
    const uint32_t preserved = gpio_d.CFGLR & 0x0ff000f0U;
    afio.PCFR1 = 0x8003c0U | 0x4000U;
    pwm_display_init();
    pwm_display_blank_period(false);
    assert((gpio_d.CFGLR & 0x0ff000f0U) == preserved);
    assert((afio.PCFR1 & 0x8003c0U) == 0 && (afio.PCFR1&0x4000U));
    assert(timer_1.PSC == 47U && timer_2.ATRLR == 99U);
    assert(timer_1.BDTR == 0x8000U);
    assert((gpio_c.CFGLR & 0xfff00000U) == 0x33300000U);
    assert((gpio_a.CFGLR & 0x00000f00U) == 0x00000400U);
    const uint8_t diagonal[8] = {1,2,4,8,16,32,64,128};
    const uint8_t levels[8] = {0,10,25,40,50,70,85,100};
    const uint8_t half[8] = {50,50,50,50,50,50,50,50};
    uint8_t invalid[8] = {3,0,0,0,0,0,0,0};
    assert(!pwm_display_present(invalid,levels));
    invalid[0]=101;
    assert(!pwm_display_present(diagonal,invalid));
    assert(pwm_display_present(diagonal,levels));
    assert(!pwm_display_present(diagonal,half));
    pwm_display_tick(); check(0,0);
    assert(pwm_display_present(diagonal,half));
    for (unsigned i=1;i<8;++i) { pwm_display_tick(); check(i,levels[i]); }
    for (unsigned i=0;i<8;++i) { pwm_display_tick(); check(i,50); }
    assert(pwm_display_scans()==16);
    timer_2.CNT=timer_1.CNT=25;
    gpio_d.INDR=1U<<2;
    uint8_t row,duty; bool high,expected;
    assert(pwm_display_sample(&row,&duty,&high,&expected));
    assert(row==7 && duty==50 && high && expected);
    gpio_d.INDR=0;
    assert(pwm_display_sample(&row,&duty,&high,&expected) && !high && expected);
    timer_1.CNT=50;
    assert(!pwm_display_sample(&row,&duty,&high,&expected));
    timer_1.CNT=75;
    assert(pwm_display_sample(&row,&duty,&high,&expected) && !high && !expected);
    pwm_display_blank_period(true);
    pwm_display_tick();
    assert(timer_1.CHCTLR1==0x4040U && timer_2.DMAINTENR==1U);
    assert(!pwm_display_sample(&row,&duty,&high,&expected));
    timer_2.INTFR=1U;
    pwm_display_unblank();
    assert(timer_2.DMAINTENR==0 && timer_1.CHCTLR1==0x6060U);
    std::puts("PWM tests passed: independent channels, forced-low blanking, paired buffers, sparse guard, pin preservation and pad sampling.");
}
