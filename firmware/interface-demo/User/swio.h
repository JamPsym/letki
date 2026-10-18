#pragma once

#include <stdbool.h>

void swio_init(void);
/* Foreground only. Polls never wait for a connected probe. */
void swio_poll(void (*receive)(char));
/* Queue a complete ASCII message; false means it did not fit. */
bool swio_write(const char *message);
