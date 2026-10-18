#pragma once
#include <stdint.h>

typedef struct { volatile uint16_t CTLR1, CTLR2, OADDR1, OADDR2, DATAR, STAR1, STAR2; } I2C_TypeDef;
typedef struct { volatile uint16_t STATR, DATAR; } USART_TypeDef;
extern I2C_TypeDef fake_i2c;
extern USART_TypeDef fake_usart;
#define I2C1 (&fake_i2c)
#define USART1 (&fake_usart)
#define GPIOC ((void *)1)
#define GPIOD ((void *)2)
#define ENABLE 1
#define DISABLE 0
#define GPIO_Pin_1 2
#define GPIO_Pin_2 4
#define GPIO_Pin_5 32
#define GPIO_Pin_6 64
#define GPIO_Mode_IN_FLOATING 0
#define GPIO_Mode_AF_OD 1
#define GPIO_Mode_AF_PP 2
#define GPIO_Mode_IPU 3
#define GPIO_Speed_30MHz 0
#define GPIO_FullRemap_I2C1 0
#define GPIO_PartialRemap_I2C1 1
#define GPIO_PartialRemap1_USART1 2
#define GPIO_PartialRemap2_USART1 3
#define RCC_APB1Periph_I2C1 1
#define RCC_APB2Periph_GPIOC 2
#define RCC_APB2Periph_GPIOD 4
#define RCC_APB2Periph_AFIO 8
#define RCC_APB2Periph_USART1 16
#define I2C_Mode_I2C 0
#define I2C_DutyCycle_2 0
#define I2C_Ack_Enable 0x400
#define I2C_AcknowledgedAddress_7bit 0
#define USART_WordLength_8b 0
#define USART_StopBits_1 0
#define USART_Parity_No 0
#define USART_HardwareFlowControl_None 0
#define USART_Mode_Tx 8
#define USART_Mode_Rx 4
#define USART_IT_RXNE 0x0525
#define USART1_IRQn 32
#define I2C_CTLR1_PE 1
#define I2C_CTLR1_START 0x100
#define I2C_CTLR1_STOP 0x200
#define I2C_CTLR1_ACK 0x400
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
#define USART_STATR_PE 1
#define USART_STATR_FE 2
#define USART_STATR_NE 4
#define USART_STATR_ORE 8
#define USART_STATR_RXNE 0x20
#define USART_STATR_TXE 0x80

typedef struct { unsigned GPIO_Pin, GPIO_Mode, GPIO_Speed; } GPIO_InitTypeDef;
typedef struct { uint32_t I2C_ClockSpeed; uint16_t I2C_Mode, I2C_DutyCycle,
    I2C_OwnAddress1, I2C_Ack, I2C_AcknowledgedAddress; } I2C_InitTypeDef;
typedef struct { uint32_t USART_BaudRate; uint16_t USART_WordLength,
    USART_StopBits, USART_Parity, USART_HardwareFlowControl, USART_Mode; } USART_InitTypeDef;
void RCC_APB1PeriphClockCmd(unsigned, int);
void RCC_APB2PeriphClockCmd(unsigned, int);
void GPIO_Init(void *, GPIO_InitTypeDef *);
void GPIO_PinRemapConfig(unsigned, int);
void I2C_DeInit(I2C_TypeDef *);
void I2C_Init(I2C_TypeDef *, I2C_InitTypeDef *);
void I2C_Cmd(I2C_TypeDef *, int);
void USART_Init(USART_TypeDef *, USART_InitTypeDef *);
void USART_Cmd(USART_TypeDef *, int);
void USART_ITConfig(USART_TypeDef *, unsigned, int);
void NVIC_EnableIRQ(unsigned);
void __disable_irq(void);
void __enable_irq(void);
typedef struct { volatile uint32_t CTLR, CNT, CMP, SR; } MockSysTick;
extern MockSysTick fake_systick;
#define SysTick (&fake_systick)
#define SysTick_IRQn 12
extern uint32_t SystemCoreClock;
void SystemCoreClockUpdate(void);
