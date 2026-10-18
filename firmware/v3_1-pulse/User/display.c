#include "display.h"
#include "ch32v00x.h"

/* Study C only: AO3415A sources, DMN2056U-7 sinks, reversed LEDs.
 * GPIO LOW blanks before address changes. PWM2 plus one-pulse mode ends
 * every row pulse in hardware, even if the next SysTick never arrives.
 * Nominal timer window 110us, pulse <=80us, scan slot 125us, frame 1ms.
 * Not compatible with original v3. Scope gate/drain timing before use.
 */
#define ROWS_A (1U<<1)
#define ROWS_C ((1U<<0)|(1U<<3)|(1U<<4))
#define ROWS_D ((1U<<2)|(1U<<3)|(1U<<4)|(1U<<7))
#define ADDRESS_C ((1U<<5)|(1U<<6)|(1U<<7))
static uint8_t frames[2][8];
static volatile uint8_t active_frame, pending_frame;
static uint8_t scan_column;
/* Prototype power-up stays dark until an explicit brightness command. */
static volatile uint8_t requested_brightness;
static uint16_t pulse_ticks;
static const uint16_t gamma_pulse[101] = {
    0, 1, 1, 1, 1, 1, 2, 3, 4, 5,
    6, 7, 9, 11, 13, 15, 17, 19, 22, 25,
    28, 31, 34, 38, 42, 45, 50, 54, 58, 63,
    68, 73, 78, 84, 89, 95, 101, 108, 114, 121,
    128, 135, 142, 150, 158, 166, 174, 182, 191, 200,
    209, 218, 228, 238, 247, 258, 268, 279, 290, 301,
    312, 324, 335, 347, 360, 372, 385, 398, 411, 424,
    438, 452, 466, 480, 495, 510, 525, 540, 556, 572,
    588, 604, 620, 637, 654, 671, 689, 707, 725, 743,
    761, 780, 799, 818, 838, 858, 878, 898, 918, 939,
    960,
};

static void blank_rows(void)
{
    TIM1->CHCTLR1 = TIM1->CHCTLR2 = 0x4040U;
    TIM2->CHCTLR1 = TIM2->CHCTLR2 = 0x4040U;
    GPIOA->BSHR = ROWS_A << 16;
    GPIOC->BSHR = ROWS_C << 16;
    GPIOD->BSHR = ROWS_D << 16;
    GPIOA->CFGLR = (GPIOA->CFGLR & ~0xf0U) | 0x30U;
    GPIOC->CFGLR = (GPIOC->CFGLR & ~0xff00fU) | 0x33003U;
    GPIOD->CFGLR = (GPIOD->CFGLR & ~0xf00fff00U) | 0x30033300U;
}
static void timer_init(TIM_TypeDef *timer)
{
    timer->CTLR1 = TIM_OPM;
    timer->CTLR2 = timer->SMCFGR = timer->DMAINTENR = 0;
    timer->CCER = 0x1111U; /* Main outputs, complementary/SWIO outputs off. */
    timer->CHCTLR1 = timer->CHCTLR2 = 0x4040U;
    timer->PSC = SystemCoreClock/12000000U - 1U;
    timer->ATRLR = PULSE_TIMER_TICKS-1U;
    timer->CH1CVR = timer->CH2CVR = timer->CH3CVR = timer->CH4CVR = PULSE_TIMER_TICKS;
    timer->SWEVGR = TIM_UG; /* Reload prescaler and reset the upcounter to zero. */
    timer->INTFR = 0;
}
void display_init(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC |
                     RCC_APB2Periph_GPIOD | RCC_APB2Periph_TIM1 | RCC_AFIOEN;
    RCC->APB1PCENR |= RCC_APB1Periph_TIM2;
    AFIO->PCFR1 &= ~(AFIO_PCFR1_TIM1_REMAP | AFIO_PCFR1_TIM2_REMAP | AFIO_PCFR1_TIM1_1_RM);
    blank_rows();
    GPIOC->BSHR = ADDRESS_C << 16;
    for (unsigned pin=5; pin<=7; ++pin) {
        const unsigned shift=pin*4U;
        GPIOC->CFGLR=(GPIOC->CFGLR & ~(0xfU<<shift)) | (0x7U<<shift);
    }
    timer_init(TIM1); timer_init(TIM2);
    TIM1->RPTCR = 0;
    TIM1->BDTR = TIM_MOE;
}
void display_brightness(uint8_t percent)
{
    if (percent<=100U) requested_brightness=percent;
}
uint8_t display_brightness_get(void) { return requested_brightness; }
bool display_present(const uint8_t columns[8])
{
    if (pending_frame) return false;
    const uint8_t next=active_frame^1U;
    for (unsigned col=0;col<8;++col) frames[next][col]=columns[col];
    __asm__ volatile ("" ::: "memory");
    pending_frame=next+1U;
    return true;
}
void display_tick(void)
{
    blank_rows();
    TIM1->CTLR1 = TIM2->CTLR1 = TIM_OPM;
    if (!scan_column) {
        pulse_ticks=gamma_pulse[requested_brightness];
        if (pending_frame) {
            active_frame=pending_frame-1U;
            pending_frame=0;
        }
    }
    const uint32_t address=((scan_column&1U)<<7)|((scan_column&2U)<<5)|((scan_column&4U)<<3);
    GPIOC->BSHR=((ADDRESS_C & ~address)<<16)|address;
    const uint8_t pixels=frames[active_frame][scan_column];
    const uint8_t mask=pulse_ticks ? pixels : 0;
    const uint16_t compare=PULSE_TIMER_TICKS-pulse_ticks;
    /* PWM2 is LOW for CNT<CCR and HIGH for CCR<=CNT<=ARR.
       CCR>=360 guarantees initial blank; ARR rollover returns CNT to zero.
       OPM clears CEN at that rollover: output stays LOW without any ISR. */
    TIM2->CH4CVR=(pixels&1U) ? compare : PULSE_TIMER_TICKS;
    TIM2->CH3CVR=(pixels&2U) ? compare : PULSE_TIMER_TICKS;
    TIM2->CH2CVR=(pixels&4U) ? compare : PULSE_TIMER_TICKS;
    TIM2->CH1CVR=(pixels&8U) ? compare : PULSE_TIMER_TICKS;
    TIM1->CH4CVR=(pixels&16U) ? compare : PULSE_TIMER_TICKS;
    TIM1->CH3CVR=(pixels&32U) ? compare : PULSE_TIMER_TICKS;
    TIM1->CH2CVR=(pixels&64U) ? compare : PULSE_TIMER_TICKS;
    TIM1->CH1CVR=(pixels&128U) ? compare : PULSE_TIMER_TICKS;
    TIM1->SWEVGR = TIM2->SWEVGR = TIM_UG;
    TIM1->INTFR = TIM2->INTFR = 0;
    TIM1->DMAINTENR = TIM2->DMAINTENR = 0;
    TIM1->CHCTLR1 = TIM1->CHCTLR2 = 0x7070U;
    TIM2->CHCTLR1 = TIM2->CHCTLR2 = 0x7070U;
    GPIOA->CFGLR=(GPIOA->CFGLR & ~0xf0U)|0x30U|((mask&64U) ? 0x80U : 0);
    GPIOC->CFGLR=(GPIOC->CFGLR & ~0xff00fU)|0x33003U|
                ((mask&2U) ? 8U : 0)|((mask&16U) ? 0x80000U : 0)|((mask&32U) ? 0x8000U : 0);
    GPIOD->CFGLR=(GPIOD->CFGLR & ~0xf00fff00U)|0x30033300U|
                ((mask&1U) ? 0x80000000U : 0)|((mask&4U) ? 0x8000U : 0)|
                ((mask&8U) ? 0x80000U : 0)|((mask&128U) ? 0x800U : 0);
    TIM1->CTLR1 = TIM_OPM|TIM_CEN;
    TIM2->CTLR1 = TIM_OPM|TIM_CEN;
    scan_column=(scan_column+1U)&7U;
}
void display_unblank(void)
{
    /* No delayed software release: compare/rollover hardware owns the pulse. */
    TIM2->INTFR=0;
}

