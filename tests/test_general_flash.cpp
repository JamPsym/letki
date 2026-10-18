/* Actual native callbacks against a flash controller/register model. */
#include <cassert>
#include <cstdint>
#include <cstring>
extern "C" {
#include "general.h"
}
enum { FLASH_STATR_BSY=1, FLASH_STATR_WRPRTERR=16, FLASH_STATR_EOP=32,
       FLASH_CTLR_STRT=64, FLASH_CTLR_PAGE_PG=65536,
       FLASH_CTLR_PAGE_ER=131072, FLASH_CTLR_BUF_LOAD=262144,
       FLASH_CTLR_BUF_RST=524288, LOCK=128, FLOCK=32768 };
alignas(64) static uint8_t content[256];
static uint8_t buffer[64];
static uintptr_t word_address;
static uint32_t word_value;
static unsigned starts, stores, blanks, busy_reads;
static bool irq_enabled=true, protected_flash;
struct Status {
  uint32_t value=0;
  operator uint32_t() {
    if (busy_reads) { --busy_reads; return value|FLASH_STATR_BSY; }
    return value;
  }
  Status &operator=(uint32_t clear) { value&=~clear; return *this; }
};
struct Control {
  uint32_t value=LOCK|FLOCK;
  operator uint32_t() { return value; }
  Control &operator=(uint32_t next);
  Control &operator|=(uint32_t mask) { return *this=value|mask; }
  Control &operator&=(uint32_t mask) { return *this=value&mask; }
};
static struct { Status STATR;Control CTLR;uintptr_t ADDR=0; } flash;
Control &Control::operator=(uint32_t next) {
  if ((next&FLASH_CTLR_BUF_RST) && (value&FLASH_CTLR_PAGE_PG)) {
    memset(buffer,255,64);busy_reads=1;
  }
  if (next&FLASH_CTLR_BUF_LOAD) {
    assert(value&FLASH_CTLR_PAGE_PG);
    unsigned at=(word_address-(uintptr_t)content)%64;
    for(unsigned i=0;i<4;++i) buffer[at+i]&=uint8_t(word_value>>(8*i));
    busy_reads=1;
  }
  if (next&FLASH_CTLR_STRT) {
    assert(!(next&(LOCK|FLOCK)));
    assert(flash.ADDR>=(uintptr_t)content && flash.ADDR+64<=(uintptr_t)content+sizeof content);
    assert(!(flash.ADDR%64));++starts;
    if(protected_flash)flash.STATR.value|=FLASH_STATR_WRPRTERR;
    else if(next&FLASH_CTLR_PAGE_ER)memset((void *)flash.ADDR,255,64);
    else {
      assert(next&FLASH_CTLR_PAGE_PG);
      for(unsigned i=0;i<64;++i)((uint8_t *)flash.ADDR)[i]&=buffer[i];
    }
    busy_reads=1;flash.STATR.value|=FLASH_STATR_EOP;
  }
  value=next&~(FLASH_CTLR_BUF_LOAD|FLASH_CTLR_BUF_RST|FLASH_CTLR_STRT);
  return *this;
}
static struct { uint32_t CTLR=7,SR=0,CMP=0,CNT=100; } tick;
static unsigned SystemCoreClock=48000000;
static lg_node node;
#define FLASH (&flash)
#define SysTick (&tick)
#define __content_start content
#define __content_end (content+sizeof content)
#define __disable_irq() (irq_enabled=false)
#define __enable_irq() (irq_enabled=true)
static void display_suspend() { assert(!irq_enabled);++blanks; }
static void FLASH_Unlock_Fast() { flash.CTLR.value&=~(LOCK|FLOCK); }
static void FLASH_Lock_Fast() { flash.CTLR.value|=FLOCK; }
static void FLASH_Lock() { flash.CTLR.value|=LOCK; }
static void word_store(uint8_t *address,uint32_t value) {
  assert(!irq_enabled);assert(flash.CTLR.value&FLASH_CTLR_PAGE_PG);
  assert(!((uintptr_t)address%4));word_address=(uintptr_t)address;word_value=value;++stores;
}
#define LG_FLASH_WORD_STORE(address,value) word_store(address,value)
#include "../firmware/general/User/content_flash.h"
int main() {
  memset(content,255,sizeof content);memset(buffer,0,64);
  uint8_t program[64],manifest[64];
  memset(program,0x53,64);memset(manifest,0x46,64);
  // Each second page must start from a reset program buffer, not data AND old data.
  assert(write_content(64,program));assert(!memcmp(content+64,program,64));
  assert(write_content(0,manifest));assert(!memcmp(content,manifest,64));
  assert(stores==32 && starts==2 && irq_enabled && blanks==2);
  assert((flash.CTLR.value&(LOCK|FLOCK))==(LOCK|FLOCK));
  assert(tick.CTLR==7 && tick.CMP==tick.CNT+SystemCoreClock/2000);
  unsigned old=blanks;
  assert(!write_content(1,program));assert(!write_content(256,program));
  assert(!erase_content(0,0));assert(!erase_content(192,128));assert(blanks==old);
  node.maintenance=true;assert(erase_content(0,128));assert(tick.CTLR==5);
  for(unsigned i=0;i<128;++i)assert(content[i]==255);
  protected_flash=true;assert(!write_content(0,manifest));
  assert(irq_enabled && (flash.CTLR.value&(LOCK|FLOCK))==(LOCK|FLOCK));
  for(unsigned i=0;i<64;++i)assert(content[i]==255);
  return 0;
}
