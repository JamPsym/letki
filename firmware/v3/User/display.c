#include "display.h"
#include "ch32v00x.h"

/* Front of the PCB, left to right and top to bottom.
 * Decoder drives cathode columns S1..S8; GPIO drives anode rows D8..D1.
 * Keep PD1 (SWIO), PA2/PD0 (buttons), PC1/PC2 (I2C), PD5/PD6 (UART) free.
 */
struct drive_pin { GPIO_TypeDef *port; uint8_t pin; };
static const struct drive_pin rows[8] = {
    {GPIOD, 7}, {GPIOC, 0}, {GPIOD, 3}, {GPIOD, 4},
    {GPIOC, 4}, {GPIOC, 3}, {GPIOA, 1}, {GPIOD, 2},
};

#define ROWS_A (1U << 1)
#define ROWS_C ((1U << 0) | (1U << 3) | (1U << 4))
#define ROWS_D ((1U << 2) | (1U << 3) | (1U << 4) | (1U << 7))
#define ADDRESS_C ((1U << 5) | (1U << 6) | (1U << 7))

#ifdef DISPLAY_LEVELS
static uint16_t frames[2][64]; /* Fixed per-pixel timer duties, no heap. */
#else
static uint8_t frames[2][8];
#endif
static volatile uint8_t active_frame;
/* Zero means no pending frame; 1 and 2 identify buffers 0 and 1. */
static volatile uint8_t pending_frame;
#ifdef DISPLAY_GENERAL
static volatile uint16_t pending_generation, presented_generation;
bool display_present_tagged(const uint8_t levels[64], uint16_t generation)
{
    /* Only foreground publishes; SysTick cannot consume the tag until pending
       is set inside display_present_levels. */
    if (pending_frame) return false;
    pending_generation = generation;
    return display_present_levels(levels);
}
uint16_t display_presented_generation(void) { return presented_generation; }
#endif
static uint8_t scan_column;
static volatile uint8_t requested_brightness = 100;
/* Gamma 2.2: round(1200 * (percent/100)^2.2), with nonzero input
 * clamped to at least one timer tick. Flash-only table; no floating point
 * or formatting in the scan ISR. 12 MHz / 1200 retains the 100 us period.
 */
#define PWM_TICKS 1200U
static const uint16_t gamma_duty[101] = {
    0, 1, 1, 1, 1, 2, 2, 3, 5, 6,
    8, 9, 11, 13, 16, 18, 21, 24, 28, 31,
    35, 39, 43, 47, 52, 57, 62, 67, 73, 79,
    85, 91, 98, 105, 112, 119, 127, 135, 143, 151,
    160, 169, 178, 187, 197, 207, 217, 228, 239, 250,
    261, 273, 285, 297, 309, 322, 335, 348, 362, 376,
    390, 404, 419, 434, 450, 465, 481, 497, 514, 530,
    548, 565, 583, 600, 619, 637, 656, 675, 695, 714,
    734, 755, 775, 796, 818, 839, 861, 883, 906, 929,
    952, 975, 999, 1023, 1047, 1072, 1097, 1122, 1148, 1174,
    1200,
};
#ifndef DISPLAY_LEVELS
static uint16_t brightness = PWM_TICKS;
#endif
static uint32_t gate_a, gate_c, gate_d;

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

#ifdef DISPLAY_GENERAL
void display_suspend(void)
{
    TIM2->DMAINTENR = 0;
    TIM2->INTFR = 0;
    TIM1->CTLR1 = TIM2->CTLR1 = 0;
    blank_rows();
    for (unsigned buffer=0; buffer<2; ++buffer)
        for (unsigned pixel=0; pixel<64; ++pixel) frames[buffer][pixel]=0;
    pending_frame=active_frame=scan_column=0;
}
#endif

static void timer_init(TIM_TypeDef *timer)
{
    timer->CTLR1 = timer->CTLR2 = timer->SMCFGR = timer->DMAINTENR = 0;
    timer->CCER = 0x1111U; /* Main channels only; SWIO complementary output stays off. */
    timer->CHCTLR1 = timer->CHCTLR2 = 0x4040U;
    timer->PSC = SystemCoreClock/12000000U-1U;
    timer->ATRLR = PWM_TICKS - 1U;
    timer->CH1CVR = timer->CH2CVR = timer->CH3CVR = timer->CH4CVR = 0;
    timer->SWEVGR = TIM_UG;
    timer->INTFR = 0;
}

void display_init(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC |
                     RCC_APB2Periph_GPIOD | RCC_APB2Periph_TIM1 | RCC_AFIOEN;
    RCC->APB1PCENR |= RCC_APB1Periph_TIM2;
    AFIO->PCFR1 &= ~(AFIO_PCFR1_TIM1_REMAP | AFIO_PCFR1_TIM2_REMAP | AFIO_PCFR1_TIM1_1_RM);
    GPIOA->BSHR = ROWS_A << 16;
    GPIOC->BSHR = ROWS_C << 16;
    GPIOD->BSHR = ROWS_D << 16;
    timer_init(TIM1); timer_init(TIM2);
    TIM1->RPTCR = 0; TIM1->BDTR = TIM_MOE;
    GPIOC->BSHR = ADDRESS_C << 16;
    for (unsigned row = 0; row < 8; ++row)
    {
        const unsigned shift = rows[row].pin * 4U;
        rows[row].port->CFGLR = (rows[row].port->CFGLR & ~(0xFU << shift)) |
                               (0x3U << shift);
    }
    for (unsigned pin = 5; pin <= 7; ++pin)
    {
        const unsigned shift = pin * 4U;
        GPIOC->CFGLR = (GPIOC->CFGLR & ~(0xFU << shift)) | (0x3U << shift);
    }
}

void display_brightness(uint8_t percent)
{
    if (percent <= 100U) requested_brightness = percent;
}
uint8_t display_brightness_get(void) { return requested_brightness; }

#ifdef DISPLAY_LEVELS
bool display_present_levels(const uint8_t levels[64])
{
    if (pending_frame != 0) return false;
    for (unsigned i = 0; i < 64; ++i)
        if (levels[i] > 100U) return false;
    const uint8_t next = active_frame ^ 1U;
    const unsigned percent = requested_brightness;
    for (unsigned i = 0; i < 64; ++i)
        frames[next][i] = gamma_duty[(levels[i]*percent + 50U)/100U];
    __asm__ volatile ("" ::: "memory");
    pending_frame = next + 1U;
    return true;
}
#else
bool display_present(const uint8_t columns[8])
{
    if (pending_frame != 0)
        return false;
    const uint8_t next = active_frame ^ 1U;
    for (unsigned column = 0; column < 8; ++column)
        frames[next][column] = columns[column];
    /* Publish the completed buffer after all pixel writes. */
    __asm__ volatile ("" ::: "memory");
    pending_frame = next + 1U;
    return true;
}

#endif

void display_tick(void)
{
    /* Timer AF owns the rows: force low before changing the decoder. */
    blank_rows();
    TIM2->DMAINTENR = 0;
    TIM1->CTLR1 = TIM2->CTLR1 = 0;
#ifndef DISPLAY_LEVELS
    if (scan_column == 0) brightness = gamma_duty[requested_brightness];
#endif
    if (scan_column == 0 && pending_frame != 0)
    {
        active_frame = pending_frame - 1U;
        pending_frame = 0;
#ifdef DISPLAY_GENERAL
        presented_generation = pending_generation;
#endif
    }
    /* A0=PC7, A1=PC6, A2=PC5, as in the verified strip test. */
    const uint32_t address = ((scan_column & 1U) << 7) |
                             ((scan_column & 2U) << 5) |
                             ((scan_column & 4U) << 3);
    GPIOC->BSHR = ((ADDRESS_C & ~address) << 16) | address;
#ifdef DISPLAY_LEVELS
    const uint16_t *duty = &frames[active_frame][scan_column*8U];
    TIM2->CH4CVR = duty[0]; TIM2->CH3CVR = duty[1];
    TIM2->CH2CVR = duty[2]; TIM2->CH1CVR = duty[3];
    TIM1->CH4CVR = duty[4]; TIM1->CH3CVR = duty[5];
    TIM1->CH2CVR = duty[6]; TIM1->CH1CVR = duty[7];
    uint8_t mask = 0;
    for (unsigned i = 0; i < 8; ++i)
        if (duty[i]) mask |= 1U << i;
#else
    const uint8_t pixels = frames[active_frame][scan_column];
    /* Default WCH mappings, D8..D1: TIM2 CH4..1, TIM1 CH4..1. */
    TIM2->CH4CVR = pixels & 0x01U ? brightness : 0;
    TIM2->CH3CVR = pixels & 0x02U ? brightness : 0;
    TIM2->CH2CVR = pixels & 0x04U ? brightness : 0;
    TIM2->CH1CVR = pixels & 0x08U ? brightness : 0;
    TIM1->CH4CVR = pixels & 0x10U ? brightness : 0;
    TIM1->CH3CVR = pixels & 0x20U ? brightness : 0;
    TIM1->CH2CVR = pixels & 0x40U ? brightness : 0;
    TIM1->CH1CVR = pixels & 0x80U ? brightness : 0;
    const uint8_t mask = brightness ? pixels : 0;
#endif
    gate_a = 0x30U | ((mask & 0x40U) ? 0x80U : 0);
    gate_c = 0x33003U | ((mask & 2U) ? 8U : 0) |
             ((mask & 0x10U) ? 0x80000U : 0) | ((mask & 0x20U) ? 0x8000U : 0);
    gate_d = 0x30033300U | ((mask & 1U) ? 0x80000000U : 0) |
             ((mask & 4U) ? 0x8000U : 0) | ((mask & 8U) ? 0x80000U : 0) |
             ((mask & 0x80U) ? 0x800U : 0);
    TIM1->SWEVGR = TIM2->SWEVGR = TIM_UG;
    TIM1->INTFR = TIM2->INTFR = 0;
    TIM2->DMAINTENR = TIM_UIE;
    TIM1->CTLR1 = TIM2->CTLR1 = TIM_CEN;
    scan_column = (scan_column + 1U) & 7U;
}

void display_unblank(void)
{
    if (!(TIM2->INTFR & TIM_UIF)) return;
    TIM2->INTFR = 0;
    TIM2->DMAINTENR = 0;
    TIM1->CHCTLR1 = TIM1->CHCTLR2 = 0x6060U;
    TIM2->CHCTLR1 = TIM2->CHCTLR2 = 0x6060U;
    GPIOA->CFGLR = (GPIOA->CFGLR & ~0xf0U) | gate_a;
    GPIOC->CFGLR = (GPIOC->CFGLR & ~0xff00fU) | gate_c;
    GPIOD->CFGLR = (GPIOD->CFGLR & ~0xf00fff00U) | gate_d;
}
