#include "ch32v00x.h"
#include "display.h"
#include "swio.h"

static volatile uint32_t milliseconds;
static uint8_t scan_fraction;
static uint8_t frame[8];
static uint8_t step;
static bool paused;

static void report(void)
{
    if (step < 8U) swio_write("SCAN rows: top to bottom\r\n");
    else if (step < 16U) swio_write("SCAN columns: left to right\r\n");
    else swio_write("SCAN pixels: each row, left to right\r\n");
}

static void command(char key)
{
    switch (key) {
    case 'p': paused = true; swio_write("PAUSED\r\n"); break;
    case 'r': paused = false; swio_write("RESUMED\r\n"); break;
    case 's': report(); break;
    case 'h': swio_write("Scan demo: p pause; r resume; s phase\r\n"); break;
    default: break;
    }
}

static void pattern(void)
{
    for (unsigned col = 0; col < 8U; ++col) {
        if (step < 8U) frame[col] = 1U << step;
        else if (step < 16U) frame[col] = col == step-8U ? 0xffU : 0;
        else frame[col] = col == ((step-16U) & 7U) ? 1U << ((step-16U)/8U) : 0;
    }
}

void SysTick_Handler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void SysTick_Handler(void)
{
    SysTick->SR = 0;
    if (++scan_fraction == 2U) { scan_fraction = 0; ++milliseconds; }
    display_tick();
}

void TIM2_IRQHandler(void) __attribute__((interrupt("WCH-Interrupt-fast")));
void TIM2_IRQHandler(void) { display_unblank(); }

int main(void)
{
    SystemCoreClockUpdate();
    display_init();
    display_brightness(100);
    pattern();
    display_present(frame);
    SysTick->CTLR = 0;
    SysTick->CNT = 0;
    SysTick->CMP = SystemCoreClock/2000U-1U;
    SysTick->SR = 0;
    NVIC_EnableIRQ(SysTick_IRQn);
    NVIC_EnableIRQ(TIM2_IRQn);
    SysTick->CTLR = 0xfU;
    __enable_irq();
    swio_init();
    swio_write("Letki v3 SWIO ready. Row/column/pixel scan demo\r\n");
    report();
    uint32_t previous = 0;
    bool pending = false;
    for (;;) {
        swio_poll(command);
        const uint32_t now = milliseconds;
        if (paused) previous = now;
        else if (!pending && now-previous >= (step < 16U ? 600U : 150U)) {
            step = (step+1U)%80U;
            pattern();
            pending = true;
        }
        if (pending && display_present(frame)) {
            previous = now;
            pending = false;
            if (step == 0U || step == 8U || step == 16U) report();
        }
    }
}
