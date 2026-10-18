#pragma once
#include <stdbool.h>
#include <stdint.h>
enum bus_mode { BUS_OFF, BUS_CONTROLLER, BUS_TARGET };
/* Reports are foreground-only. success is application CRC confirmation. */
void bus_init(enum bus_mode mode);
bool bus_send(uint16_t counter, uint32_t now);
void bus_poll(uint32_t now, void (*report)(bool success, uint16_t counter, const char *reason));
bool bus_busy(void);
