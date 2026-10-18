#include "pwm_show.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    uint8_t a[64],b[64];
    for(unsigned scene=0;scene<PWM_SHOW_SCENES;++scene) {
        unsigned seen[101]={0},changed=0;
        pwm_show_tile(a,0,0,5,(int)scene);
        for(unsigned tick=0;tick<256;++tick) for(unsigned tile=0;tile<5;++tile) {
            pwm_show_tile(b,tick,tile,5,(int)scene);
            for(unsigned p=0;p<64;++p) { assert(b[p]<=100);seen[b[p]]=1; }
            if(memcmp(a,b,64)) ++changed;
        }
        unsigned distinct=0;for(unsigned n=0;n<=100;++n) distinct+=seen[n];
        assert(distinct>=8 && changed>100);
    }
    /* Same global ribbon/lantern coordinates do not change with host tiling. */
    for(unsigned tile=0;tile<5;++tile) for(unsigned tick=0;tick<64;++tick) {
        pwm_show_tile(a,tick,tile,5,0);pwm_show_tile(b,tick,tile,6,0);assert(!memcmp(a,b,64));
    }
    /* Exact low-end ladder values are retained away from the moving highlight. */
    pwm_show_tile(a,0,4,5,4);
    const uint8_t levels[8]={0,1,2,5,10,25,50,100};
    for(unsigned y=0;y<8;++y) assert(a[y*8+4]==levels[y]);
    for(unsigned act=0;act<PWM_SHOW_SCENES;++act) {
        pwm_show_tile(a,(act+1)*PWM_SHOW_ACT_STEPS-1,2,5,-1);
        pwm_show_tile(b,(act+1)*PWM_SHOW_ACT_STEPS,2,5,-1);
        unsigned difference=0;for(unsigned p=0;p<64;++p) difference+=(unsigned)(a[p]>b[p]?a[p]-b[p]:b[p]-a[p]);
        assert(difference<64*20); /* No hard scene cut. */
    }
    for(unsigned tick=0;tick<PWM_SHOW_SCENES*PWM_SHOW_ACT_STEPS;tick+=37) {
        pwm_show_tile(a,tick,3,5,-1);pwm_show_tile(b,tick+PWM_SHOW_SCENES*PWM_SHOW_ACT_STEPS,3,5,-1);
        assert(!memcmp(a,b,64)); /* Recorded show really loops. */
    }
    pwm_show_tile(a,UINT32_MAX,255,256,-1);
    for(unsigned p=0;p<64;++p) assert(a[p]<=100);
    puts("PWM show: six moving multilevel scenes, tiling, low-end ladder, crossfades and tick bounds passed");
}
