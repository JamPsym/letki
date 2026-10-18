#pragma once
#include <stdbool.h>
#include <stdint.h>
void lg_clock_init(bool head);
uint32_t lg_clock_poll(uint32_t local);
uint16_t lg_clock_age(uint32_t local);
void lg_clock_session(uint16_t session);
