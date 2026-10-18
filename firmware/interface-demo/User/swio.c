#include "swio.h"
#include <stddef.h>
#include <stdint.h>

/* CH32V003 CPU aliases for debug DATA0/1, also used by WCH's debug.c.
 * Packet format compatible with cnlohr/ch32fun's minichlink terminal:
 * DATA0 low byte = 0x80 | (length + 4); first 3 bytes in bits 8..31.
 * DATA1 carries the last 4 bytes. Host acknowledges by clearing bit 7
 * and may supply up to 3 input bytes with the same length+4 encoding.
 * This implements the protocol without importing the ch32fun SDK.
 */
#ifndef SWIO_DATA0
#define SWIO_DATA0 (*(volatile uint32_t *)0xE00000F4U)
#define SWIO_DATA1 (*(volatile uint32_t *)0xE00000F8U)
#endif

#define TX_SIZE 128U
static uint8_t tx[TX_SIZE];
static uint8_t head, tail;

void swio_init(void)
{
    head = tail = 0;
    SWIO_DATA1 = 0;
    SWIO_DATA0 = 0x80U;
}

bool swio_write(const char *message)
{
    size_t length = 0;
    while (message[length] != '\0')
    {
        if (++length >= TX_SIZE)
            return false;
    }
    const unsigned used = (head - tail) & (TX_SIZE - 1U);
    if (length > TX_SIZE - 1U - used)
        return false;
    for (size_t i = 0; i < length; ++i)
    {
        tx[head] = (uint8_t)message[i];
        head = (head + 1U) & (TX_SIZE - 1U);
    }
    return true;
}

void swio_poll(void (*receive)(char))
{
    const uint32_t input = SWIO_DATA0;
    if (input & 0x80U)
        return;

    const unsigned count = input & 0x3FU;
    if (receive && count >= 5U && count <= 7U)
        for (unsigned i = 0; i < count - 4U; ++i)
            receive((char)(input >> (8U * (i + 1U))));

    uint32_t first = 0, last = 0;
    unsigned length = 0;
    while (tail != head && length < 7U)
    {
        const uint32_t byte = tx[tail];
        tail = (tail + 1U) & (TX_SIZE - 1U);
        if (length < 3U) first |= byte << (8U * (length + 1U));
        else last |= byte << (8U * (length - 3U));
        ++length;
    }
    SWIO_DATA1 = last;
    __asm__ volatile ("" ::: "memory");
    /* A zero-length packet also allows host input while the logs are idle. */
    SWIO_DATA0 = first | 0x80U | (length + 4U);
}
