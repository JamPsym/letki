#pragma once
#include <stdint.h>
struct DataRegister {
  uint16_t value = 0;
  operator uint16_t();
  DataRegister &operator=(uint16_t next) {
    value = next;
    return *this;
  }
};
struct I2C_TypeDef {
  uint16_t CTLR1 = 0, CTLR2 = 0, OADDR1 = 0, OADDR2 = 0;
  DataRegister DATAR;
  uint16_t STAR1 = 0, STAR2 = 0;
};
extern I2C_TypeDef fake_i2c;
inline DataRegister::operator uint16_t() {
  fake_i2c.STAR1 &= ~0x40;
  return value;
}
#define I2C1 (&fake_i2c)
#define GPIOC ((void *)1)
#define ENABLE 1
#define DISABLE 0
#define GPIO_Pin_1 2
#define GPIO_Pin_2 4
#define GPIO_Mode_AF_OD 1
#define GPIO_Speed_30MHz 0
#define GPIO_FullRemap_I2C1 0
#define GPIO_PartialRemap_I2C1 1
#define RCC_APB1Periph_I2C1 1
#define RCC_APB2Periph_GPIOC 2
#define RCC_APB2Periph_AFIO 8
#define I2C_Mode_I2C 0
#define I2C_DutyCycle_2 0
#define I2C_Ack_Enable 0x400
#define I2C_AcknowledgedAddress_7bit 0
#define I2C_CTLR1_PE 1
#define I2C_CTLR1_ENGC 0x40
#define I2C_CTLR1_START 0x100
#define I2C_CTLR1_STOP 0x200
#define I2C_STAR1_SB 1
#define I2C_STAR1_ADDR 2
#define I2C_STAR1_BTF 4
#define I2C_STAR1_STOPF 0x10
#define I2C_STAR1_RXNE 0x40
#define I2C_STAR1_TXE 0x80
#define I2C_STAR1_BERR 0x100
#define I2C_STAR1_ARLO 0x200
#define I2C_STAR1_AF 0x400
#define I2C_STAR1_OVR 0x800
#define I2C_STAR2_BUSY 2
#define I2C_STAR2_TRA 4
#define I2C_STAR2_GENCALL 0x10
struct GPIO_InitTypeDef {
  unsigned GPIO_Pin, GPIO_Mode, GPIO_Speed;
};
struct I2C_InitTypeDef {
  uint32_t I2C_ClockSpeed;
  uint16_t I2C_Mode, I2C_DutyCycle, I2C_OwnAddress1, I2C_Ack,
      I2C_AcknowledgedAddress;
};
void RCC_APB1PeriphClockCmd(unsigned, int);
void RCC_APB2PeriphClockCmd(unsigned, int);
void GPIO_Init(void *, GPIO_InitTypeDef *);
void GPIO_PinRemapConfig(unsigned, int);
void I2C_DeInit(I2C_TypeDef *);
void I2C_Init(I2C_TypeDef *, I2C_InitTypeDef *);
void I2C_Cmd(I2C_TypeDef *, int);
