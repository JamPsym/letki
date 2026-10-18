#include "scene.h"
#include "frame_packet.h"
#include "message.h"
#include "font.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static struct scene s;
static char reply[128];
static const char *send(const char *line)
{
    const char *r=scene_command(&s,line,123,0,0,reply); assert(r); return r;
}
static void unchanged(const char *line)
{
    struct scene before=s;
    assert(!strncmp(send(line),"ERR ",4)); assert(!memcmp(&s,&before,sizeof s));
}
int main(void)
{
    scene_init(&s); assert(s.mode==SCENE_BOUNCE && s.interval==75 && s.brightness==100);
    unsigned end=(unsigned)scene_columns(message_text(),message_length())-16;
    bool reversed=false, came_back=false; unsigned previous=s.offset;
    for (unsigned n=0;n<300;++n) {
        scene_next(&s); assert(s.offset<=end);
        assert(s.offset==previous || s.offset==previous+1 || s.offset+1==previous);
        if (s.reverse) reversed=true;
        if (reversed && !s.offset) came_back=true;
        uint8_t tile[8]; scene_frame(tile,message_text(),message_length(),s.offset,1,false);
        assert(!memcmp(tile,s.pixels+8,8)); previous=s.offset;
    }
    assert(reversed && came_back);
    assert(!strcmp(send("m scroll"),"OK mode updated\r\n"));
    unsigned total=(unsigned)scene_columns(message_text(),message_length());
    for (unsigned n=0;n<total;++n) scene_next(&s);
    assert(s.offset==0);
    send("p"); struct scene held=s; scene_next(&s); assert(!memcmp(&held,&s,sizeof s));
    send("r"); scene_next(&s); assert(s.offset==1);
    unchanged("m wrong"); unchanged("v 9"); unchanged("b 101"); unchanged("ordinary text");
    unchanged("t \xc0\x80"); unchanged("g 00"); unchanged("f123");
    send("v 11"); send("+"); assert(s.interval==10);
    send("v 499"); send("-"); assert(s.interval==500);
    assert(!strcmp(send("t zażółć gęślą jaźń"),"OK text updated\r\n"));
    assert(wcsstr(message_text(),L"ZAŻÓŁĆ GĘŚLĄ JAŹŃ"));
    char long_text[70]; memcpy(long_text,"t ",2); memset(long_text+2,'A',65); long_text[67]=0;
    unchanged(long_text); long_text[66]=0; send(long_text); assert(message_length()==66);
    scene_key(&s,'t'); scene_key(&s,' '); scene_key(&s,'X');
    assert(!strncmp(send("t UART"),"ERR busy",8));
    scene_key(&s,27); send("t "); assert(scene_columns(message_text(),message_length())==4);
    send("m bounce"); for(unsigned n=0;n<50;++n) scene_next(&s); assert(s.offset==0);
    send("g 01020408102040800102040810204080"); assert(s.host_frames);
    uint8_t expected[8]={1,2,4,8,16,32,64,128}; assert(!memcmp(s.pixels,expected,8));
    assert(!memcmp(s.pixels+8,expected,8)); held=s; scene_next(&s); assert(!memcmp(&held,&s,sizeof s));
    send("b 25"); assert(s.brightness==25 && s.host_frames);
    send("0"); assert(!s.host_frames && !s.paused && s.brightness==100 && s.mode==SCENE_BOUNCE);
    send("t A B C D E F G H I J K L"); send("m fall");
    assert(s.mode==SCENE_FALL && s.pulse && s.line==0 && s.offset==0);
    /* At five-board width, A..G fit on the first word-wrapped line.
       Check actual glyph bits enter from the top and shift down, across tiles. */
    uint8_t falling[40], previous_fall[40];
    for (unsigned step=0;step<16;++step) {
        for (unsigned tile=0;tile<5;++tile) scene_tile(falling+8*tile,&s,tile,40);
        if (step==7) {
            /* Seven letters fit: 7*4 + 6*2 - 1 = 39 columns, starting at x=0. */
            assert(falling[0]==font_compact_column(L'A',0));
        }
        if (step>7) for (unsigned x=0;x<40;++x)
            assert(falling[x]==(uint8_t)(previous_fall[x]<<1));
        memcpy(previous_fall,falling,40);
        assert(scene_brightness(&s)<=s.brightness);
        scene_next_width(&s,40);
    }
    assert(s.offset==0 && s.line==1);
    for(unsigned n=0;n<16;++n) scene_next_width(&s,40);
    assert(s.line==0); /* All twelve words appear, then repeat. */
    send("b 25"); unsigned low=100, high=0;
    for(unsigned n=0;n<64;++n) {
        unsigned value=scene_brightness(&s); if(value<low) low=value; if(value>high) high=value;
        scene_next_width(&s,40);
    }
    assert(low<=2 && high==25);
    /* Fully visible lines at phases 7 and 23 must differ substantially. */
    s.pulse_phase=7; unsigned dim_line=scene_brightness(&s);
    s.pulse_phase=23; assert(scene_brightness(&s)>dim_line*2);
    send("p"); held=s; scene_next_width(&s,40); assert(!memcmp(&held,&s,sizeof s));
    send("r"); send("b 0"); assert(scene_brightness(&s)==0);
    send("b 1"); for(unsigned n=0;n<64;++n) {
        assert(scene_brightness(&s)<=1); scene_next_width(&s,40);
    }
    unchanged("e wrong"); send("e off"); assert(scene_brightness(&s)==1);
    send("e pulse"); send("g 01020408102040800102040810204080");
    assert(scene_brightness(&s)==1); /* Manual frames retain requested brightness. */
    send("t ABCDEFGHIJKLMNOP"); send("m fall");
    for(unsigned n=0;n<16;++n) scene_next(&s);
    assert(s.line==1); /* Long words split rather than disappear. */
    send("t "); send("m fall");
    for(unsigned n=0;n<100;++n) {
        scene_next(&s); for(unsigned x=0;x<16;++x) assert(!s.pixels[x]);
    }
    send("0"); assert(!s.pulse);
    send("ping hello"); assert(!strcmp(reply,"PONG hello\r\n"));
    scene_status(&s,UINT32_MAX,UINT32_MAX,UINT32_MAX,reply); assert(strlen(reply)<127);
    assert(strstr(reply,"4294967295"));
    struct strip_frame a={.sequence=65535,.brightness=100,.flags=1,.pixels={1,2,3,4,5,6,7,8}}, b={0};
    uint8_t packet[STRIP_PACKET_BYTES]; strip_encode(packet,&a);
    assert(strip_decode(packet,sizeof packet,&b)); assert(!memcmp(&a,&b,sizeof a));
    for(unsigned byte=0;byte<STRIP_PACKET_BYTES;++byte) for(unsigned bit=0;bit<8;++bit) {
        struct strip_frame before=b; packet[byte]^=(uint8_t)(1U<<bit);
        assert(!strip_decode(packet,sizeof packet,&b)); assert(!memcmp(&before,&b,sizeof b));
        packet[byte]^=(uint8_t)(1U<<bit);
    }
    assert(!strip_decode(packet,sizeof packet-1,&b));
    puts("Strip scene: modes/bounds/pause/UTF-8/64-char rejection/SWIO isolation/brightness/frames and packet corruption passed");
}
