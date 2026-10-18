#include "pwm_display.h"
#include "ch32v00x.h"

/* WCH RM v1.9 tables 7-8/7-9, default mappings; PCB D8..D1. */
struct row_pin { GPIO_TypeDef *gpio; TIM_TypeDef *timer; uint8_t pin, channel; };
static const struct row_pin rows[8] = {
    {GPIOD, TIM2, 7, 4}, {GPIOC, TIM2, 0, 3},
    {GPIOD, TIM2, 3, 2}, {GPIOD, TIM2, 4, 1},
    {GPIOC, TIM1, 4, 4}, {GPIOC, TIM1, 3, 3},
    {GPIOA, TIM1, 1, 2}, {GPIOD, TIM1, 2, 1},
};
#define FORCE_LOW 0x4040U
#define PWM_MODE1 0x6060U
#define CHANNELS 0x1111U /* Main outputs only: never enable PD1/PA2/PD0 complements. */
#define ADDRESS_C 0xe0U

static uint8_t pixels[2][8], duties[2][8];
static volatile uint8_t active, pending, selected_row = 255, selected_duty;
static uint8_t column;
static volatile uint32_t scans;
static volatile bool blank_period = true, gate_open;
static uint32_t gate_a, gate_c, gate_d;

static void blank(void)
{
    /* GPIO BSHR cannot blank pins once the alternate timer function owns them.
       Force OCxREF low, with main outputs still enabled, before decoder changes. */
    TIM1->CHCTLR1 = TIM1->CHCTLR2 = FORCE_LOW;
    TIM2->CHCTLR1 = TIM2->CHCTLR2 = FORCE_LOW;
    GPIOA->BSHR = 0x02U << 16;
    GPIOC->BSHR = 0x19U << 16;
    GPIOD->BSHR = 0x9cU << 16;
    GPIOA->CFGLR = (GPIOA->CFGLR & ~0x000000f0U) | 0x00000030U;
    GPIOC->CFGLR = (GPIOC->CFGLR & ~0x000ff00fU) | 0x00033003U;
    GPIOD->CFGLR = (GPIOD->CFGLR & ~0xf00fff00U) | 0x30033300U;
}

static void configure_timer(TIM_TypeDef *timer)
{
    timer->CTLR1 = 0;
    timer->CTLR2 = 0;
    timer->SMCFGR = 0;
    timer->DMAINTENR = 0;
    timer->CCER = CHANNELS;
    timer->CHCTLR1 = timer->CHCTLR2 = FORCE_LOW;
    timer->PSC = SystemCoreClock / 1000000U - 1U;
    timer->ATRLR = 99U; /* 1 MHz counter, 100 ticks: nominal 10 kHz PWM. */
    timer->CH1CVR = timer->CH2CVR = timer->CH3CVR = timer->CH4CVR = 0;
    timer->SWEVGR = TIM_UG;
    timer->INTFR = 0;
}

void pwm_display_init(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC |
                     RCC_APB2Periph_GPIOD | RCC_APB2Periph_TIM1 | RCC_AFIOEN;
    RCC->APB1PCENR |= RCC_APB1Periph_TIM2;
    /* Preserve USART remapping and SDI. TIM1_CH1 must not be mapped to LSI. */
    AFIO->PCFR1 &= ~(AFIO_PCFR1_TIM1_REMAP | AFIO_PCFR1_TIM2_REMAP | AFIO_PCFR1_TIM1_1_RM);
    GPIOA->BSHR = 0x02U << 16;
    GPIOC->BSHR = (0x19U | ADDRESS_C) << 16;
    GPIOD->BSHR = 0x9cU << 16;
    configure_timer(TIM1);
    configure_timer(TIM2);
    TIM1->RPTCR = 0;
    TIM1->BDTR = TIM_MOE; /* Break/complementary outputs disabled. */
    for (unsigned row = 0; row < 8; ++row) {
        const unsigned shift = rows[row].pin * 4U;
        rows[row].gpio->CFGLR = (rows[row].gpio->CFGLR & ~(0xfU << shift)) |
                               (0x3U << shift); /* GPIO low until a lit row is gated to PWM. */
    }
    for (unsigned pin = 5; pin <= 7; ++pin)
        GPIOC->CFGLR = (GPIOC->CFGLR & ~(0xfU << (pin*4U))) | (3U << (pin*4U));
    active = pending = column = 0;
    scans = 0;
    selected_row = 255;
}

bool pwm_display_present(const uint8_t frame[8], const uint8_t levels[8])
{
    if (pending) return false;
    for (unsigned i = 0; i < 8; ++i)
        if (levels[i] > 100U || (frame[i] && (frame[i] & (frame[i]-1U)))) return false;
    const uint8_t next = active ^ 1U;
    for (unsigned i = 0; i < 8; ++i) {
        pixels[next][i] = frame[i];
        duties[next][i] = levels[i];
    }
    __asm__ volatile ("" ::: "memory");
    pending = next+1U;
    return true;
}

static void compare(TIM_TypeDef *timer, uint8_t channel, uint8_t duty)
{
    switch (channel) {
        case 1: timer->CH1CVR = duty; break;
        case 2: timer->CH2CVR = duty; break;
        case 3: timer->CH3CVR = duty; break;
        default: timer->CH4CVR = duty; break;
    }
}

void pwm_display_tick(void)
{
    blank();
    gate_open = false;
    TIM2->DMAINTENR = 0;
    TIM1->CTLR1 = TIM2->CTLR1 = 0;
    if (!column && pending) { active = pending-1U; pending = 0; }
    TIM1->CH1CVR = TIM1->CH2CVR = TIM1->CH3CVR = TIM1->CH4CVR = 0;
    TIM2->CH1CVR = TIM2->CH2CVR = TIM2->CH3CVR = TIM2->CH4CVR = 0;
    const uint32_t address = ((column & 1U) << 7) | ((column & 2U) << 5) | ((column & 4U) << 3);
    GPIOC->BSHR = ((ADDRESS_C & ~address) << 16) | address;
    selected_row = 255;
    for (unsigned row = 0; row < 8; ++row) {
        if (!(pixels[active][column] & (1U << row))) continue;
        selected_row = row;
        selected_duty = duties[active][row];
        compare(rows[row].timer, rows[row].channel, selected_duty);
    }
    const uint8_t mask = selected_duty ? pixels[active][column] : 0;
    gate_a = 0x30U | ((mask & 0x40U) ? 0x80U : 0);
    gate_c = 0x33003U | ((mask & 2U) ? 8U : 0) |
             ((mask & 0x10U) ? 0x80000U : 0) | ((mask & 0x20U) ? 0x8000U : 0);
    gate_d = 0x30033300U | ((mask & 1U) ? 0x80000000U : 0) |
             ((mask & 4U) ? 0x8000U : 0) | ((mask & 8U) ? 0x80000U : 0) |
             ((mask & 0x80U) ? 0x800U : 0);
    /* Both counters restart while outputs are forced low. No PWM ISR needed. */
    TIM1->SWEVGR = TIM2->SWEVGR = TIM_UG;
    TIM1->INTFR = TIM2->INTFR = 0;
    if (blank_period) TIM2->DMAINTENR = TIM_UIE;
    else {
        TIM1->CHCTLR1 = TIM1->CHCTLR2 = PWM_MODE1;
        TIM2->CHCTLR1 = TIM2->CHCTLR2 = PWM_MODE1;
        GPIOA->CFGLR = (GPIOA->CFGLR & ~0xf0U) | gate_a;
        GPIOC->CFGLR = (GPIOC->CFGLR & ~0xff00fU) | gate_c;
        GPIOD->CFGLR = (GPIOD->CFGLR & ~0xf00fff00U) | gate_d;
        gate_open = true;
    }
    TIM1->CTLR1 = TIM2->CTLR1 = TIM_CEN;
    column = (column+1U) & 7U;
    ++scans;
}

void pwm_display_unblank(void)
{
    if (!(TIM2->INTFR & TIM_UIF)) return;
    TIM2->INTFR = 0;
    TIM2->DMAINTENR = 0;
    TIM1->CHCTLR1 = TIM1->CHCTLR2 = PWM_MODE1;
    TIM2->CHCTLR1 = TIM2->CHCTLR2 = PWM_MODE1;
    GPIOA->CFGLR = (GPIOA->CFGLR & ~0xf0U) | gate_a;
    GPIOC->CFGLR = (GPIOC->CFGLR & ~0xff00fU) | gate_c;
    GPIOD->CFGLR = (GPIOD->CFGLR & ~0xf00fff00U) | gate_d;
    gate_open = true;
}
void pwm_display_blank_period(bool enable) { blank_period = enable; }

uint32_t pwm_display_scans(void) { return scans; }

bool pwm_display_sample(uint8_t *row, uint8_t *duty, bool *high, bool *expected)
{
    const uint32_t before = scans;
    const uint8_t index = selected_row;
    if (index >= 8 || !gate_open) return false;
    const uint8_t level = selected_duty;
    const uint16_t counter = rows[index].timer->CNT;
    const bool pin_high = (rows[index].gpio->INDR & (1U << rows[index].pin)) != 0;
    /* Reject any sample interrupted by a scan, plus uncertain edges between reads. */
    if (before != scans || counter < 10U || counter >= 90U ||
        (level && level < 100U && counter+10U >= level && counter <= level+10U)) return false;
    *row = index; *duty = level; *high = pin_high; *expected = counter < level;
    return true;
}
