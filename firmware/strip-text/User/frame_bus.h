#pragma once
#include "frame_packet.h"
void frame_bus_init(bool target);
bool frame_bus_busy(void);
bool frame_bus_send(const struct strip_frame *frame, uint32_t now);
bool frame_bus_send_to(const struct strip_frame *frame, uint32_t now, uint8_t address);
void frame_bus_poll(uint32_t now, void (*report)(bool success, const struct strip_frame *frame));
