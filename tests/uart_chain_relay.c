/* Host fixture: two independent instances of the real node protocol. */
#include <stdio.h>
#include "chain.h"
int main(void)
{
    struct chain_node nodes[2] = {0};
    int byte;
    while ((byte = getchar()) != EOF) {
        chain_feed(&nodes[0],byte,0);
        if (!nodes[0].pending) continue;
        for (unsigned i = 0; i < CHAIN_WIRE_LENGTH; ++i)
            chain_feed(&nodes[1],(uint8_t)nodes[0].output[i],0);
        nodes[0].pending = false;
        if (nodes[1].pending) {
            fputs(nodes[1].output,stdout); fflush(stdout);
            nodes[1].pending = false;
        }
    }
    return 0;
}
