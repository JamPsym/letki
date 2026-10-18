#include <assert.h>
#include <string.h>
#include "protocol.h"

int main(void)
{
    struct line_input input = {0};
    for (const char *s = "ping test\r"; *s; ++s) assert(line_feed(&input, *s) == LINE_WAIT);
    assert(line_feed(&input, '\n') == LINE_READY);
    assert(!strcmp(input.text, "ping test"));
    for (unsigned i = 0; i < LINE_CAPACITY; ++i) line_feed(&input, 'x');
    assert(line_feed(&input, '\n') == LINE_INVALID);
    line_feed(&input, 's'); line_feed(&input, 0); line_feed(&input, 's');
    assert(line_feed(&input, '\n') == LINE_INVALID);
    assert(line_feed(&input, '\n') == LINE_READY);
    assert(!*input.text);
    uint16_t value = 123;
    assert(parse_counter("65535", &value) && value == 65535);
    assert(parse_counter("0", &value) && value == 0);
    assert(!parse_counter("65536", &value) && value == 0);
    assert(!parse_counter("999999999999999999999999999999", &value));
    assert(!parse_counter("-1", &value)); assert(!parse_counter("", &value));
    assert(!parse_counter("1x", &value));
    assert(packet_crc((const uint8_t *)"123456789", 9) == 0xF4);
    for (unsigned n = 0; n <= 65535; ++n) {
        uint8_t packet[4]; packet_encode(packet, (uint16_t)n);
        assert(packet_decode(packet, 4, &value) && value == n);
        for (unsigned bit = 0; bit < 32; ++bit) {
            packet[bit / 8] ^= 1U << (bit % 8);
            assert(!packet_decode(packet, 4, &value));
            packet[bit / 8] ^= 1U << (bit % 8);
        }
        assert(!packet_decode(packet, 3, &value));
        assert(!packet_decode(packet, 5, &value));
    }
    return 0;
}
