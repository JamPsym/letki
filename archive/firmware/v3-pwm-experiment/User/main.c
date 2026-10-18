#include "ch32v00x.h"

#include "display_pwm.h"

#define GAMMA_TABLE_SIZE 256U
const uint8_t gamma_table[GAMMA_TABLE_SIZE] = {
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,
    3,3,3,3,3,4,4,4,4,5,5,5,5,6,6,6,6,7,7,7,8,8,8,9,9,9,10,10,11,11,
    11,12,12,13,13,13,14,14,15,15,16,16,17,17,18,18,19,19,20,20,21,22,
    22,23,23,24,25,25,26,26,27,28,28,29,30,30,31,32,33,33,34,35,35,36,
    37,38,39,39,40,41,42,43,43,44,45,46,47,48,49,49,50,51,52,53,54,55,
    56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,73,74,75,76,77,78,
    79,81,82,83,84,85,87,88,89,90,91,93,94,95,97,98,99,100,102,103,105,106,
    107,109,110,111,113,114,116,117,119,120,121,123,124,126,127,129,130,132,133,135,
    137,138,140,141,143,145,146,148,149,151,153,154,156,158,159,161,163,165,166,168,
    170,172,173,175,177,179,181,182,184,186,188,190,192,194,196,197,199,201,203,205,
    207,209,211,213,215,217,219,221,223,225,227,229,231,234,236,238,240,242,244,246,
    248,251,253,255
};
static inline uint8_t gamma_correct(uint8_t level)
{
    return gamma_table[level];
}


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

static void delay_ms(uint32_t ms);
static void set_all_pwm(uint8_t level);
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

    //////////////

    // display_pwm_init();


     while(1)
     {
         for(uint16_t level = 0; level < GAMMA_TABLE_SIZE; ++level)
         {
             set_all_pwm((uint8_t)255);
             SET_BIT(TIM1->SWEVGR, TIM_UG);
             SET_BIT(TIM2->SWEVGR, TIM_UG);
             delay_ms(3);
         }

         for(int level = GAMMA_TABLE_SIZE - 1; level >= 0; --level)
         {
             set_all_pwm((uint8_t)255);
             SET_BIT(TIM1->SWEVGR, TIM_UG);
             SET_BIT(TIM2->SWEVGR, TIM_UG);
             delay_ms(3);
         }
     }

    //////////////

    

    while(1)
    {
        static uint8_t line = 0;
        const uint8_t mask = 0b11100000;

        line++;
        line &= 7;
        uint8_t bit_reversal[8] = {0b000, 0b100, 0b010, 0b110, 0b001, 0b101, 0b011, 0b111};
        MODIFY_REG(GPIOC->OUTDR, mask, bit_reversal[line] << 5);
        delay_ms(200);
    }
}


static void set_all_pwm(uint8_t level)
{
    const uint8_t corrected = gamma_correct(level);
    display_pwm_write_raw(corrected);
}
