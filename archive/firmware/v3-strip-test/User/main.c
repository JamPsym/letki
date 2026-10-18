#include "ch32v00x.h"

#define ROW_STEP_MS 100U

#define MODIFY_REG(REG, CLEARMASK, SETMASK) ((REG) = (((REG) & (~(CLEARMASK))) | (SETMASK)))
#define SET_BIT(REG, BIT) ((REG) |= (BIT))
#define CLEAR_BIT(REG, BIT) ((REG) &= ~(BIT))

struct gpio_line { uint32_t gpio_base; uint8_t pin; };

const struct gpio_line column_drive_lines[8] = {
    {GPIOD_BASE, 2},
    {GPIOA_BASE, 1},
    {GPIOC_BASE, 3},
    {GPIOC_BASE, 4},
    {GPIOD_BASE, 4},
    {GPIOD_BASE, 3},
    {GPIOC_BASE, 0},
    {GPIOD_BASE, 7},
};

const struct gpio_line row_sink_lines[3] = {
    {GPIOC_BASE, 5},
    {GPIOC_BASE, 6},
    {GPIOC_BASE, 7},
};

volatile uint32_t system_clock;
__attribute__((interrupt("WCH-Interrupt-fast"))) void SysTick_Handler()
{
    system_clock++;

    SysTick->SR = 0;
}

static void delay_ms(uint32_t ms)
{
    const uint32_t start = system_clock;
    while((uint32_t)(system_clock - start) < ms)
    {
    }
}

static void delay_init()
{
    SystemCoreClockUpdate();
    SysTick->CMP = SystemCoreClock/1000;
    SET_BIT(SysTick->CTLR, 0b1111);
    NVIC_EnableIRQ(SysTick_IRQn);
    __enable_irq();
}

int main(void)
{
    delay_init();

    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC | RCC_APB2Periph_GPIOD | RCC_AFIOEN;

    for(size_t i = 0; i < 8; ++i)
    {
        GPIO_TypeDef *drive_port = (GPIO_TypeDef *)column_drive_lines[i].gpio_base;
        uint32_t drive_pin = column_drive_lines[i].pin;
        MODIFY_REG(drive_port->CFGLR, 0xFU << (drive_pin * 4), 0b0011U << (drive_pin * 4)); // push-pull output
        SET_BIT(drive_port->OUTDR, 0x1 << drive_pin);
    }

    for(size_t i = 0; i < 3; ++i)
    {
        GPIO_TypeDef *sink_port = (GPIO_TypeDef *)row_sink_lines[i].gpio_base;
        uint32_t sink_pin = row_sink_lines[i].pin;
        MODIFY_REG(sink_port->CFGLR, 0xFU << (sink_pin * 4), 0b0011U << (sink_pin * 4)); // push-pull output
    }

    

    while(1)
    {
        static uint8_t line = 0;
        const uint8_t mask = 0b11100000;

        line++;
        line &= 7;
        uint8_t bit_reversal[8] = {0b000, 0b100, 0b010, 0b110, 0b001, 0b101, 0b011, 0b111};
        MODIFY_REG(GPIOC->OUTDR, mask, bit_reversal[line] << 5);
        delay_ms(ROW_STEP_MS);
    }
}
