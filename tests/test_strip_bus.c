#include <assert.h>
#include <string.h>
#include "ch32v00x.h"
#include "frame_bus.h"
#include "protocol.h"

I2C_TypeDef fake_i2c;
USART_TypeDef fake_usart;
static unsigned reports, irq_disabled;
static bool last_success;
static struct strip_frame last_frame;
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
static void report(bool success, const struct strip_frame *frame) {
    ++reports; last_success = success; last_frame = *frame;
}
static void step(uint16_t status, uint16_t status2, uint32_t now) {
    fake_i2c.STAR1 = status; fake_i2c.STAR2 = status2; frame_bus_poll(now, report);
}

static void controller_reply(uint16_t counter, bool good, uint8_t address)
{
    struct strip_frame frame={.sequence=counter,.brightness=100,.pixels={1,2,3,4,5,6,7,8}};
    uint8_t packet[STRIP_PACKET_BYTES]; strip_encode(packet, &frame);
    frame_bus_init(false);
    assert(frame_bus_send_to(&frame, 0, address));
    assert(!frame_bus_send(&frame, 0));
    step(0, 0, 1); assert(fake_i2c.CTLR1 & I2C_CTLR1_START);
    step(I2C_STAR1_SB, I2C_STAR2_BUSY, 2); assert(fake_i2c.DATAR == (unsigned)address*2);
    /* TXE alone must not start data before the address is acknowledged. */
    step(I2C_STAR1_TXE, I2C_STAR2_BUSY, 3); assert(fake_i2c.DATAR == (unsigned)address*2);
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY, 4);
    for (unsigned i = 0; i < STRIP_PACKET_BYTES; ++i) {
        step(I2C_STAR1_TXE, I2C_STAR2_BUSY, 5 + i);
        assert(fake_i2c.DATAR == packet[i]);
    }
    step(I2C_STAR1_BTF, I2C_STAR2_BUSY, 19);
    assert(fake_i2c.CTLR1 & I2C_CTLR1_STOP);
    /* Emulate the hardware completing STOP. */
    fake_i2c.CTLR1 &= ~I2C_CTLR1_STOP;
    step(0, 0, 20);
    step(I2C_STAR1_SB, I2C_STAR2_BUSY, 21); assert(fake_i2c.DATAR == (unsigned)address*2+1);
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY, 22);
    assert(!(fake_i2c.CTLR1 & I2C_CTLR1_ACK));
    assert(fake_i2c.CTLR1 & I2C_CTLR1_STOP);
    assert(!irq_disabled);
    fake_i2c.DATAR = packet[13] ^ (good ? 0 : 1);
    step(I2C_STAR1_RXNE, I2C_STAR2_BUSY, 23);
    fake_i2c.CTLR1 &= ~I2C_CTLR1_STOP;
    const unsigned before = reports;
    step(0, 0, 24);
    assert(reports == before + 1 && last_success == good);
    assert(last_frame.sequence == counter && !frame_bus_busy());
    assert(fake_i2c.CTLR1 & I2C_CTLR1_ACK);
}

static void target_receive(uint16_t counter, bool good)
{
    struct strip_frame frame={.sequence=counter,.brightness=100,.pixels={1,2,3,4,5,6,7,8}};
    uint8_t packet[STRIP_PACKET_BYTES]; strip_encode(packet, &frame);
    if (!good) packet[13] ^= 1;
    frame_bus_init(true);
#ifdef STRIP_TILE
    assert(fake_i2c.OADDR1 == (0x31U+STRIP_TILE)*2);
#else
    assert(fake_i2c.OADDR1 == 0x64);
#endif
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY, 0);
    for (unsigned i = 0; i < STRIP_PACKET_BYTES; ++i) {
        fake_i2c.DATAR = packet[i]; step(I2C_STAR1_RXNE, I2C_STAR2_BUSY, i + 1);
    }
    const unsigned before = reports;
    step(I2C_STAR1_STOPF, 0, 15);
    assert(reports == before + 1 && last_success == good);
    if (good) assert(last_frame.sequence == counter);
    step(I2C_STAR1_ADDR, I2C_STAR2_BUSY | I2C_STAR2_TRA, 16);
    step(I2C_STAR1_TXE, I2C_STAR2_BUSY | I2C_STAR2_TRA, 17);
    assert((fake_i2c.DATAR == packet_crc(packet, 13)) == good);
    step(I2C_STAR1_AF, 0, 18);
    assert(!(fake_i2c.STAR1 & I2C_STAR1_AF) && !frame_bus_busy());
}

int main(void)
{
    for(uint8_t address=0x32;address<=0x35;++address) {
        controller_reply(0,true,address); controller_reply(65535,true,address); controller_reply(42,false,address);
    }
    struct strip_frame frame={.sequence=7,.brightness=100};
    frame_bus_init(false); assert(frame_bus_send(&frame,0));
    step(I2C_STAR1_AF,0,1); assert(!last_success && !frame_bus_busy());
    assert(frame_bus_send(&frame,0)); step(0,I2C_STAR2_BUSY,100);
    assert(!last_success && !frame_bus_busy());
    assert(frame_bus_send(&frame,UINT32_MAX-50)); step(0,I2C_STAR2_BUSY,50);
    assert(!last_success && !frame_bus_busy());
    target_receive(1234,true); target_receive(1234,false);
    return 0;
}
