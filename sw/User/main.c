#include "ch32v00x.h"
#include "core_riscv.h"
#include "debug.h"
#include "display_hw.h"
#include "display_pwm.h"
#include "gamma.h"

#include "display_direct.h"

#include <wchar.h>

#include <stddef.h>
#include <stdio.h>

#define MODIFY_REG(REG, CLEARMASK, SETMASK) ((REG) = (((REG) & (~(CLEARMASK))) | (SETMASK)))
#define SET_BIT(REG, BIT) ((REG) |= (BIT))
#define CLEAR_BIT(REG, BIT) ((REG) &= ~(BIT))

static void delay_ms(uint32_t ms);
static void set_all_pwm(uint8_t level);

volatile uint32_t system_clock;
__attribute__((interrupt("WCH-Interrupt-fast"))) void SysTick_Handler()
{
    system_clock++;

    if(system_clock % 1000 == 0)
    {
        printf("sekundka %u \r\n", system_clock/1000);
    }

    SysTick->SR = 0;
}

int main(void)
{
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_1);
    SystemCoreClockUpdate();

    USART_Printf_Init(115200);
    printf("USART debug ready\r\n");

    SysTick->CMP = SystemCoreClock/1000;
    SET_BIT(SysTick->CTLR, 0b1111);
    NVIC_EnableIRQ(SysTick_IRQn);
    __enable_irq();

    // display_pwm_init();


    //  while(1)
    //  {
    //      for(uint16_t level = 0; level < GAMMA_TABLE_SIZE; ++level)
    //      {
    //          set_all_pwm((uint8_t)255);
    //          SET_BIT(TIM1->SWEVGR, TIM_UG);
    //          SET_BIT(TIM2->SWEVGR, TIM_UG);
    //          delay_ms(3);
    //      }

    //      for(int level = GAMMA_TABLE_SIZE - 1; level >= 0; --level)
    //      {
    //          set_all_pwm((uint8_t)255);
    //          SET_BIT(TIM1->SWEVGR, TIM_UG);
    //          SET_BIT(TIM2->SWEVGR, TIM_UG);
    //          delay_ms(3);
    //      }
    //  }


    display_direct_init();
    const wchar_t str[] = L" DOBRA DZIAŁA NIE UMIEM LUTOWAĆ ";
    const size_t str_cap = sizeof(str) / sizeof(str[0]);

    while(1)
    {
       render_loop(str, str_cap, 250, 2);
       //render_scroll_loop(str, str_cap, 50, 2);
    }
    
}

static void delay_ms(uint32_t ms)
{
    const uint32_t start = system_clock;
    while((uint32_t)(system_clock - start) < ms)
    {
    }
}


static void set_all_pwm(uint8_t level)
{
    const uint8_t corrected = gamma_correct(level);
    display_pwm_write_raw(corrected);
}
