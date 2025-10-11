#pragma once

#include <stdint.h>

#define GAMMA_TABLE_SIZE 256U

extern const uint8_t gamma_table[GAMMA_TABLE_SIZE];

static inline uint8_t gamma_correct(uint8_t level)
{
    return gamma_table[level];
}
