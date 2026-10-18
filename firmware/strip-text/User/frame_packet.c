#include "frame_packet.h"
#include "protocol.h"
void strip_encode(uint8_t p[STRIP_PACKET_BYTES], const struct strip_frame *f)
{
    p[0]=0xa6; p[1]=(uint8_t)f->sequence; p[2]=(uint8_t)(f->sequence>>8);
    p[3]=f->brightness; p[4]=f->flags;
    for (unsigned i=0;i<8;++i) p[5+i]=f->pixels[i];
    p[13]=packet_crc(p,13);
}
bool strip_decode(const uint8_t *p, unsigned length, struct strip_frame *f)
{
    if (length!=STRIP_PACKET_BYTES || p[0]!=0xa6 || p[3]>100 || (p[4]&~1U) || p[13]!=packet_crc(p,13)) return false;
    f->sequence=(uint16_t)(p[1]|((uint16_t)p[2]<<8)); f->brightness=p[3]; f->flags=p[4];
    for (unsigned i=0;i<8;++i) f->pixels[i]=p[5+i];
    return true;
}
