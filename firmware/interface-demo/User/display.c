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

static uint8_t frames[2][8];
static volatile uint8_t active_frame;
/* Zero means no pending frame; 1 and 2 identify buffers 0 and 1. */
static volatile uint8_t pending_frame;
static uint8_t scan_column;

static void blank_rows(void)
{
    GPIOA->BSHR = ROWS_A << 16;
    GPIOC->BSHR = ROWS_C << 16;
    GPIOD->BSHR = ROWS_D << 16;
}

void display_init(void)
{
    RCC->APB2PCENR |= RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOC |
                     RCC_APB2Periph_GPIOD;
    blank_rows();
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

void display_tick(void)
{
    /* Decoder enables are fixed: extinguish anodes before switching columns. */
    blank_rows();
    if (scan_column == 0 && pending_frame != 0)
    {
        active_frame = pending_frame - 1U;
        pending_frame = 0;
    }
    /* A0=PC7, A1=PC6, A2=PC5, as in the verified strip test. */
    const uint32_t address = ((scan_column & 1U) << 7) |
                             ((scan_column & 2U) << 5) |
                             ((scan_column & 4U) << 3);
    GPIOC->BSHR = ((ADDRESS_C & ~address) << 16) | address;
    const uint8_t pixels = frames[active_frame][scan_column];
    uint32_t a = 0, c = 0, d = 0;
    for (unsigned row = 0; row < 8; ++row)
    {
        if ((pixels & (1U << row)) == 0)
            continue;
        const uint32_t pin = 1U << rows[row].pin;
        if (rows[row].port == GPIOA) a |= pin;
        else if (rows[row].port == GPIOC) c |= pin;
        else d |= pin;
    }
    GPIOA->BSHR = a;
    GPIOC->BSHR = c;
    GPIOD->BSHR = d;
    scan_column = (scan_column + 1U) & 7U;
}
