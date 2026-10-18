#include "swio.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

volatile uint32_t mock_data0, mock_data1;
static char received[4];
static unsigned received_count;
static void receive(char key) { received[received_count++] = key; }

int main(void)
{
    swio_init();
    assert(mock_data0 == 0x80 && mock_data1 == 0);
    assert(swio_write("abcdefghij"));
    swio_poll(receive);
    assert(mock_data0 == 0x80); /* Unattached host never blocks or consumes TX. */
    mock_data0 = 0;
    swio_poll(receive);
    assert(mock_data0 == 0x6362618bU && mock_data1 == 0x67666564U);
    mock_data0 = 0;
    swio_poll(receive);
    assert(mock_data0 == 0x6a696887U && mock_data1 == 0);
    mock_data0 = 0;
    swio_poll(receive);
    assert(mock_data0 == 0x84); /* Request input without requiring a log. */
    mock_data0 = 7U | ('s' << 8) | ('+' << 16) | ('p' << 24);
    swio_poll(receive);
    assert(received_count == 3 && memcmp(received, "s+p", 3) == 0);
    assert(mock_data0 == 0x84);
    char full[128];
    memset(full, 'x', 127); full[127] = 0;
    assert(swio_write(full));
    assert(!swio_write("overflow")); /* Whole messages are dropped, not truncated. */
    mock_data0 = 0;
    swio_poll(receive);
    assert(swio_write("1234567")); /* Ring storage becomes reusable after a packet. */
    puts("SWIO tests passed: packets, idle input, backpressure and ring wrap.");
}
