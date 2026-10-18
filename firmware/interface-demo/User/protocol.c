#include "protocol.h"

enum line_result line_feed(struct line_input *input, unsigned char byte)
{
    if (byte == '\r') return LINE_WAIT;
    if (byte == '\n') {
        input->text[input->used] = 0;
        const bool invalid = input->invalid;
        input->used = 0;
        input->invalid = false;
        return invalid ? LINE_INVALID : LINE_READY;
    }
    if (byte < 32 || byte > 126 || input->used == LINE_CAPACITY - 1) {
        input->invalid = true;
        return LINE_WAIT;
    }
    if (!input->invalid) input->text[input->used++] = (char)byte;
    return LINE_WAIT;
}

bool parse_counter(const char *text, uint16_t *value)
{
    uint32_t result = 0;
    if (!*text) return false;
    while (*text) {
        if (*text < '0' || *text > '9') return false;
        result = result * 10U + (unsigned)(*text++ - '0');
        if (result > 65535U) return false;
    }
    *value = (uint16_t)result;
    return true;
}

uint8_t packet_crc(const uint8_t *bytes, unsigned length)
{
    uint8_t crc = 0;
    while (length--) {
        crc ^= *bytes++;
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (uint8_t)((crc << 1) ^ ((crc & 0x80U) ? 0x07U : 0));
    }
    return crc;
}

void packet_encode(uint8_t packet[4], uint16_t value)
{
    packet[0] = 0xA5;
    packet[1] = (uint8_t)value;
    packet[2] = (uint8_t)(value >> 8);
    packet[3] = packet_crc(packet, 3);
}

bool packet_decode(const uint8_t *packet, unsigned length, uint16_t *value)
{
    if (length != 4 || packet[0] != 0xA5 || packet[3] != packet_crc(packet, 3))
        return false;
    *value = (uint16_t)(packet[1] | ((uint16_t)packet[2] << 8));
    return true;
}
