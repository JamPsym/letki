#include "display_pwm.h"

#include "ch32v00x.h"
#include "display_hw.h"

#include <stddef.h>

#define MODIFY_REG(REG, CLEARMASK, SETMASK) ((REG) = (((REG) & (~(CLEARMASK))) | (SETMASK)))
#define SET_BIT(REG, BIT) ((REG) |= (BIT))
#define CLEAR_BIT(REG, BIT) ((REG) &= ~(BIT))

static void configure_pwm_gpio(void);
static void configure_pwm_timers(void);

void display_pwm_init(void)
{
    configure_pwm_gpio();
    configure_pwm_timers();
}

void display_pwm_write_raw(uint8_t level)
{
    TIM1->CH1CVR = level;
    TIM1->CH2CVR = level;
    TIM1->CH3CVR = level;
    TIM1->CH4CVR = level;

    TIM2->CH1CVR = level;
    TIM2->CH2CVR = level;
    TIM2->CH3CVR = level;
    TIM2->CH4CVR = level;
}

static void configure_pwm_gpio(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC | RCC_APB2Periph_GPIOD | RCC_AFIOEN;

    for(size_t i = 0; i < 8; ++i)
    {
        GPIO_TypeDef *sink_port = (GPIO_TypeDef *)column_sink_lines[i].gpio_base;
        uint32_t sink_pin = column_sink_lines[i].pin;
        MODIFY_REG(sink_port->CFGLR, 0xFU << (sink_pin * 4), 0b0011U << (sink_pin * 4)); // push-pull output
        CLEAR_BIT(sink_port->OUTDR, 1U << sink_pin);

        GPIO_TypeDef *drive_port = (GPIO_TypeDef *)row_drive_lines[i].gpio_base;
        uint32_t drive_pin = row_drive_lines[i].pin;
        MODIFY_REG(drive_port->CFGLR, 0xFU << (drive_pin * 4), 0b1011U << (drive_pin * 4)); // AF push-pull
    }

    MODIFY_REG(AFIO->PCFR1, AFIO_PCFR1_SWJ_CFG, AFIO_PCFR1_SWJ_CFG_DISABLE);
}

static void configure_pwm_timers(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_TIM1;
    RCC->APB1PCENR |= RCC_APB1Periph_TIM2;

    TIM1->PSC = SystemCoreClock/1000000U - 1U; // 1 MHz
    TIM1->ATRLR = 0xFF;
    display_pwm_write_raw(0);

    SET_BIT(TIM1->CHCTLR1, TIM_OC1M_2 | TIM_OC1M_1 | TIM_OC1PE | TIM_OC2M_2 | TIM_OC2M_1 | TIM_OC2PE);
    SET_BIT(TIM1->CHCTLR2, TIM_OC3M_2 | TIM_OC3M_1 | TIM_OC3PE | TIM_OC4M_2 | TIM_OC4M_1 | TIM_OC4PE);
    SET_BIT(TIM1->CTLR1, TIM_ARPE);
    SET_BIT(TIM1->BDTR, TIM_MOE);
    SET_BIT(TIM1->CCER, TIM_CC1E | TIM_CC2E | TIM_CC3E | TIM_CC4E);
    SET_BIT(TIM1->SWEVGR, TIM_UG);
    SET_BIT(TIM1->CTLR1, TIM_CEN);

    TIM2->PSC = SystemCoreClock/1000000U - 1U;
    TIM2->ATRLR = 0xFF;
    display_pwm_write_raw(0);

    SET_BIT(TIM2->CHCTLR1, TIM_OC1M_2 | TIM_OC1M_1 | TIM_OC1PE | TIM_OC2M_2 | TIM_OC2M_1 | TIM_OC2PE);
    SET_BIT(TIM2->CHCTLR2, TIM_OC3M_2 | TIM_OC3M_1 | TIM_OC3PE | TIM_OC4M_2 | TIM_OC4M_1 | TIM_OC4PE);
    SET_BIT(TIM2->CTLR1, TIM_ARPE);
    SET_BIT(TIM2->CCER, TIM_CC1E | TIM_CC2E | TIM_CC3E | TIM_CC4E);
    SET_BIT(TIM2->SWEVGR, TIM_UG);
    SET_BIT(TIM2->CTLR1, TIM_CEN);
}
