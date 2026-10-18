#include "ch32v00x.h"
#include <cassert>
#include <cstring>
extern "C" {
#include "general.h"
}
#include "../firmware/general/User/clock.c"
I2C_TypeDef fake_i2c;
static unsigned resets;
void RCC_APB1PeriphClockCmd(unsigned, int) {}
void RCC_APB2PeriphClockCmd(unsigned, int) {}
void GPIO_Init(void *, GPIO_InitTypeDef *p) { assert(p->GPIO_Pin == 6); }
void GPIO_PinRemapConfig(unsigned, int) {}
void I2C_DeInit(I2C_TypeDef *) {
  fake_i2c = I2C_TypeDef();
  ++resets;
}
void I2C_Init(I2C_TypeDef *, I2C_InitTypeDef *p) {
  assert(p->I2C_ClockSpeed == 100000);
  assert(p->I2C_Ack == I2C_Ack_Enable);
}
void I2C_Cmd(I2C_TypeDef *, int) {}
static uint32_t receive(uint32_t remote, uint32_t local, bool corrupt = false,
                        bool last_with_stop = false, unsigned count = 7,
                        uint32_t delayed_end = 0) {
  uint8_t packet[8] = {0xc1};
  lg_put32(packet + 1, remote);
  lg_put16(packet + 5, lg_crc(packet, 5));
  if (corrupt)
    packet[5] ^= 1;
  fake_i2c.STAR1 = I2C_STAR1_ADDR;
  fake_i2c.STAR2 = I2C_STAR2_GENCALL;
  lg_clock_poll(local);
  for (unsigned i = 0; i < count; ++i) {
    fake_i2c.DATAR = packet[i];
    fake_i2c.STAR1 = I2C_STAR1_RXNE |
                     ((last_with_stop && i + 1 == count) ? I2C_STAR1_STOPF : 0);
    lg_clock_poll(delayed_end && i + 1 == count ? delayed_end : local);
  }
  fake_i2c.STAR1 = I2C_STAR1_STOPF;
  return lg_clock_poll(delayed_end ? delayed_end : local);
}
int main() {
  lg_clock_init(true);
  assert(!(fake_i2c.CTLR1 & I2C_CTLR1_ENGC));
  lg_clock_poll(99);
  assert(clock_state.phase == 0);
  lg_clock_poll(100);
  assert(clock_state.phase == 1);
  fake_i2c.STAR1 = I2C_STAR1_SB;
  lg_clock_poll(101);
  assert(fake_i2c.DATAR.value == 0);
  fake_i2c.STAR1 = I2C_STAR1_ADDR;
  fake_i2c.STAR2 = 0;
  lg_clock_poll(102);
  uint8_t packet[7];
  for (unsigned i = 0; i < 7; ++i) {
    fake_i2c.STAR1 = I2C_STAR1_TXE;
    lg_clock_poll(103);
    packet[i] = (uint8_t)fake_i2c.DATAR.value;
  }
  assert(packet[0] == 0xc1 && lg_u32(packet + 1) == 100 &&
         lg_u16(packet + 5) == lg_crc(packet, 5));
  fake_i2c.STAR1 = I2C_STAR1_BTF;
  lg_clock_poll(104);
  assert(fake_i2c.CTLR1 & I2C_CTLR1_STOP);
  // Idle BUSY must neither stall forever nor reset on every foreground poll.
  fake_i2c.STAR1=0;fake_i2c.STAR2=I2C_STAR2_BUSY;
  unsigned idle_resets=resets;
  lg_clock_poll(200);assert(clock_state.phase==5);
  lg_clock_poll(210);assert(resets==idle_resets);
  lg_clock_poll(221);assert(resets==idle_resets+1 && clock_state.phase==0);
  lg_clock_poll(222);assert(clock_state.phase==1);
  clock_state={};lg_clock_init(true);
  fake_i2c.STAR2=I2C_STAR2_BUSY;lg_clock_poll(100);
  fake_i2c.STAR2=0;idle_resets=resets;
  lg_clock_poll(110);assert(clock_state.phase==0 && resets==idle_resets);
  lg_clock_poll(111);assert(clock_state.phase==1);
  clock_state={};lg_clock_init(true);
  fake_i2c.STAR2=I2C_STAR2_BUSY;lg_clock_poll(0xfffffff0U);
  idle_resets=resets;lg_clock_poll(5);
  assert(resets==idle_resets+1 && clock_state.phase==0);
  fake_i2c.STAR2=I2C_STAR2_BUSY;lg_clock_poll(6);
  lg_clock_poll(10);assert(resets==idle_resets+1);
  clock_state = {};
  lg_clock_init(false);
  assert(fake_i2c.CTLR1 & I2C_CTLR1_ENGC);
  assert(lg_clock_age(900) == 65535);
  assert(receive(1000, 900) == 1001);
  assert(lg_clock_age(900) == 0);
  assert(lg_clock_age(1500) == 600);
  assert(receive(1200, 1000, true) == 1101);
  assert(lg_clock_age(1000) == 100);
  assert(receive(1200, 1000, false, true) == 1201);
  assert(receive(1300, 1100, false, false, 6) == 1301);
  assert(lg_clock_age(1100) == 100);
  receive(1300, 1100, false, false, 8);
  assert(lg_clock_age(1100) == 100);
  receive(10, 1200);
  assert(lg_clock_age(1200) == 65535);
  lg_clock_session(123);
  assert(receive(20, 1300) == 21);
  assert(lg_clock_age(1300) == 0);
  // Last RXNE+STOP delayed by capacity-flash maintenance must be rejected,
  // without offset changes or falsely latching a head-clock regression.
  unsigned before = resets;
  assert(receive(120, 1400, false, true, 7, 1550) == 271);
  assert(resets == before + 1);
  assert(lg_clock_age(1550) == 250);
  assert(!clock_state.regressed);
  assert(receive(320, 1600) == 321);
  assert(lg_clock_age(1600) == 0);
  // An independently restarted receiver acquires an old head epoch directly.
  clock_state={};lg_clock_init(false);
  assert(receive(1234567,50)==1234568);
  assert(lg_clock_age(50)==0);
  fake_i2c.STAR1 = I2C_STAR1_BERR;
  unsigned old = resets;
  lg_clock_poll(1400);
  assert(resets == old + 1);
  // Counter time continues during a simulated 300 ms flash pause and wrap.
  lg_counter counter = {0, 0, 0};
  assert(lg_counter_update(&counter, 48000, 48000) == 1);
  assert(lg_counter_update(&counter, 48000 + 300 * 48000, 48000) == 301);
  counter.last = 0xfffffff0U;
  counter.millis = 500;
  counter.fraction = 0;
  assert(lg_counter_update(&counter, 48000 - 16, 48000) == 501);
  return 0;
}
