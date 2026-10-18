#include "display.h"
#include "ch32v00x.h"

/* Communication-only image for the 33-ohm MOSFET tile. No LED scan, PWM,
 * frame buffers or HIGH row-gate writes. Preserve SWIO/UART/I2C/button pins.
 */
#define ROWS_A (1U << 1)
#define ROWS_C ((1U << 0) | (1U << 3) | (1U << 4))
#define ROWS_D ((1U << 2) | (1U << 3) | (1U << 4) | (1U << 7))
#define ADDRESS_C ((1U << 5) | (1U << 6) | (1U << 7))

static void blank_rows(void)
{
    GPIOA->BSHR = ROWS_A << 16;
    GPIOC->BSHR = ROWS_C << 16;
    GPIOD->BSHR = ROWS_D << 16;
}

static void output_low(GPIO_TypeDef *port, uint32_t pins)
{
    for (unsigned pin = 0; pin < 8; ++pin)
        if (pins & (1U << pin))
            port->CFGLR = (port->CFGLR & ~(0xFU << (pin * 4U))) |
                          (0x3U << (pin * 4U));
}

void display_init(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC |
                     RCC_APB2Periph_GPIOD | RCC_APB2Periph_TIM1;
    RCC->APB1PCENR |= RCC_APB1Periph_TIM2;
    /* Stop any previous timer state before selecting driven-low GPIO. */
    TIM1->CTLR1 = TIM2->CTLR1 = 0;
    TIM1->CCER = TIM2->CCER = 0;
    TIM1->BDTR = 0;
    TIM1->DMAINTENR = TIM2->DMAINTENR = 0;
    TIM1->INTFR = TIM2->INTFR = 0;
    blank_rows();
    GPIOC->BSHR = ADDRESS_C << 16;
    output_low(GPIOA, ROWS_A);
    output_low(GPIOC, ROWS_C | ADDRESS_C);
    output_low(GPIOD, ROWS_D);
}

bool display_present(const uint8_t columns[8])
{
    (void)columns;
    return true; /* Interface status pixels are deliberately not displayed. */
}

void display_tick(void)
{
    blank_rows();
}
