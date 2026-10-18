#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <wchar.h>

#define SCENE_DEFAULT_TEXT L" LETKI DZIAŁA "
#define SCENE_DEFAULT_MS 75U
#ifndef SCENE_COLUMNS
#define SCENE_COLUMNS 16U
#endif
enum scene_mode { SCENE_SCROLL, SCENE_BOUNCE, SCENE_FALL };
struct scene {
    uint32_t revision, interval;
    unsigned offset, dwell;
    uint8_t brightness, pulse_phase;
    unsigned line;
    bool reverse, paused, host_frames, pulse;
    enum scene_mode mode;
    uint8_t pixels[16];
};
void scene_init(struct scene *s);
void scene_render(struct scene *s);
void scene_tile(uint8_t frame[8], const struct scene *s, unsigned tile, unsigned columns);
uint8_t scene_brightness(const struct scene *s);
const char *scene_mode_name(const struct scene *s);
void scene_next(struct scene *s);
void scene_next_width(struct scene *s, unsigned display_columns);
bool scene_editing(void);
/* Renderer and five-tile firmware reuse the geometry at their strip width. */
size_t scene_columns(const wchar_t *text, size_t length);
void scene_frame(uint8_t frame[8], const wchar_t *text, size_t length,
                 unsigned offset, unsigned tile, bool repeat);
const char *scene_key(struct scene *s, uint8_t key);
const char *scene_command(struct scene *s, const char *line, uint32_t now,
                          uint32_t errors, uint32_t drops, char reply[128]);
void scene_status(const struct scene *s, uint32_t now, uint32_t errors,
                  uint32_t drops, char reply[128]);
