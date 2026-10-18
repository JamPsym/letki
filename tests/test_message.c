#include "message.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

static enum message_result send(const char *input)
{
    message_begin();
    enum message_result result = MESSAGE_PENDING;
    for (size_t i = 0; input[i]; ++i)
        result = message_feed((uint8_t)input[i]);
    return result;
}

int main(void)
{
    message_init(L" DEFAULT ");
    assert(send(" zobacz adaś działa\n") == MESSAGE_APPLIED);
    assert(wcscmp(message_text(), L" ZOBACZ ADAŚ DZIAŁA ") == 0);
    assert(message_length() == wcslen(message_text()));
    assert(send("ąćęłńóśźż\r") == MESSAGE_APPLIED);
    assert(wcscmp(message_text(), L" ĄĆĘŁŃÓŚŹŻ ") == 0);
    assert(send("OLD\n") == MESSAGE_APPLIED);
    assert(send("NEW\x1b") == MESSAGE_CANCELLED);
    assert(wcscmp(message_text(), L" OLD ") == 0);
    const char *invalid[] = {"\xc0\xaf\n", "\xed\xa0\x80\n",
                            "\xf4\x90\x80\x80\n", "\xe2\n", "\x80\n"};
    for (size_t i = 0; i < sizeof(invalid) / sizeof(invalid[0]); ++i)
    {
        assert(send(invalid[i]) == MESSAGE_INVALID);
        assert(wcscmp(message_text(), L" OLD ") == 0);
    }
    char boundary[67];
    memset(boundary, 'a', 64); boundary[64] = '\n'; boundary[65] = 0;
    assert(send(boundary) == MESSAGE_APPLIED);
    assert(message_length() == 66);
    boundary[64] = 'a'; boundary[65] = '\n'; boundary[66] = 0;
    assert(send(boundary) == MESSAGE_TOO_LONG);
    assert(message_length() == 66); /* Keep the previous complete message. */
    assert(send("Aś\177B\n") == MESSAGE_APPLIED);
    assert(wcscmp(message_text(), L" AB ") == 0);
    assert(send("\n") == MESSAGE_APPLIED);
    assert(wcscmp(message_text(), L"  ") == 0); /* Empty input clears the display. */
    assert(!message_editing());
    puts("Message tests passed: UTF-8, Polish case, limits, cancellation and editing.");
}
