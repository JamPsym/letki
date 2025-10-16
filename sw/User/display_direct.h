#pragma once

#include <stddef.h>
#include <stdint.h>
#include <wchar.h>

void display_direct_init(void);
void render_loop(const wchar_t *str, size_t str_cap, uint32_t animation_time, uint32_t total_count);
void render_scroll_loop(const wchar_t *str, size_t str_cap, uint32_t animation_time, uint32_t total_count);
