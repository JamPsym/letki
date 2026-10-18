/* Frame transport derived from the previously tested foreground interface bus.
 * Separate buffers/API preserve the original four-byte diagnostic images. */
#include "frame_bus.h"
#include "protocol.h"
#include "ch32v00x.h"

#define ADDRESS 0x32U /* 7-bit address; WCH APIs take ADDRESS << 1. */
#ifndef STRIP_TILE
#define STRIP_TILE 1
#endif
static uint8_t destination=ADDRESS;
enum phase { IDLE, START_WRITE, ADDRESS_WRITE, WAIT_WRITE_ADDRESS, WRITE_BYTES, FINISH_WRITE,
             WAIT_STOP, START_READ, ADDRESS_READ, READ_REPLY, FINISH_READ };
static bool target;
static enum phase phase;
static uint8_t packet[STRIP_PACKET_BYTES], rx[STRIP_PACKET_BYTES], response;
static unsigned index, received;
static struct strip_frame transfer;
static uint32_t started;
static bool target_transmitting, target_active, target_valid;

void frame_bus_init(bool next)
{
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_I2C1, ENABLE);
    I2C_DeInit(I2C1);
    target = next;
    phase = IDLE;
    received = 0;
    response = 0;
    target_active = target_transmitting = target_valid = false;
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOC | RCC_APB2Periph_AFIO, ENABLE);
    GPIO_InitTypeDef gpio = {0};
    gpio.GPIO_Pin = GPIO_Pin_1 | GPIO_Pin_2;
    gpio.GPIO_Mode = GPIO_Mode_AF_OD;
    gpio.GPIO_Speed = GPIO_Speed_30MHz;
    GPIO_Init(GPIOC, &gpio);
    GPIO_PinRemapConfig(GPIO_FullRemap_I2C1, DISABLE);
    GPIO_PinRemapConfig(GPIO_PartialRemap_I2C1, DISABLE);
    I2C_InitTypeDef config = {0};
    config.I2C_ClockSpeed = 100000;
    config.I2C_Mode = I2C_Mode_I2C;
    config.I2C_DutyCycle = I2C_DutyCycle_2;
    config.I2C_OwnAddress1 = (next ? (STRIP_TILE ? 0x31U+STRIP_TILE : ADDRESS) : 0x31U) << 1;
    config.I2C_Ack = I2C_Ack_Enable;
    config.I2C_AcknowledgedAddress = I2C_AcknowledgedAddress_7bit;
    I2C_Init(I2C1, &config);
    I2C_Cmd(I2C1, ENABLE);
}

bool frame_bus_busy(void) { return phase != IDLE || target_active; }

static bool begin_send(const struct strip_frame *frame, uint32_t now)
{
    if (target || phase != IDLE) return false;
    strip_encode(packet, frame);
    transfer = *frame;
    index = 0;
    started = now;
    phase = START_WRITE;
    return true;
}
bool frame_bus_send_to(const struct strip_frame *frame, uint32_t now, uint8_t address)
{
    if (target || phase!=IDLE || address<0x32U || address>0x35U) return false;
    destination=address;
    return begin_send(frame,now);
}
bool frame_bus_send(const struct strip_frame *frame, uint32_t now)
{
    return frame_bus_send_to(frame,now,ADDRESS);
}

static void target_poll(uint32_t now,
                        void (*report)(bool, const struct strip_frame *))
{
    const uint16_t status = I2C1->STAR1;
    if (status & (I2C_STAR1_BERR | I2C_STAR1_ARLO | I2C_STAR1_OVR)) {
        frame_bus_init(true);
        report(false, &transfer);
        return;
    }
    if (status & I2C_STAR1_ADDR) {
        target_transmitting = (I2C1->STAR2 & I2C_STAR2_TRA) != 0;
        target_active = true;
        started = now;
        if (!target_transmitting) { received = 0; target_valid = false; }
    }
    if (!target_transmitting && (status & I2C_STAR1_RXNE)) {
        const uint8_t byte = (uint8_t)I2C1->DATAR;
        if (received < sizeof(rx)) rx[received] = byte;
        if (received < sizeof(rx) + 1U) ++received;
    }
    if (status & I2C_STAR1_STOPF) {
        /* STAR1 was read above; writing CTLR1 clears STOPF. Drain a final byte
           before validating the complete write transaction. */
        if (!target_transmitting && (I2C1->STAR1 & I2C_STAR1_RXNE)) {
            const uint8_t byte = (uint8_t)I2C1->DATAR;
            if (received < sizeof(rx)) rx[received] = byte;
            if (received < sizeof(rx) + 1U) ++received;
        }
        I2C1->CTLR1 |= I2C_CTLR1_PE;
        target_active = false;
        if (!target_transmitting) {
            target_valid = strip_decode(rx, received, &transfer);
            response = target_valid ? rx[13] : (uint8_t)(rx[13] ^ 0xFFU);
            report(target_valid, &transfer);
        }
    }
    if (target_transmitting && (status & I2C_STAR1_TXE))
        I2C1->DATAR = response;
    /* The controller deliberately NACKs the single reply byte. */
    if (status & I2C_STAR1_AF) {
        I2C1->STAR1 &= ~I2C_STAR1_AF;
        target_active = false;
    }
    if (target_active && (uint32_t)(now - started) >= 100U) {
        frame_bus_init(true);
        report(false, &transfer);
    }
}

void frame_bus_poll(uint32_t now, void (*report)(bool, const struct strip_frame *))
{
    if (target) { target_poll(now, report); return; }
    if (phase == IDLE) return;
    const uint16_t status = I2C1->STAR1;
    if ((status & (I2C_STAR1_AF | I2C_STAR1_BERR | I2C_STAR1_ARLO | I2C_STAR1_OVR)) ||
        (uint32_t)(now - started) >= 100U) {
        if (!(status & I2C_STAR1_ARLO)) I2C1->CTLR1 |= I2C_CTLR1_STOP;
        frame_bus_init(false);
        report(false, &transfer);
        return;
    }
    switch (phase) {
        case START_WRITE:
            if (!(I2C1->STAR2 & I2C_STAR2_BUSY)) {
                I2C1->CTLR1 |= I2C_CTLR1_START;
                phase = ADDRESS_WRITE;
            }
            break;
        case ADDRESS_WRITE:
            if (status & I2C_STAR1_SB) {
                I2C1->DATAR = destination << 1;
                phase = WAIT_WRITE_ADDRESS;
            }
            break;
        case WAIT_WRITE_ADDRESS:
            if (status & I2C_STAR1_ADDR) {
                (void)I2C1->STAR2;
                phase = WRITE_BYTES;
            }
            break;
        case WRITE_BYTES:
            if (status & I2C_STAR1_TXE) {
                I2C1->DATAR = packet[index++];
                if (index == sizeof(packet)) phase = FINISH_WRITE;
            }
            break;
        case FINISH_WRITE:
            if (status & I2C_STAR1_BTF) {
                I2C1->CTLR1 |= I2C_CTLR1_STOP;
                phase = WAIT_STOP;
            }
            break;
        case WAIT_STOP:
            if (!(I2C1->STAR2 & I2C_STAR2_BUSY) &&
                !(I2C1->CTLR1 & I2C_CTLR1_STOP)) {
                I2C1->CTLR1 |= I2C_CTLR1_START;
                phase = START_READ;
            }
            break;
        case START_READ:
            if (status & I2C_STAR1_SB) {
                I2C1->DATAR = (destination << 1) | 1U;
                phase = ADDRESS_READ;
            }
            break;
        case ADDRESS_READ:
            if (status & I2C_STAR1_ADDR) {
                /* One-byte receive: disable ACK before clearing ADDR, then
                   issue STOP before RXNE. Keep this sequence uninterrupted. */
                __disable_irq();
                I2C1->CTLR1 &= ~I2C_CTLR1_ACK;
                (void)I2C1->STAR2;
                I2C1->CTLR1 |= I2C_CTLR1_STOP;
                __enable_irq();
                phase = READ_REPLY;
            }
            break;
        case READ_REPLY:
            if (status & I2C_STAR1_RXNE) {
                response = (uint8_t)I2C1->DATAR;
                phase = FINISH_READ;
            }
            break;
        case FINISH_READ:
            if (!(I2C1->STAR2 & I2C_STAR2_BUSY) &&
                !(I2C1->CTLR1 & I2C_CTLR1_STOP)) {
                I2C1->CTLR1 |= I2C_CTLR1_ACK;
                phase = IDLE;
                report(response == packet[13], &transfer);
            }
            break;
        default: break;
    }
}
