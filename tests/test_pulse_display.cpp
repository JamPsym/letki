#include "ch32v00x.h"
#include "display.h"
#include <cassert>
#include <cmath>
#include <cstdio>

GPIO_TypeDef gpio_a, gpio_c, gpio_d;
RCC_TypeDef rcc;
TIM_TypeDef timer_1, timer_2;
AFIO_TypeDef afio;
uint32_t SystemCoreClock=48000000;

static uint32_t row_outputs()
{
    return (gpio_a.OUTDR&2U)|(gpio_c.OUTDR&0x19U)|(gpio_d.OUTDR&0x9cU);
}
void WriteRegister::operator=(uint32_t value)
{
    const uint32_t old=gpio_c.OUTDR&0xe0U;
    gpio->OUTDR=(gpio->OUTDR & ~(value>>16))|(value&0xffffU);
    if ((gpio_c.OUTDR&0xe0U)!=old) {
        assert(row_outputs()==0);
        assert(timer_1.CHCTLR1==0x4040U && timer_2.CHCTLR1==0x4040U);
        assert((gpio_a.CFGLR&0xf0U)==0x30U);
        assert((gpio_c.CFGLR&0xff00fU)==0x33003U);
        assert((gpio_d.CFGLR&0xf00fff00U)==0x30033300U);
    }
}
static unsigned expected(unsigned percent)
{
    if (!percent) return 0;
    const unsigned n=unsigned(std::floor(960*std::pow(percent/100.0,2.2)+.5));
    return n ? n : 1;
}
/* Peripheral model follows the WCH OPM + PWM2 specification. This checks the
   programmed registers and failure behavior, not silicon waveforms/LED current. */
static bool high(const TIM_TypeDef &t, unsigned compare, unsigned mode)
{
    return mode==0xbU && t.CNT>=compare && t.CNT<=t.ATRLR;
}
static void step(TIM_TypeDef &t)
{
    if (!(t.CTLR1&TIM_CEN)) return;
    if (++t.CNT>t.ATRLR) {
        t.CNT=0; t.INTFR|=TIM_UIF;
        if (t.CTLR1&TIM_OPM) t.CTLR1&=~TIM_CEN;
    }
}
static void column(unsigned col, uint8_t pixels, unsigned percent)
{
    display_tick();
    const unsigned decoded=((gpio_c.OUTDR>>7)&1U)|((gpio_c.OUTDR>>5)&2U)|((gpio_c.OUTDR>>3)&4U);
    assert(decoded==col);
    assert(timer_1.CTLR1==(TIM_OPM|TIM_CEN) && timer_2.CTLR1==(TIM_OPM|TIM_CEN));
    assert(timer_1.PSC==3 && timer_2.PSC==3);
    assert(timer_1.ATRLR==1319 && timer_2.ATRLR==1319);
    assert(timer_1.CCER==0x1111U && timer_2.CCER==0x1111U);
    assert(timer_1.CHCTLR1==0x7070U && timer_1.CHCTLR2==0x7070U);
    assert(timer_2.CHCTLR1==0x7070U && timer_2.CHCTLR2==0x7070U);
    assert(timer_1.DMAINTENR==0 && timer_2.DMAINTENR==0);
    assert(timer_1.SWEVGR==TIM_UG && timer_2.SWEVGR==TIM_UG);
    timer_1.CNT=timer_2.CNT=0; /* Apply the programmed UG event. */
    const unsigned compares[8]={timer_2.CH4CVR,timer_2.CH3CVR,timer_2.CH2CVR,timer_2.CH1CVR,
                                timer_1.CH4CVR,timer_1.CH3CVR,timer_1.CH2CVR,timer_1.CH1CVR};
    GPIO_TypeDef *ports[8]={GPIOD,GPIOC,GPIOD,GPIOD,GPIOC,GPIOC,GPIOA,GPIOD};
    const unsigned pins[8]={7,0,3,4,4,3,1,2};
    unsigned modes[8], counts[8]={};
    for (unsigned row=0;row<8;++row) {
        modes[row]=(ports[row]->CFGLR>>(pins[row]*4U))&0xfU;
        const bool on=(pixels&(1U<<row)) && percent;
        assert(modes[row]==(on ? 0xbU : 3U));
        assert(compares[row]==1320U-((pixels&(1U<<row)) ? expected(percent) : 0U));
        assert(compares[row]>=360U);
    }
    /* Skip the next SysTick and all timer IRQs: one pulse must end anyway,
       and stay off for many more periods. */
    for (unsigned tick=0;tick<4000;++tick) {
        for (unsigned row=0;row<8;++row) {
            const TIM_TypeDef &t=row<4 ? timer_2 : timer_1;
            const bool on=high(t,compares[row],modes[row]);
            if (tick<360 || tick>=1320) assert(!on);
            counts[row]+=on;
        }
        step(timer_1);step(timer_2);
    }
    for (unsigned row=0;row<8;++row)
        assert(counts[row]==((pixels&(1U<<row)) ? expected(percent) : 0U));
    assert(!(timer_1.CTLR1&TIM_CEN) && !(timer_2.CTLR1&TIM_CEN));
    display_unblank(); /* A stray compatibility IRQ cannot restart a pulse. */
    assert(!(timer_1.CTLR1&TIM_CEN) && !(timer_2.CTLR1&TIM_CEN));
    assert(timer_1.CNT==0 && timer_2.CNT==0);
    for (unsigned pin=5;pin<=7;++pin) assert(((gpio_c.CFGLR>>(pin*4U))&0xfU)==7U);
    assert((gpio_a.OUTDR&4U) && (gpio_c.OUTDR&6U)==6U && (gpio_d.OUTDR&2U));
    assert((gpio_d.CFGLR&0xf0U)==0x40U); /* SWIO unchanged. */
}
int main()
{
    gpio_a.OUTDR=4;gpio_c.OUTDR=6;gpio_d.OUTDR=2;
    display_init();
    assert(row_outputs()==0);
    const uint8_t diag[8]={1,2,4,8,16,32,64,128}, all[8]={255,255,255,255,255,255,255,255}, blank[8]={};
    assert(display_brightness_get()==0);
    assert(display_present(all));
    for (unsigned col=0;col<8;++col) column(col,255,0);
    display_brightness(100);
    assert(display_present(diag));assert(!display_present(blank));
    column(0,diag[0],100);
    assert(display_present(all));assert(!display_present(blank));
    for (unsigned col=1;col<8;++col) column(col,diag[col],100);
    for (unsigned col=0;col<8;++col) column(col,255,100);
    for (unsigned percent=0;percent<=100;++percent) {
        display_brightness(percent);
        for (unsigned col=0;col<8;++col) column(col,255,percent);
    }
    display_brightness(101);assert(display_brightness_get()==100);
    display_brightness(25);column(0,255,25);
    display_brightness(75);
    for (unsigned col=1;col<8;++col) column(col,255,25);
    column(0,255,75);
    assert(display_present(blank));
    for (unsigned col=1;col<8;++col) column(col,255,75);
    for (unsigned col=0;col<8;++col) column(col,0,75);
    std::puts("Pulse study register/model tests passed: all channels/levels, GPIO blanking, bounded OPM pulse, skipped-IRQ OFF and frame latches. Not physical validation.");
}
