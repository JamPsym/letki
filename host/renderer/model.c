#include "model.h"
#include "protocol.h"
#include "frame_packet.h"
#include "message.h"
#include <stdlib.h>
#include <string.h>

bool model_init(struct renderer_model *m, unsigned count)
{
    if (!pong_phase_count(count)) return false;
    struct tile *tiles = calloc(count, sizeof *tiles);
    if (!tiles) return false;
    free(m->tiles);
    *m = (struct renderer_model){.tiles=tiles, .count=count, .interval=100, .running=true,
                                .pwm_choice=-1,.pwm_brightness=100};
    scene_init(&m->text_scene);
    for (unsigned i=0; i<count; ++i) tiles[i].link=true;
    return true;
}

void model_free(struct renderer_model *m) { free(m->tiles); m->tiles=NULL; }

void model_reset(struct renderer_model *m)
{
    for (unsigned i=0; i<m->count; ++i) m->tiles[i]=(struct tile){.link=true};
    m->next_phase=0; m->now=0; m->elapsed=0; m->paused=false;
    m->pwm_tick=0;
    m->pwm_started=false;
    scene_init(&m->text_scene); m->text_started=false;
    if (m->text_demo) m->interval=m->text_scene.interval;
    m->uart_reply[0]=0;
}

static void text_exchange(struct renderer_model *m)
{
    struct scene pending=m->text_scene;
    if (m->text_started && m->text_revision==pending.revision) scene_next_width(&pending,m->count*8);
    bool success=true;
    for (unsigned i=0;i<m->count;++i) {
        struct tile *t=&m->tiles[i];
        if (!t->link) { success=false; break; }
        struct strip_frame f={.sequence=(uint16_t)m->next_phase,.brightness=scene_brightness(&pending),.flags=pending.paused};
        if (pending.host_frames) {
            if (i<2) memcpy(f.pixels,pending.pixels+i*8,8);
        } else scene_tile(f.pixels,&pending,i,m->count*8);
        uint8_t packet[STRIP_PACKET_BYTES]; strip_encode(packet,&f);
        if (t->corrupt) { packet[13]^=1; t->corrupt=false; }
        if (!strip_decode(packet,sizeof packet,&f)) {
            if (i) pong_failed(&t->pong);
            success=false; break;
        }
        if (i) {
            memcpy(t->columns,f.pixels,8); t->raw=true;
            pong_accept_tiles(&t->pong,(uint16_t)m->next_phase,m->now,m->count);
        }
    }
    if (success) {
        m->text_scene=pending; m->text_started=true; m->text_revision=pending.revision;
        struct tile *t=&m->tiles[0];
        if (pending.host_frames) memcpy(t->columns,pending.pixels,8);
        else scene_tile(t->columns,&pending,0,m->count*8);
        t->raw=true; pong_accept_tiles(&t->pong,(uint16_t)m->next_phase,m->now,m->count);
        m->next_phase=(m->next_phase+1)%pong_phase_count(m->count);
    } else pong_failed(&m->tiles[0].pong);
}

void model_exchange(struct renderer_model *m)
{
    if (m->pwm_demo) {
        if(m->pwm_started && !m->paused) ++m->pwm_tick;
        for(unsigned i=0;i<m->count;++i) {
            struct tile *t=&m->tiles[i];
            pwm_show_tile(t->levels,m->pwm_tick,i,m->count,m->pwm_choice);
            memset(t->columns,0,8);
            for(unsigned y=0;y<8;++y) for(unsigned x=0;x<8;++x)
                if(t->levels[y*8+x]) t->columns[x]|=(uint8_t)(1U<<y);
            t->raw=true;
        }
        m->pwm_started=true;
        return;
    }
    if (m->text_demo) { text_exchange(m); return; }
    uint16_t sent=(uint16_t)(m->next_phase | (m->paused ? PONG_PAUSED : 0));
    uint8_t packet[4]; packet_encode(packet, sent);
    bool success=true;
    for (unsigned i=0; i<m->count; ++i) {
        struct tile *t=&m->tiles[i];
        if (!t->link) { success=false; break; }
        uint8_t received[4]; memcpy(received,packet,sizeof received);
        if (t->corrupt) { received[3]^=1; t->corrupt=false; }
        uint16_t value;
        if (!packet_decode(received,4,&value)) {
            if (i) pong_failed(&t->pong);
            success=false; break;
        }
        /* Controller commits only after the whole simulated chain acknowledges. */
        if (i && !pong_accept_tiles(&t->pong,value,m->now,m->count)) { success=false; break; }
        t->raw=false;
    }
    if (success) {
        pong_accept_tiles(&m->tiles[0].pong,sent,m->now,m->count);
        if (!m->paused) m->next_phase=(m->next_phase+1)%pong_phase_count(m->count);
    } else pong_failed(&m->tiles[0].pong);
}

void model_advance(struct renderer_model *m, unsigned ms)
{
    if (m->external) { m->now+=ms; return; }
    while (ms) {
        unsigned slice=m->interval-m->elapsed;
        if (slice>ms) slice=ms;
        m->now+=slice; m->elapsed+=slice; ms-=slice;
        if (m->elapsed==m->interval) { m->elapsed=0; model_exchange(m); }
    }
}

void model_columns(const struct renderer_model *m, unsigned i, uint8_t columns[8])
{
    if (m->tiles[i].raw) memcpy(columns,m->tiles[i].columns,8);
    else pong_frame_tiles(&m->tiles[i].pong,i,m->count,m->now,columns);
}

void model_status(const struct renderer_model *m, FILE *out)
{
    fprintf(out,"{\"ok\":true,\"boards\":%u,\"phase_count\":%u,\"now_ms\":%u,"
                "\"interval_ms\":%u,\"running\":%s,\"paused\":%s,\"mode\":\"%s\",\"tiles\":[",
            m->count,pong_phase_count(m->count),m->now,m->interval,
            m->running?"true":"false",(m->text_demo?m->text_scene.paused:m->paused)?"true":"false",m->external?"external":"simulation");
    for (unsigned i=0; i<m->count; ++i) {
        const struct tile *t=&m->tiles[i]; uint8_t columns[8]; model_columns(m,i,columns);
        fprintf(out,"%s{\"index\":%u,\"phase\":%u,\"accepted\":%u,\"failed\":%u,"
                    "\"alive\":%s,\"link\":%s,\"raw\":%s,\"columns\":\"",
                i?",":"",i,t->pong.phase,t->pong.accepted,t->pong.failed,
                pong_alive(&t->pong,m->now)?"true":"false",t->link?"true":"false",t->raw?"true":"false");
        for (unsigned x=0; x<8; ++x) fprintf(out,"%02x",columns[x]);
        fputs("\",\"levels\":\"",out);
        if(m->pwm_demo) for(unsigned p=0;p<64;++p) fprintf(out,"%02x",t->levels[p]);
        fputs("\"}",out);
    }
    fprintf(out,"],\"pwm_scene\":\"%s\",\"pwm_auto\":%s,\"pwm_tick\":%u,\"pwm_brightness_pct\":%u,\"pwm_audio\":%s,",
            pwm_show_name(pwm_show_scene(m->pwm_tick,m->pwm_choice)),m->pwm_choice<0?"true":"false",m->pwm_tick,m->pwm_brightness,m->pwm_audio?"true":"false");
    fprintf(out,"\"demo\":\"%s\",\"text_mode\":\"%s\",\"text_columns\":%zu,\"text_offset\":%u,\"brightness_pct\":%u,\"effective_brightness_pct\":%u,\"pulse\":%s,\"text_line\":%u,\"uart_reply\":\"",
            m->pwm_demo?"pwm":m->text_demo?"text":"pong",scene_mode_name(&m->text_scene),scene_columns(message_text(),message_length()),m->text_scene.offset,m->text_scene.brightness,scene_brightness(&m->text_scene),m->text_scene.pulse?"true":"false",m->text_scene.line);
    for (const char *p=m->uart_reply;*p;++p) {
        if (*p=='\r') fputs("\\r",out);
        else if (*p=='\n') fputs("\\n",out);
        else if (*p=='"' || *p=='\\') { fputc('\\',out); fputc(*p,out); }
        else fputc(*p,out);
    }
    fputs("\"}\n",out);
}

static bool number(const char *s, unsigned max, unsigned *value)
{
    if (!*s) return false;
    unsigned v=0;
    for (; *s; ++s) {
        if (*s<'0' || *s>'9') return false;
        unsigned d=(unsigned)(*s-'0');
        if (v>max/10 || (v==max/10 && d>max%10)) return false;
        v=v*10+d;
    }
    *value=v; return true;
}

static bool hex_bytes(const char *s, uint8_t *bytes, unsigned count)
{
    if (strlen(s)!=count*2) return false;
    for (unsigned i=0; i<count; ++i) {
        unsigned v=0;
        for (unsigned j=0; j<2; ++j) {
            unsigned char c=(unsigned char)s[i*2+j];
            unsigned d=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:16;
            if (d==16) return false;
            v=v*16+d;
        }
        bytes[i]=(uint8_t)v;
    }
    return true;
}

bool model_command(struct renderer_model *m, const char *command)
{
    if (!strncmp(command,"uart ",5)) {
        if (!m->text_demo || strlen(command)>=512) return false;
        uint32_t revision=m->text_scene.revision;
        unsigned interval=m->interval;
        char reply[128];
        const char *r=scene_command(&m->text_scene,command+5,m->now,0,0,reply);
        if (r) {
            if (strlen(r)>=sizeof m->uart_reply) return false;
            strcpy(m->uart_reply,r);
        } else m->uart_reply[0]=0;
        m->interval=m->text_scene.interval;
        if (m->interval!=interval || m->text_scene.revision!=revision) m->elapsed=0;
        return !r || strncmp(r,"ERR ",4);
    }
    if (strlen(command)>=256) return false;
    char copy[256]; strcpy(copy,command);
    char *save=NULL, *parts[4]={0}; unsigned n=0;
    for (char *p=strtok_r(copy," \t",&save); p; p=strtok_r(NULL," \t",&save)) {
        if (n==4) return false;
        parts[n++]=p;
    }
    if (!n) return false;
    unsigned value=0, index=0;
    if (n==1) {
        if (!strcmp(parts[0],"status")) return true;
        if (!strcmp(parts[0],"pause")) { m->paused=true; if(m->text_demo) scene_key(&m->text_scene,'p'); return true; }
        if (!strcmp(parts[0],"resume")) { m->paused=false; if(m->text_demo) scene_key(&m->text_scene,'r'); return true; }
        if (!strcmp(parts[0],"stop")) { m->running=false; return true; }
        if (!strcmp(parts[0],"run")) { m->running=true; return true; }
        if (!strcmp(parts[0],"reset")) { model_reset(m); return true; }
    }
    if ((n==1 || n==2) && !strcmp(parts[0],"step")) {
        if (n==1) value=1;
        else if (!number(parts[1],10000,&value) || !value) return false;
        model_advance(m,value*m->interval); return true;
    }
    if (n==2) {
        if (!strcmp(parts[0],"demo")) {
            if (strcmp(parts[1],"text") && strcmp(parts[1],"pong") && strcmp(parts[1],"pwm")) return false;
            model_reset(m); m->text_demo=!strcmp(parts[1],"text"); m->pwm_demo=!strcmp(parts[1],"pwm"); m->external=false;
            m->interval=m->pwm_demo?40:m->text_demo?m->text_scene.interval:100; m->elapsed=0;
            if(m->pwm_demo) { m->pwm_choice=-1; m->pwm_brightness=100; model_exchange(m); }
            return true;
        }
        if (!strcmp(parts[0],"mode")) {
            if (strcmp(parts[1],"simulation") && strcmp(parts[1],"external")) return false;
            m->external=!strcmp(parts[1],"external"); model_reset(m); return true;
        }
        if (!strcmp(parts[0],"boards")) {
            if (!number(parts[1],PONG_MAX_TILES,&value) || !value) return false;
            bool running=m->running, external=m->external, text_demo=m->text_demo,pwm_demo=m->pwm_demo;
            int choice=m->pwm_choice; uint8_t brightness=m->pwm_brightness;
            if (!model_init(m,value)) return false;
            m->running=running; m->external=external; m->text_demo=text_demo;
            m->pwm_demo=pwm_demo; m->pwm_choice=choice; m->pwm_brightness=brightness;
            if(pwm_demo) { m->interval=40; model_exchange(m); }
            if (text_demo) m->interval=m->text_scene.interval;
            return true;
        }
        if (!strcmp(parts[0],"advance")) {
            if (!number(parts[1],3600000,&value)) return false;
            model_advance(m,value); return true;
        }
        if (!strcmp(parts[0],"speed")) {
            if (!number(parts[1],500,&value) || value<(m->pwm_demo?10U:50U)) return false;
            m->interval=value; m->elapsed=0;
            if (m->text_demo) { m->text_scene.interval=value; ++m->text_scene.revision; }
            return true;
        }
        if (!strcmp(parts[0],"corrupt")) {
            if (!number(parts[1],m->count-1,&index)) return false;
            m->tiles[index].corrupt=true; return true;
        }
    }
    if(n==3 && !strcmp(parts[0],"pwm") && m->pwm_demo) {
        if(!strcmp(parts[1],"audio")) {
            if(strcmp(parts[2],"on") && strcmp(parts[2],"off")) return false;
            m->pwm_audio=!strcmp(parts[2],"on");
            if(m->pwm_audio) m->running=false;
            return true;
        }
        if(!strcmp(parts[1],"seek")) {
            if(!number(parts[2],3600000,&value)) return false;
            m->now=value; m->elapsed=value%m->interval;
            m->pwm_tick=value/m->interval; m->pwm_started=false;
            model_exchange(m); return true;
        }
        if(!strcmp(parts[1],"scene")) {
            static const char *const names[]={"silk","ripples","comets","lanterns","ladder","daisy"};
            int choice=-2;
            if(!strcmp(parts[2],"auto")) choice=-1;
            for(unsigned i=0;i<PWM_SHOW_SCENES;++i) if(!strcmp(parts[2],names[i])) choice=(int)i;
            if(choice==-2) return false;
            m->pwm_choice=choice; m->pwm_tick=0; m->pwm_started=false; m->elapsed=0; model_exchange(m); return true;
        }
        if(!strcmp(parts[1],"brightness")) {
            if(!number(parts[2],100,&value)) return false;
            m->pwm_brightness=(uint8_t)value; return true;
        }
    }
    if (n==3 && number(parts[1],m->count-1,&index)) {
        if (!strcmp(parts[0],"levels")) {
            uint8_t levels[64];
            if (!hex_bytes(parts[2],levels,64)) return false;
            for (unsigned p=0;p<64;++p) if (levels[p]>100) return false;
            memcpy(m->tiles[index].levels,levels,64);
            memset(m->tiles[index].columns,0,8);
            for(unsigned y=0;y<8;++y) for(unsigned x=0;x<8;++x)
                if(levels[y*8+x])m->tiles[index].columns[x]|=(uint8_t)(1U<<y);
            m->tiles[index].raw=true;
            m->external=m->pwm_demo=true;m->text_demo=m->running=false;
            m->pwm_brightness=100;
            return true;
        }
        if (!strcmp(parts[0],"link")) {
            if (strcmp(parts[2],"up") && strcmp(parts[2],"down")) return false;
            m->tiles[index].link=!strcmp(parts[2],"up"); return true;
        }
        if (!strcmp(parts[0],"frame")) {
            uint8_t columns[8]; if (!hex_bytes(parts[2],columns,8)) return false;
            memcpy(m->tiles[index].columns,columns,8); m->tiles[index].raw=true; return true;
        }
        if (!strcmp(parts[0],"packet")) {
            uint8_t packet[4]; uint16_t phase;
            if (!hex_bytes(parts[2],packet,4) || !packet_decode(packet,4,&phase)) return false;
            if (!pong_accept_tiles(&m->tiles[index].pong,phase,m->now,m->count)) return false;
            m->tiles[index].raw=false; return true;
        }
        if (!strcmp(parts[0],"receive")) {
            if (!number(parts[2],65535,&value)) return false;
            if (!pong_accept_tiles(&m->tiles[index].pong,(uint16_t)value,m->now,m->count)) return false;
            m->tiles[index].raw=false; return true;
        }
    }
    return false;
}
