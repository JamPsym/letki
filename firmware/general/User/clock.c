/* CH32V003 RM v1.9 chapter 14: ENGC enables address-zero general call.
 * UART remains the addressed data path; this seven-byte message is a clock
 * beacon only, with magic avoiding reserved general-call command values. */
#include "clock.h"
#include "ch32v00x.h"
#include "general.h"
#ifndef GENERAL_TILE
#define GENERAL_TILE 1
#endif
static struct {
  uint32_t started, last;
  int32_t offset;
  uint16_t session;
  uint8_t bytes[7], index, phase;
  bool head, valid, regressed;
} clock_state;
void lg_clock_init(bool head) {
  clock_state.head = head;
  clock_state.phase = clock_state.index = 0;
  RCC_APB1PeriphClockCmd(RCC_APB1Periph_I2C1, ENABLE);
  I2C_DeInit(I2C1);
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
  config.I2C_OwnAddress1 = (head ? 0x31U : 0x31U + GENERAL_TILE) << 1;
  config.I2C_Ack = I2C_Ack_Enable;
  config.I2C_AcknowledgedAddress = I2C_AcknowledgedAddress_7bit;
  I2C_Init(I2C1, &config);
  if (!head)
    I2C1->CTLR1 |= I2C_CTLR1_ENGC;
  I2C_Cmd(I2C1, ENABLE);
}
void lg_clock_session(uint16_t session) {
  if (session != clock_state.session) {
    if (clock_state.regressed)
      clock_state.valid = false;
    clock_state.regressed = false;
    clock_state.session = session;
  }
}
uint16_t lg_clock_age(uint32_t local) {
  if (clock_state.head)
    return 0;
  uint32_t age = local - clock_state.last;
  return !clock_state.valid || clock_state.regressed ? 65535
         : age > 65534                               ? 65534
                                                     : (uint16_t)age;
}
static void receive_end(uint32_t now) {
  if (clock_state.index != 7 || clock_state.bytes[0] != 0xc1 ||
      lg_u16(clock_state.bytes + 5) != lg_crc(clock_state.bytes, 5))
    return;
  uint32_t remote =
      lg_u32(clock_state.bytes + 1) + 1; /* nominal 0.8ms wire time */
  if (clock_state.valid &&
      (int32_t)(remote - (now + clock_state.offset)) < -100) {
    clock_state.regressed = true;
    return;
  }
  if (clock_state.regressed)
    return;
  clock_state.offset = (int32_t)(remote - now);
  clock_state.last = now;
  clock_state.valid = true;
}
uint32_t lg_clock_poll(uint32_t now) {
  /* Flash maintenance can leave the last byte and STOP pending. Expire the
   * transaction before accepting its timestamp: it describes its start time,
   * not the time at which foreground polling finally resumes. */
  if (clock_state.phase && (uint32_t)(now - clock_state.started) > 20) {
    lg_clock_init(clock_state.head);
    return now + clock_state.offset;
  }
  uint16_t status = I2C1->STAR1;
  if (status &
      (I2C_STAR1_BERR | I2C_STAR1_ARLO | I2C_STAR1_OVR | I2C_STAR1_AF)) {
    if (clock_state.head && !(status & I2C_STAR1_ARLO))
      I2C1->CTLR1 |= I2C_CTLR1_STOP;
    lg_clock_init(clock_state.head);
    return now + clock_state.offset;
  }
  if (!clock_state.head) {
    if (status & I2C_STAR1_ADDR) {
      /* STAR1 read then STAR2 clears ADDR. Only general-call writes accepted.
       */
      uint16_t secondary = I2C1->STAR2;
      clock_state.phase =
          (secondary & I2C_STAR2_GENCALL) && !(secondary & I2C_STAR2_TRA);
      clock_state.index = 0;
      clock_state.started = now;
    }
    if (status & I2C_STAR1_RXNE) {
      uint8_t byte = (uint8_t)I2C1->DATAR;
      if (clock_state.phase && clock_state.index < 7)
        clock_state.bytes[clock_state.index++] = byte;
      else
        clock_state.phase = 0;
    }
    if (status & I2C_STAR1_STOPF) {
      if (I2C1->STAR1 & I2C_STAR1_RXNE) {
        uint8_t byte = (uint8_t)I2C1->DATAR;
        if (clock_state.phase && clock_state.index < 7)
          clock_state.bytes[clock_state.index++] = byte;
        else
          clock_state.phase = 0;
      }
      I2C1->CTLR1 |= I2C_CTLR1_PE;
      if (clock_state.phase)
        receive_end(now);
      clock_state.phase = 0;
    }
  } else {
    switch (clock_state.phase) {
    case 0:
      if ((uint32_t)(now - clock_state.last) < 100)
        break;
      if (I2C1->STAR2 & I2C_STAR2_BUSY) {
        /* A missing STOP (for example while a receiver is probed) must not
         * leave the head idle forever. Use the common bounded reset path. */
        clock_state.phase = 5;
        clock_state.started = now;
        break;
      }
      clock_state.bytes[0] = 0xc1;
      lg_put32(clock_state.bytes + 1, now);
      lg_put16(clock_state.bytes + 5, lg_crc(clock_state.bytes, 5));
      clock_state.last = clock_state.started = now;
      clock_state.index = 0;
      I2C1->CTLR1 |= I2C_CTLR1_START;
      clock_state.phase = 1;
      break;
    case 1:
      if (status & I2C_STAR1_SB) {
        I2C1->DATAR = 0;
        clock_state.phase = 2;
      }
      break;
    case 2:
      if (status & I2C_STAR1_ADDR) {
        (void)I2C1->STAR2;
        clock_state.phase = 3;
      }
      break;
    case 3:
      if (status & I2C_STAR1_TXE) {
        I2C1->DATAR = clock_state.bytes[clock_state.index++];
        if (clock_state.index == 7)
          clock_state.phase = 4;
      }
      break;
    case 4:
      if (status & I2C_STAR1_BTF) {
        I2C1->CTLR1 |= I2C_CTLR1_STOP;
        clock_state.phase = 0;
      }
      break;
    case 5:
      if (!(I2C1->STAR2 & I2C_STAR2_BUSY))
        clock_state.phase = 0;
      break;
    }
  }
  return now + clock_state.offset;
}
