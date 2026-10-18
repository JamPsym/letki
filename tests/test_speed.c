#include "speed.h"
#include <assert.h>
#include <stdio.h>

static uint32_t current = 75;
static enum speed_result send(const char *text)
{
    speed_begin();
    enum speed_result result = SPEED_PENDING;
    for (unsigned i = 0; text[i]; ++i) result = speed_feed((uint8_t)text[i], &current);
    return result;
}
int main(void)
{
    assert(send(" 17\n") == SPEED_APPLIED && current == 17);
    assert(send("10\r") == SPEED_APPLIED && current == 10);
    assert(send("500\n") == SPEED_APPLIED && current == 500);
    const char *bad[] = {"9\n", "501\n", "999999999999999999\n", "a\n", "\n", "20 5\n"};
    for (unsigned i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i)
        assert(send(bad[i]) == SPEED_INVALID && current == 500);
    assert(send("22\x1b") == SPEED_CANCELLED && current == 500);
    puts("Speed tests passed: exact intervals, bounds, overflow and cancellation.");
}
