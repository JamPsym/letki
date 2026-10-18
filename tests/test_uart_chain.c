#include <assert.h>
#include <string.h>
#include "chain.h"

static void feed(struct chain_node *n, const char *s, uint32_t errors)
{
    while (*s) chain_feed(n,(uint8_t)*s++,errors);
}
static void deliver(struct chain_node *from, struct chain_node *to, uint32_t errors)
{
    assert(from->pending); feed(to,from->output,errors); from->pending = false;
}
int main(void)
{
    assert(chain_crc((const uint8_t *)"123456789",9)==0x29b1);
    struct chain_packet p = {.token=0x1234abcd,.counter=0xa55a};
    char wire[CHAIN_WIRE_LENGTH+1]; chain_encode(wire,&p);
    assert(strlen(wire)==CHAIN_WIRE_LENGTH);
    struct chain_node a={0},b={0},c={0};
    feed(&a,wire,0); deliver(&a,&b,0); deliver(&b,&c,0);
    assert(a.last.hops==1 && b.last.hops==2 && c.last.hops==3);
    assert(c.last.counter==p.counter && c.last.token==p.token && !c.last.errors);
    /* A pending reply is preserved; an overflowing second packet cannot change LEDs. */
    char saved[CHAIN_WIRE_LENGTH+1]; memcpy(saved,c.output,sizeof(saved));
    p.counter=42; chain_encode(wire,&p); feed(&c,wire,0);
    assert(c.dropped==1 && c.last.counter==0xa55a && !memcmp(saved,c.output,sizeof(saved)));
    c.pending=false; feed(&c,wire,0); assert(c.last.errors==1 && c.last.counter==42);
    /* Every payload bit corruption must fail validation and preserve display state. */
    for (unsigned byte=0;byte<14;++byte) for (unsigned bit=0;bit<8;++bit) {
        struct chain_node n={0}; feed(&n,wire,0); n.pending=false;
        n.input[byte]^=1U<<bit;
        struct chain_packet bad;
        assert(!chain_decode(n.input,&bad));
    }
    const char *invalid[]={"@123\n","@GGGG\n","@\r\n"};
    for (unsigned i=0;i<3;++i) {
        struct chain_node n={0}; feed(&n,invalid[i],0);
        assert(!n.pending && !n.accepted && n.rejected==1);
        feed(&n,wire,0); assert(n.pending && n.last.errors==1);
    }
    struct chain_node n={0};
    feed(&n,"@01",0); chain_feed(&n,'0'|CHAIN_RX_INVALID,1);
    feed(&n,wire+3,1); assert(!n.pending && n.rejected==1);
    feed(&n,wire,1); assert(n.pending && n.last.errors==2);
    n.pending=false;
    feed(&n,"@01",0); chain_feed(&n,'0'|CHAIN_RX_GAP,1);
    feed(&n,wire+3,1); assert(n.rejected==2 && n.accepted==1);
    /* Aborted frames resynchronize only at a new marker, even without a newline. */
    feed(&n,"@0000",0); feed(&n,wire,0); assert(n.pending && n.rejected==3);
    struct chain_node many={0}; p.hops=255; chain_encode(wire,&p); feed(&many,wire,0);
    assert(!many.pending && many.rejected==1);
    p.hops=254; p.errors=UINT32_MAX-1U; chain_encode(wire,&p); feed(&many,wire,10);
    assert(many.pending && many.last.hops==255 && many.last.errors==UINT32_MAX);
    /* Healthy frames already queued ahead of an overflow marker stay valid. */
    struct chain_node ordered={0}; p.hops=0; p.errors=0; chain_encode(wire,&p);
    feed(&ordered,wire,0); assert(ordered.accepted==1 && !ordered.last.errors);
    ordered.pending=false; feed(&ordered,"@01",0);
    chain_feed(&ordered,'0'|CHAIN_RX_GAP,1); feed(&ordered,wire+3,1);
    assert(ordered.accepted==1 && ordered.rejected==1);
    /* LF and CRLF accepted, extra digits/data after CR rejected. */
    struct chain_node endings={0}; wire[29]='\n'; wire[30]=0; feed(&endings,wire,0);
    assert(endings.pending); endings.pending=false;
    chain_encode(wire,&p); wire[29]='0'; feed(&endings,wire,0);
    assert(!endings.pending && endings.rejected==1);
    return 0;
}
