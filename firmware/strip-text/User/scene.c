#if !defined(STRIP_TILE) || !STRIP_TILE
#include "scene.h"
#include "font.h"
#include "message.h"
#include "speed.h"
#include "brightness.h"
#include "frame_input.h"
#include <string.h>

static unsigned width(wchar_t ch) { return ch==L' ' ? 2U : 4U; }
size_t scene_columns(const wchar_t *text, size_t length)
{
    size_t n=0; for (size_t i=0;i<length;++i) n+=width(text[i]); return n;
}
void scene_frame(uint8_t frame[8], const wchar_t *text, size_t length,
                 unsigned offset, unsigned tile, bool repeat)
{
    size_t total=scene_columns(text,length);
    for (unsigned x=0;x<8;++x) {
        size_t pos=(size_t)offset+8U*tile+x;
        if (!total || (!repeat && pos>=total)) { frame[x]=0; continue; }
        if (repeat) pos%=total;
        size_t ch=0;
        while (pos>=width(text[ch])) pos-=width(text[ch++]);
        frame[x]=text[ch]==L' ' ? 0 : font_compact_column(text[ch],(uint8_t)pos);
    }
}
/* Greedy word wrapping without another text buffer. Long words split only
   when necessary. The message parser's surrounding spaces are skipped. */
static size_t line_end(size_t start, unsigned columns)
{
    const wchar_t *text=message_text();
    size_t length=message_length(), end=start, space=start;
    unsigned used=0;
    while (end<length && used+width(text[end])<=columns) {
        used+=width(text[end]);
        if (text[end]==L' ') space=end;
        ++end;
    }
    if (end<length && text[end]!=L' ' && space>start) end=space;
    return end>start ? end : start+1;
}
static size_t next_line(size_t end)
{
    while (end<message_length() && message_text()[end]==L' ') ++end;
    return end;
}
static void fall_tile(uint8_t frame[8], const struct scene *s, unsigned tile, unsigned columns)
{
    size_t start=next_line(0), end=start;
    for (unsigned n=0;n<=s->line && start<message_length();++n) {
        end=line_end(start,columns);
        if (n<s->line) start=next_line(end);
    }
    while (end>start && message_text()[end-1]==L' ') --end;
    unsigned used=(unsigned)scene_columns(message_text()+start,end-start);
    /* Omit the last letter's inter-character gap when centering. */
    if (used) --used;
    unsigned left=used<columns?(columns-used)/2:0;
    for (unsigned x=0;x<8;++x) {
        unsigned px=tile*8+x;
        uint8_t bits=0;
        if (px>=left && px-left<used) {
            size_t pos=px-left, ch=start;
            while (ch<end && pos>=width(message_text()[ch])) pos-=width(message_text()[ch++]);
            if (ch<end && message_text()[ch]!=L' ')
                bits=font_compact_column(message_text()[ch],(uint8_t)pos);
        }
        /* Bit zero is the top row: shift toward larger bits to fall down. */
        frame[x]=s->offset<8 ? (uint8_t)(bits>>(7-s->offset)) :
                              (uint8_t)((unsigned)bits<<(s->offset-7));
    }
}
void scene_tile(uint8_t frame[8], const struct scene *s, unsigned tile, unsigned columns)
{
    if (s->host_frames) {
        if (tile<2) memcpy(frame,s->pixels+8*tile,8);
        else memset(frame,0,8);
        return;
    }
    if (s->mode!=SCENE_FALL) {
        scene_frame(frame,message_text(),message_length(),s->offset,tile,s->mode==SCENE_SCROLL);
        return;
    }
    fall_tile(frame,s,tile,columns);
}
uint8_t scene_brightness(const struct scene *s)
{
    if (!s->pulse || s->host_frames) return s->brightness;
    unsigned phase=s->pulse_phase;
    unsigned triangle=phase<=32?phase:64-phase;
    /* Requested percentage remains the ceiling; zero always stays dark. */
    return (uint8_t)((s->brightness*(5U+95U*triangle/32U)+50U)/100U);
}
const char *scene_mode_name(const struct scene *s)
{
    return s->mode==SCENE_FALL?"fall":s->mode==SCENE_SCROLL?"scroll":"bounce";
}
void scene_render(struct scene *s)
{
    if (s->host_frames) return;
    if (s->mode==SCENE_FALL) {
        fall_tile(s->pixels,s,0,SCENE_COLUMNS);
        fall_tile(s->pixels+8,s,1,SCENE_COLUMNS);
    } else {
        scene_frame(s->pixels,message_text(),message_length(),s->offset,0,s->mode==SCENE_SCROLL);
        scene_frame(s->pixels+8,message_text(),message_length(),s->offset,1,s->mode==SCENE_SCROLL);
    }
}
static void rewind_scene(struct scene *s)
{
    s->offset=s->dwell=s->line=0; s->pulse_phase=0; s->reverse=false; s->host_frames=false;
    ++s->revision; scene_render(s);
}
void scene_init(struct scene *s)
{
    memset(s,0,sizeof *s); s->interval=SCENE_DEFAULT_MS; s->brightness=100; s->mode=SCENE_BOUNCE;
    message_init(SCENE_DEFAULT_TEXT); rewind_scene(s);
}
void scene_next_width(struct scene *s, unsigned display_columns)
{
    if (s->paused || s->host_frames) return;
    /* Four falling lines per pulse: their fully visible phases get different
       levels, rather than the equal levels of a two-line symmetric pulse. */
    s->pulse_phase=(s->pulse_phase+1U)%64U;
    unsigned total=(unsigned)scene_columns(message_text(),message_length());
    if (s->mode==SCENE_FALL) {
        if (++s->offset==16) {
            s->offset=0;
            size_t start=next_line(0);
            for (unsigned n=0;n<=s->line && start<message_length();++n)
                start=next_line(line_end(start,display_columns));
            s->line=start<message_length()?s->line+1:0;
        }
    }
    else if (s->mode==SCENE_SCROLL) s->offset=total?(s->offset+1)%total:0;
    else if (total>display_columns) {
        unsigned end=total-display_columns;
        if (s->dwell) --s->dwell;
        else if (s->reverse) {
            if (s->offset) --s->offset;
            if (!s->offset) { s->reverse=false; s->dwell=8; }
        } else {
            if (s->offset<end) ++s->offset;
            if (s->offset==end) { s->reverse=true; s->dwell=8; }
        }
    }
    scene_render(s);
}
void scene_next(struct scene *s) { scene_next_width(s,SCENE_COLUMNS); }
bool scene_editing(void)
{
    return message_editing() || speed_editing() || brightness_editing() || frame_editing();
}
const char *scene_key(struct scene *s, uint8_t key)
{
    if (message_editing()) {
        switch (message_feed(key)) {
            case MESSAGE_APPLIED: s->paused=false; rewind_scene(s); return "OK text updated\r\n";
            case MESSAGE_CANCELLED: return "Text cancelled\r\n";
            case MESSAGE_INVALID: return "ERR invalid UTF-8; text unchanged\r\n";
            case MESSAGE_TOO_LONG: return "ERR max 64 characters; text unchanged\r\n";
            default: return NULL;
        }
    }
    if (speed_editing()) {
        switch (speed_feed(key,&s->interval)) {
            case SPEED_APPLIED: ++s->revision; return "OK speed updated\r\n";
            case SPEED_INVALID: return "ERR speed must be 10..500 ms\r\n";
            case SPEED_CANCELLED: return "Speed cancelled\r\n";
            default: return NULL;
        }
    }
    if (brightness_editing()) {
        switch (brightness_feed(key,&s->brightness)) {
            case BRIGHTNESS_APPLIED: ++s->revision; return "OK brightness updated\r\n";
            case BRIGHTNESS_INVALID: return "ERR brightness must be 0..100; unchanged\r\n";
            case BRIGHTNESS_CANCELLED: return "Brightness cancelled\r\n";
            default: return NULL;
        }
    }
    if (frame_editing()) {
        static uint8_t pixels[8];
        switch (frame_feed(key,pixels)) {
            case FRAME_APPLIED:
                memcpy(s->pixels,pixels,8); memset(s->pixels+8,0,8);
                s->host_frames=true; ++s->revision; return "FRAME\r\n";
            case FRAME_INVALID: return "ERR frame needs 16 hex digits\r\n";
            case FRAME_CANCELLED: return "Frame cancelled\r\n";
            default: return NULL;
        }
    }
    switch (key) {
        case 't': message_begin(); return NULL;
        case 'v': speed_begin(); return NULL;
        case 'b': brightness_begin(); return NULL;
        case 'f': frame_begin(); return NULL;
        case 'p': s->paused=true; break;
        case 'r': s->paused=false; break;
        case 'a': s->paused=true; rewind_scene(s); return "ARMED\r\n";
        case '0': s->interval=SCENE_DEFAULT_MS; s->brightness=100;
                  s->mode=SCENE_BOUNCE; s->pulse=false; s->paused=false; rewind_scene(s); return NULL;
        case '+': if (s->interval>10) s->interval=s->interval>15?s->interval-5:10; break;
        case '-': if (s->interval<500) s->interval=s->interval<495?s->interval+5:500; break;
        default: return NULL;
    }
    ++s->revision; return NULL;
}
static char *append(char *p, const char *s) { while (*s) *p++=*s++; return p; }
static char *decimal(char *p, uint32_t n)
{
    char digits[10]; unsigned used=0;
    do { digits[used++]=(char)('0'+n%10); n/=10; } while (n);
    while (used) *p++=digits[--used];
    return p;
}
void scene_status(const struct scene *s, uint32_t now, uint32_t errors,
                  uint32_t drops, char reply[128])
{
    char *p=append(reply,"speed_ms="); p=decimal(p,s->interval);
    p=append(p," paused="); p=decimal(p,s->paused);
    p=append(p," uptime_ms="); p=decimal(p,now);
    p=append(p," uart_errors="); p=decimal(p,errors);
    p=append(p," tx_dropped="); p=decimal(p,drops);
    p=append(p," brightness_pct="); p=decimal(p,s->brightness);
    p=append(p,"\r\n"); *p=0;
}
const char *scene_command(struct scene *s, const char *line, uint32_t now,
                          uint32_t errors, uint32_t drops, char reply[128])
{
    if (!*line) return NULL;
    if (!strcmp(line,"status") || !strcmp(line,"s")) {
        scene_status(s,now,errors,drops,reply); return reply;
    }
    if (!strcmp(line,"h") || !strcmp(line,"help") || !strcmp(line,"?"))
        return "t TEXT; m scroll|bounce|fall; e pulse|off; v 10..500; b 0..100; p/r/0; a arm; f16hex; g32hex; ping TOKEN\r\n";
    if (!strcmp(line,"ping") || !strncmp(line,"ping ",5)) {
        size_t n=strlen(line);
        if (n>79) return "ERR ping needs at most 79 ASCII bytes\r\n";
        for (size_t i=0;i<n;++i) if ((uint8_t)line[i]>126) return "ERR ping needs ASCII\r\n";
        char *p=append(reply,"PONG"); p=append(p,line+4); p=append(p,"\r\n"); *p=0; return reply;
    }
    if (scene_editing())
        return "ERR busy; finish or cancel SWIO edit\r\n";
    if (!strncmp(line,"m ",2)) {
        if (!strcmp(line+2,"scroll")) s->mode=SCENE_SCROLL;
        else if (!strcmp(line+2,"bounce")) s->mode=SCENE_BOUNCE;
        else if (!strcmp(line+2,"fall")) s->mode=SCENE_FALL;
        else return "ERR mode must be scroll, bounce or fall\r\n";
        s->pulse=s->mode==SCENE_FALL;
        s->paused=false; rewind_scene(s); return "OK mode updated\r\n";
    }
    if (!strncmp(line,"e ",2)) {
        if (!strcmp(line+2,"pulse")) s->pulse=true;
        else if (!strcmp(line+2,"off")) s->pulse=false;
        else return "ERR effect must be pulse or off\r\n";
        s->pulse_phase=0; ++s->revision; return "OK effect updated\r\n";
    }
    if (line[0]=='g') {
        const char *hex=line+1; if (*hex==' ') ++hex;
        if (strlen(hex)!=32) return "ERR strip frame needs 32 hex digits\r\n";
        uint8_t pixels[16];
        for (unsigned i=0;i<32;++i) {
            uint8_t c=(uint8_t)hex[i];
            unsigned d=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:16;
            if (d==16) return "ERR strip frame needs 32 hex digits\r\n";
            if (!(i&1)) pixels[i/2]=(uint8_t)(d<<4); else pixels[i/2]|=(uint8_t)d;
        }
        memcpy(s->pixels,pixels,16); s->host_frames=true; ++s->revision; return "FRAME\r\n";
    }
    if (line[1]==0 && strchr("+-pr0a",line[0])) {
        const char *result=scene_key(s,(uint8_t)line[0]);
        if (result) return result;
        scene_status(s,now,errors,drops,reply); return reply;
    }
    if (((line[0]=='t'||line[0]=='v'||line[0]=='b') && (line[1]==' '||line[1]==0)) || line[0]=='f') {
        for (size_t i=0;line[i];++i) scene_key(s,(uint8_t)line[i]);
        return scene_key(s,'\n');
    }
    return "ERR unknown command; use t TEXT or h\r\n";
}
#endif
