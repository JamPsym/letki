#pragma once
#include <cstdint>
struct GPIO_TypeDef;
struct WriteRegister { GPIO_TypeDef *gpio; void operator=(uint32_t value); };
struct GPIO_TypeDef {
    uint32_t CFGLR = 0x44444444, INDR = 0, OUTDR = 0;
    WriteRegister BSHR{this};
};
struct TIM_TypeDef {
    uint32_t CTLR1=0, CTLR2=0, SMCFGR=0, DMAINTENR=0, CCER=0;
    uint32_t CHCTLR1=0, CHCTLR2=0, PSC=0, ATRLR=0;
    uint32_t CH1CVR=0, CH2CVR=0, CH3CVR=0, CH4CVR=0;
    uint32_t SWEVGR=0, INTFR=0, RPTCR=0, BDTR=0, CNT=0;
};
struct RCC_TypeDef { uint32_t APB1PCENR=0, APB2PCENR=0; };
struct AFIO_TypeDef { uint32_t PCFR1=0; };
extern GPIO_TypeDef gpio_a, gpio_c, gpio_d;
extern TIM_TypeDef timer_1, timer_2;
extern RCC_TypeDef rcc;
extern AFIO_TypeDef afio;
extern uint32_t SystemCoreClock;
#define GPIOA (&gpio_a)
#define GPIOC (&gpio_c)
#define GPIOD (&gpio_d)
#define TIM1 (&timer_1)
#define TIM2 (&timer_2)
#define RCC (&rcc)
#define AFIO (&afio)
#define RCC_APB2Periph_GPIOA 0x4U
#define RCC_APB2Periph_GPIOC 0x10U
#define RCC_APB2Periph_GPIOD 0x20U
#define RCC_APB2Periph_TIM1 0x800U
#define RCC_AFIOEN 1U
#define RCC_APB1Periph_TIM2 1U
#define AFIO_PCFR1_TIM1_REMAP 0xc0U
#define AFIO_PCFR1_TIM2_REMAP 0x300U
#define AFIO_PCFR1_TIM1_1_RM 0x800000U
#define TIM_MOE 0x8000U
#define TIM_UG 1U
#define TIM_CEN 1U
#define TIM_UIE 1U
#define TIM_UIF 1U
