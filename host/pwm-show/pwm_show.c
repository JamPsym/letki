#include "pwm_show.h"
static const uint8_t sine[64]={
    50,55,60,65,69,74,78,82,85,89,92,94,96,98,99,100,
    100,100,99,98,96,94,92,89,85,82,78,74,69,65,60,55,
    50,45,40,35,31,26,22,18,15,11,8,6,4,2,1,0,
    0,0,1,2,4,6,8,11,15,18,22,26,31,35,40,45,
};
static unsigned wave(unsigned phase) { return sine[phase&63U]; }
static unsigned distance(int v) { return (unsigned)(v<0?-v:v); }
static unsigned clamp(int value) { return value<0?0U:value>100?100U:(unsigned)value; }
unsigned pwm_show_scene(uint32_t tick, int choice)
{
    return choice<0?(tick/PWM_SHOW_ACT_STEPS)%PWM_SHOW_SCENES:(unsigned)choice%PWM_SHOW_SCENES;
}
const char *pwm_show_name(unsigned scene)
{
    static const char *const names[]={"Silk ribbon","Ripple garden","Ember trails","Five lanterns","Light ladder","Daisy chain"};
    return names[scene%PWM_SHOW_SCENES];
}
static unsigned pixel(unsigned scene, uint32_t tick, unsigned x, unsigned y, unsigned columns)
{
    unsigned phase=tick&63U;
    if (scene==0) {
        int centre=18+(int)(wave(x*2+phase)*76/100);
        unsigned ribbon=clamp(100-(int)distance((int)y*16-centre)*3);
        unsigned glow=20+wave(x*2-phase*2)*80/100;
        int other=94-(int)(wave(x*2+phase+24)*72/100);
        unsigned thread=clamp(70-(int)distance((int)y*16-other)*4);
        return clamp((int)(ribbon*glow/100+thread*wave(phase+x)/200));
    }
    if (scene==1) {
        unsigned dx=distance((int)x*4-(int)columns),dy=distance((int)y*4-8);
        unsigned radius=dx>dy?dx+dy/2:dy+dx/2;
        unsigned a=wave(radius-phase*2);
        dx=distance((int)x*4-(int)columns*3);dy=distance((int)y*4-20);
        radius=dx>dy?dx+dy/2:dy+dx/2;
        unsigned b=wave(radius-phase*2+16);
        return (a*a/100+b*b/100)/2;
    }
    if (scene==2) {
        unsigned period=columns*4+96, total=0;
        for (unsigned k=0;k<3;++k) {
            int tip=(int)(((tick%period)*3+k*period/3)%period)-48;
            int trail=tip-(int)x*4;
            int centre=12+(int)(wave(phase+k*21)*72/100);
            if (trail>=0 && trail<48) {
                unsigned head=(unsigned)(48-trail);
                unsigned vertical=clamp(100-(int)distance((int)y*16-centre)*4);
                total+=head*head*vertical/(48U*48U);
            }
        }
        return clamp((int)total);
    }
    if (scene==3) {
        unsigned shape=clamp(100-(int)(distance((int)(x%8)*2-7)+distance((int)y*2-7))*7);
        unsigned pulse=wave(phase+(x/8)*11);
        return shape*pulse*pulse/10000;
    }
    if (scene==5) {
        /* A lead pulse hands off tile by tile. Each tile blooms briefly,
           then decays, while the dotted chain carries the same moving phase. */
        unsigned period=columns*4+64;
        int tip=(int)(((tick%period)*2)%period)-32;
        int behind=tip-(int)x*4;
        unsigned chain=behind>=0 && behind<64?(unsigned)(64-behind)*100/64:0;
        unsigned middle=clamp(100-(int)distance((int)y*16-56)*5);
        unsigned node=(x%8==3 || x%8==4)?clamp(100-(int)distance((int)y*16-56)*2):0;
        return (chain*middle+chain*node)/200;
    }
    /* Exact low-end steps remain visible long enough for comparison. A
       moving highlight joins the five tiles without hiding the eight levels. */
    static const uint8_t ladder[8]={0,1,2,5,10,25,50,100};
    unsigned value=ladder[y];
    unsigned sweep=(unsigned)(tick%(columns*2));
    unsigned lead=sweep<columns?sweep:columns*2-1-sweep;
    if (distance((int)x-(int)lead)<2 && y<7) value=(value+100)/2;
    return value;
}
void pwm_show_tile(uint8_t levels[64], uint32_t tick, unsigned tile,
                   unsigned tiles, int choice)
{
    unsigned scene=pwm_show_scene(tick,choice), position=tick%PWM_SHOW_ACT_STEPS;
    unsigned blend=choice<0 && position>=PWM_SHOW_ACT_STEPS-PWM_SHOW_FADE_STEPS?
                   position-(PWM_SHOW_ACT_STEPS-PWM_SHOW_FADE_STEPS)+1:0;
    uint32_t phase=choice<0?position+PWM_SHOW_FADE_STEPS:tick;
    for(unsigned y=0;y<8;++y) for(unsigned x=0;x<8;++x) {
        unsigned a=pixel(scene,phase,tile*8+x,y,tiles*8);
        if(blend) {
            unsigned b=pixel((scene+1)%PWM_SHOW_SCENES,blend-1,tile*8+x,y,tiles*8);
            a=(a*(PWM_SHOW_FADE_STEPS-blend)+b*blend+PWM_SHOW_FADE_STEPS/2)/PWM_SHOW_FADE_STEPS;
        }
        levels[y*8+x]=(uint8_t)a;
    }
}
