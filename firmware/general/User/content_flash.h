#pragma once
/* Included by main.c and the register-level test; callbacks share its node,
 * linker bounds and timebase. The test overrides only the physical word store. */
#ifndef LG_FLASH_WORD_STORE
#define LG_FLASH_WORD_STORE(address, value) (*(volatile uint32_t *)(address) = (value))
#endif
/* Fast-page register sequence follows WCH's ch32v00x_flash.c V1.0.0.
 * Copyright (c) 2021 Nanjing Qinheng Microelectronics Co., Ltd.
 * This software and binaries are for microcontrollers manufactured by WCH.
 * Only the linker-reserved content partition is addressable here. No option
 * bytes, mass erase, programmer power or executable pages are exposed. */
static bool wait_flash(void) {
  uint32_t timeout = 1000000;
  while ((FLASH->STATR & FLASH_STATR_BSY) && --timeout) {
  }
  return timeout && !(FLASH->STATR & FLASH_STATR_WRPRTERR);
}
static bool content_bounds(unsigned offset, unsigned count) {
  unsigned size = (unsigned)(__content_end - __content_start);
  return !(offset % 64) && count && !(count % 64) && offset <= size &&
         count <= size - offset;
}
static void flash_enter(void) {
  __disable_irq();
  SysTick->CTLR = 5;
  display_suspend();
  FLASH_Unlock_Fast();
  FLASH->STATR = FLASH_STATR_EOP | FLASH_STATR_WRPRTERR;
}
static void flash_leave(void) {
  FLASH->CTLR &= ~(FLASH_CTLR_PAGE_PG | FLASH_CTLR_PAGE_ER);
  FLASH_Lock_Fast();
  FLASH_Lock();
  SysTick->SR = 0;
  SysTick->CMP = SysTick->CNT + SystemCoreClock / 2000U;
  SysTick->CTLR = node.maintenance ? 5 : 7;
  __enable_irq();
}
static bool erase_content(uint16_t offset, uint16_t length) {
  if (!content_bounds(offset, length))
    return false;
  flash_enter();
  bool ok = true;
  for (unsigned i = offset; i < (unsigned)offset + length && ok; i += 64) {
    FLASH->CTLR |= FLASH_CTLR_PAGE_ER;
    FLASH->ADDR = (uintptr_t)(__content_start + i);
    FLASH->CTLR |= FLASH_CTLR_STRT;
    ok = wait_flash();
    FLASH->CTLR &= ~FLASH_CTLR_PAGE_ER;
    if (ok)
      for (unsigned j = 0; j < 64; ++j)
        if (__content_start[i + j] != 255) {
          ok = false;
          break;
        }
  }
  flash_leave();
  return ok;
}
static bool write_content(uint16_t offset, const uint8_t *data) {
  if (!content_bounds(offset, 64))
    return false;
  flash_enter();
  /* FTPG must already be enabled when the BUFRST trigger is written. */
  FLASH->CTLR |= FLASH_CTLR_PAGE_PG;
  FLASH->CTLR |= FLASH_CTLR_BUF_RST;
  bool ok = wait_flash();
  for (unsigned i = 0; i < 64 && ok; i += 4) {
    LG_FLASH_WORD_STORE(__content_start + offset + i, lg_u32(data + i));
    FLASH->CTLR |= FLASH_CTLR_BUF_LOAD;
    ok = wait_flash();
  }
  if (ok) {
    FLASH->ADDR = (uintptr_t)(__content_start + offset);
    FLASH->CTLR |= FLASH_CTLR_STRT;
    ok = wait_flash();
  }
  flash_leave();
  return ok && !memcmp(__content_start + offset, data, 64);
}
