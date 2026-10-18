#pragma once
#include "pong.h"
#include "scene.h"
#include "pwm_show.h"
#include <stdio.h>

struct tile {
    struct pong_state pong;
    bool link, corrupt, raw;
    uint8_t columns[8];
    uint8_t levels[64];
};
struct renderer_model {
    struct tile *tiles;
    unsigned count, interval, next_phase;
    uint32_t now, elapsed;
    bool running, paused, external;
    bool text_demo, text_started;
    bool pwm_demo, pwm_started, pwm_audio;
    int pwm_choice;
    uint8_t pwm_brightness;
    uint32_t pwm_tick;
    uint32_t text_revision;
    struct scene text_scene;
    char uart_reply[128];
};
bool model_init(struct renderer_model *m, unsigned count);
void model_free(struct renderer_model *m);
void model_reset(struct renderer_model *m);
void model_exchange(struct renderer_model *m);
void model_advance(struct renderer_model *m, unsigned ms);
void model_columns(const struct renderer_model *m, unsigned tile, uint8_t columns[8]);
void model_status(const struct renderer_model *m, FILE *out);
/* Returns false on malformed commands; invalid commands preserve state. */
bool model_command(struct renderer_model *m, const char *command);
