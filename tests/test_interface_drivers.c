#include <assert.h>
#include <string.h>
#include "ch32v00x.h"
#include "bus.h"
#include "uart.h"
#include "protocol.h"

I2C_TypeDef fake_i2c;
USART_TypeDef fake_usart;
static unsigned reports, irq_disabled;
static bool last_success;
static uint16_t last_counter;
static const char *last_reason;
void RCC_APB1PeriphClockCmd(unsigned p, int e) { (void)p; (void)e; }
void RCC_APB2PeriphClockCmd(unsigned p, int e) { (void)p; (void)e; }
void GPIO_Init(void *p, GPIO_InitTypeDef *c) { (void)p; (void)c; }
void GPIO_PinRemapConfig(unsigned p, int e) { (void)p; (void)e; }
void I2C_DeInit(I2C_TypeDef *p) { memset(p, 0, sizeof(*p)); }
void I2C_Init(I2C_TypeDef *p, I2C_InitTypeDef *c) {
    assert(c->I2C_ClockSpeed == 100000);
    p->OADDR1 = c->I2C_OwnAddress1;
    p->CTLR1 = c->I2C_Ack;
}
void I2C_Cmd(I2C_TypeDef *p, int e) { if (e) p->CTLR1 |= I2C_CTLR1_PE; }
void USART_Init(USART_TypeDef *p, USART_InitTypeDef *c) {
    (void)p;
    assert(c->USART_BaudRate == 115200);
    assert(c->USART_Mode == (USART_Mode_Tx | USART_Mode_Rx));
}
void USART_Cmd(USART_TypeDef *p, int e) { (void)p; (void)e; }
void __disable_irq(void) { assert(!irq_disabled); irq_disabled = 1; }
void __enable_irq(void) { assert(irq_disabled); irq_disabled = 0; }
static void report(bool success, uint16_t counter, const char *reason) {
    ++reports; last_success = success; last_counter = counter; last_reason = reason;
}
static void step(uint16_t status, uint16_t status2, uint32_t now) {
    fake_i2c.STAR1 = status; fake_i2c.STAR2 = status2; bus_poll(now, report);
}

static void controller_reply(uint16_t counter, bool good)
{
    uint8_t packet[4]; packet_encode(packet, counter);
    bus_init(BUS_CONTROLLER);
    assert(bus_send(counter, 0));
    assert(!bus_send(counter + 1, 0));
    step(0, 0, 1); assert(fake_i2c.CTLR1 & I2C_CTLR1_START);
    step(I2C_STAR1_SB, I2C_STAR2_BUSY, 2); assert(fake_i2c.DATAR == 0x64);
    /* TXE alone must not start data before the address is acknowledged. */
    step(I2C_STAR1_TXE, I2C_STAR2_BUSY, 3); assert(fake_i2c.DATAR == 0x64);
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY, 4);
    for (unsigned i = 0; i < 4; ++i) {
        step(I2C_STAR1_TXE, I2C_STAR2_BUSY, 5 + i);
        assert(fake_i2c.DATAR == packet[i]);
    }
    step(I2C_STAR1_BTF, I2C_STAR2_BUSY, 9);
    assert(fake_i2c.CTLR1 & I2C_CTLR1_STOP);
    /* Emulate the hardware completing STOP. */
    fake_i2c.CTLR1 &= ~I2C_CTLR1_STOP;
    step(0, 0, 10);
    step(I2C_STAR1_SB, I2C_STAR2_BUSY, 11); assert(fake_i2c.DATAR == 0x65);
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY, 12);
    assert(!(fake_i2c.CTLR1 & I2C_CTLR1_ACK));
    assert(fake_i2c.CTLR1 & I2C_CTLR1_STOP);
    assert(!irq_disabled);
    fake_i2c.DATAR = packet[3] ^ (good ? 0 : 1);
    step(I2C_STAR1_RXNE, I2C_STAR2_BUSY, 13);
    fake_i2c.CTLR1 &= ~I2C_CTLR1_STOP;
    const unsigned before = reports;
    step(0, 0, 14);
    assert(reports == before + 1 && last_success == good);
    assert(last_counter == counter && !bus_busy());
    assert(fake_i2c.CTLR1 & I2C_CTLR1_ACK);
}

static void target_receive(uint16_t counter, bool good)
{
    uint8_t packet[4]; packet_encode(packet, counter);
    if (!good) packet[3] ^= 1;
    bus_init(BUS_TARGET); assert(fake_i2c.OADDR1 == 0x64);
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY, 0);
    for (unsigned i = 0; i < 4; ++i) {
        fake_i2c.DATAR = packet[i]; step(I2C_STAR1_RXNE, I2C_STAR2_BUSY, i + 1);
    }
    const unsigned before = reports;
    step(I2C_STAR1_STOPF, 0, 5);
    assert(reports == before + 1 && last_success == good);
    if (good) assert(last_counter == counter);
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY | I2C_STAR2_TRA, 6);
    step(I2C_STAR1_TXE, I2C_STAR2_BUSY | I2C_STAR2_TRA, 7);
    assert((fake_i2c.DATAR == packet_crc(packet, 3)) == good);
    step(I2C_STAR1_AF, 0, 8);
    assert(!(fake_i2c.STAR1 & I2C_STAR1_AF) && !bus_busy());
}

static uint8_t received_byte;
static void receive(uint8_t byte) { received_byte = byte; }
int main(void)
{
    controller_reply(0, true); controller_reply(65535, true); controller_reply(42, false);
    bus_init(BUS_CONTROLLER); assert(bus_send(7, 0));
    step(I2C_STAR1_AF, 0, 1);
    assert(!last_success && !strcmp(last_reason, "NACK") && !bus_busy());
    assert(bus_send(8, 0)); step(0, I2C_STAR2_BUSY, 100);
    assert(!last_success && !strcmp(last_reason, "timeout") && !bus_busy());
    /* Wraparound-safe deadline. */
    assert(bus_send(9, UINT32_MAX - 50)); step(0, I2C_STAR2_BUSY, 50);
    assert(!strcmp(last_reason, "timeout"));
    target_receive(1234, true); target_receive(1234, false);
    bus_init(BUS_OFF); assert(!bus_send(1, 0));
    uart_init();
    fake_usart.STATR = USART_STATR_TXE;
    assert(uart_write("ABC"));
    uart_poll(receive); assert(fake_usart.DATAR == 'A');
    uart_poll(receive); assert(fake_usart.DATAR == 'B');
    uart_poll(receive); assert(fake_usart.DATAR == 'C');
    fake_usart.STATR = USART_STATR_RXNE; fake_usart.DATAR = 'x';
    uart_poll(receive); assert(received_byte == 'x');
    fake_usart.STATR = USART_STATR_RXNE | USART_STATR_ORE;
    uart_poll(receive); assert(received_byte == 0 && uart_errors() == 1);
    char large[256]; memset(large, 'x', 255); large[255] = 0;
    assert(uart_write(large)); assert(!uart_write("x") && uart_dropped() == 1);
    return 0;
}
