#include "brightness.h"
#include <assert.h>
#include <stdio.h>
static enum brightness_result send(const char *s, uint8_t *value)
{
    enum brightness_result result = BRIGHTNESS_PENDING;
    brightness_begin();
    while (*s) result = brightness_feed((uint8_t)*s++, value);
    return result;
}
int main(void)
{
    uint8_t value = 75;
    assert(send(" 0\n", &value) == BRIGHTNESS_APPLIED && value == 0);
    assert(send("100\r", &value) == BRIGHTNESS_APPLIED && value == 100);
    assert(send("25", &value) == BRIGHTNESS_PENDING && value == 100);
    assert(brightness_feed(27, &value) == BRIGHTNESS_CANCELLED && value == 100);
    const char *bad[] = {"\n", "-1\n", "101\n", "999999999999999\n", "5 0\n", "50x\n"};
    for (unsigned i = 0; i < sizeof(bad)/sizeof(bad[0]); ++i)
        assert(send(bad[i], &value) == BRIGHTNESS_INVALID && value == 100);
    assert(send("50\n", &value) == BRIGHTNESS_APPLIED && value == 50);
    puts("Brightness tests passed: bounds, staged/cancelled drafts and invalid-input preservation.");
}
