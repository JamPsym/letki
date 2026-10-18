#define _GNU_SOURCE
#include "model.h"
#include "xdg-shell-client-protocol.h"
#include <cairo/cairo.h>
#include <wayland-client.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input-event-codes.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#define CLIENTS 8
#define COMMAND_SIZE 4096
static volatile sig_atomic_t interrupted;
static void interrupt_handler(int sig) { (void)sig; interrupted=1; }
static uint64_t monotonic_ms(void)
{
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return (uint64_t)t.tv_sec*1000+(unsigned)t.tv_nsec/1000000;
}
struct buffer {
    struct wl_buffer *wl;
    cairo_surface_t *image;
    void *data;
    size_t size;
    struct buffer *next;
};
struct client { int fd; size_t used; char command[COMMAND_SIZE]; uint64_t started; };
struct app {
    struct renderer_model model;
    struct wl_display *display;
    struct wl_registry *registry;
    struct wl_compositor *compositor;
    struct wl_shm *shm;
    struct xdg_wm_base *wm;
    struct wl_surface *surface;
    struct xdg_surface *xdg;
    struct xdg_toplevel *toplevel;
    struct wl_seat *seat;
    struct wl_keyboard *keyboard;
    struct wl_callback *frame;
    struct buffer *buffers;
    struct client clients[CLIENTS];
    int server, width, height;
    bool configured, dirty, quit, headless, pwm_title;
    char socket_path[sizeof(((struct sockaddr_un *)0)->sun_path)];
    dev_t socket_dev; ino_t socket_ino;
};

static void label(cairo_t *cr, double x, double y, double size, const char *text)
{
    cairo_set_font_size(cr,size); cairo_move_to(cr,x,y); cairo_show_text(cr,text);
}
static void fitted_label(cairo_t *cr, double x, double y, double size,
                         double available, const char *text)
{
    cairo_text_extents_t extent;
    cairo_set_font_size(cr,size); cairo_text_extents(cr,text,&extent);
    if (extent.width>available && available>0) size*=available/extent.width;
    label(cr,x,y,size,text);
}
static void paint(struct app *a, cairo_surface_t *image, int width, int height)
{
    if(a->toplevel && a->pwm_title!=a->model.pwm_demo) {
        a->pwm_title=a->model.pwm_demo;
        xdg_toplevel_set_title(a->toplevel,a->pwm_title?"Letki PWM show":"Letki test renderer");
    }
    cairo_t *cr=cairo_create(image);
    cairo_set_source_rgb(cr,.035,.045,.065); cairo_paint(cr);
    cairo_select_font_face(cr,"sans",CAIRO_FONT_SLANT_NORMAL,CAIRO_FONT_WEIGHT_NORMAL);
    cairo_set_source_rgb(cr,.92,.95,1);
    label(cr,24,36,22,a->model.external && a->model.pwm_demo?"LETKI  /  general firmware preview":a->model.pwm_demo?"LETKI  /  LIGHT STUDY":a->model.text_demo?"LETKI  /  standard text firmware preview":"LETKI  /  native strip test");
    char text[256];
    snprintf(text,sizeof text,"%u boards  |  %s  |  %s  |  %u ms/step  |  clock %u ms",
             a->model.count,a->model.text_demo?(scene_mode_name(&a->model.text_scene)):a->model.external?"External frames":"Simulated transport",
             a->model.running?((a->model.text_demo?a->model.text_scene.paused:a->model.paused)?"Paused, live exchanges":"Running"):"Manual clock",
             a->model.interval,a->model.now);
    if(a->model.pwm_demo && !a->model.external)
        snprintf(text,sizeof text,"%u x 8  /  %s  /  %s  /  brightness %u%%",
                 a->model.count*8,pwm_show_name(pwm_show_scene(a->model.pwm_tick,a->model.pwm_choice)),
                 a->model.paused?"Paused":a->model.pwm_audio?"Audio synchronized":a->model.pwm_choice<0?"Continuous show":"Single scene",a->model.pwm_brightness);
    cairo_set_source_rgb(cr,.57,.65,.77); fitted_label(cr,24,62,13,width-48,text);
    double cell=fmin((width-48.0)/(a->model.count*8.0),(height-230.0)/8.0);
    if (cell<.01) cell=.01;
    double ox=(width-a->model.count*8*cell)/2, oy=100+(height-230-8*cell)/2;
    for (unsigned i=0; i<a->model.count; ++i) {
        double x=ox+i*8*cell;
        bool alive=a->model.pwm_demo || pong_alive(&a->model.tiles[i].pong,a->model.now);
        cairo_set_source_rgb(cr,.07,.10,.13);
        cairo_rectangle(cr,x+1,oy+1,8*cell-2,8*cell-2); cairo_fill(cr);
        cairo_set_source_rgb(cr,alive?.16:.7,alive?.30:.21,alive?.26:.16);
        cairo_rectangle(cr,x+1,oy+1,8*cell-2,8*cell-2); cairo_set_line_width(cr,1); cairo_stroke(cr);
        uint8_t columns[8]; model_columns(&a->model,i,columns);
        for (unsigned col=0; col<8; ++col) for (unsigned row=0; row<8; ++row) {
            bool lit=(columns[col]&(1U<<row))!=0;
            double level=a->model.text_demo?pow(scene_brightness(&a->model.text_scene)/100.0,2.2):1;
            if(a->model.pwm_demo) {
                unsigned percept=(a->model.tiles[i].levels[row*8+col]*a->model.pwm_brightness+50U)/100U;
                double ticks=round(1200*pow(percept/100.0,2.2));
                if(percept && ticks<1) ticks=1;
                /* PWM models linear emitted light; encode it for a display
                   rather than applying gamma twice to the screen pixels. */
                level=pow(ticks/1200.0,1/2.2); lit=percept!=0;
            }
            if (!level) lit=false;
            double cx=x+(col+.5)*cell, cy=oy+(row+.5)*cell;
            if (lit) {
                cairo_set_source_rgba(cr,1,.30,.015,a->model.pwm_demo?.15*level:.14);
                cairo_arc(cr,cx,cy,cell*.45,0,2*M_PI); cairo_fill(cr);
            }
            cairo_set_source_rgb(cr,lit?fmax(.14,level):.14,lit?fmax(.17,.49*level):.17,lit?fmax(.13,.13*level):.19);
            if(a->model.pwm_demo) cairo_set_source_rgb(cr,.035+.965*level,.045+.31*level,.055+.025*level);
            cairo_arc(cr,cx,cy,cell*.29,0,2*M_PI); cairo_fill(cr);
        }
        if (cell>=5) {
            if(a->model.pwm_demo) {
                unsigned sum=0;
                for(unsigned p=0;p<64;++p) sum+=a->model.tiles[i].levels[p];
                snprintf(text,sizeof text,"%02u    %u%% mean",i+1,(sum*a->model.pwm_brightness+3200)/6400);
                cairo_set_source_rgb(cr,.52,.49,.45);
                fitted_label(cr,x+5,oy+8*cell+24,fmin(12,cell*1.2),8*cell-10,text);
                continue;
            }
            snprintf(text,sizeof text,"#%u  %s",i,a->model.text_demo?"TEXT":a->model.tiles[i].raw?"FRAME":alive?"OK":"WAIT / FAULT");
            cairo_set_source_rgb(cr,.72,.77,.86); label(cr,x+5,oy+8*cell+21,fmin(12,cell*1.2),text);
            snprintf(text,sizeof text,"phase %u",a->model.tiles[i].pong.phase);
            fitted_label(cr,x+5,oy+8*cell+39,fmin(10,cell*.9),8*cell-10,text);
            snprintf(text,sizeof text,"rx %u / bad %u",a->model.tiles[i].pong.accepted,a->model.tiles[i].pong.failed);
            fitted_label(cr,x+5,oy+8*cell+53,fmin(10,cell*.9),8*cell-10,text);
        }
    }
    cairo_set_source_rgb(cr,.62,.68,.78);
    if(a->model.pwm_demo) {
        unsigned active=pwm_show_scene(a->model.pwm_tick,a->model.pwm_choice);
        double segment=(width-48.0)/PWM_SHOW_SCENES;
        for(unsigned i=0;i<PWM_SHOW_SCENES;++i) {
            cairo_set_source_rgb(cr,i==active?.95:.36,i==active?.51:.38,i==active?.21:.40);
            fitted_label(cr,24+i*segment,height-81,12,segment-12,pwm_show_name(i));
            cairo_rectangle(cr,24+i*segment,height-69,segment-14,2);cairo_fill(cr);
        }
        if(a->model.pwm_choice<0) {
            cairo_set_source_rgb(cr,1,.43,.10);
            cairo_rectangle(cr,24+active*segment,height-69,(segment-14)*(a->model.pwm_tick%PWM_SHOW_ACT_STEPS)/(double)PWM_SHOW_ACT_STEPS,3);cairo_fill(cr);
        }
        cairo_set_source_rgb(cr,.62,.65,.69);
        fitted_label(cr,24,height-36,12,width-48,a->model.pwm_audio?
                     "Space pause sound + light   +/- brightness   Q close":
                     "Space pause   N next scene   A automatic show   +/- brightness   R restart   Q close");
        snprintf(text,sizeof text,"%u individually dimmed pixels  /  gamma 2.2  /  simulation preview",a->model.count*64);
        fitted_label(cr,24,height-16,11,width-48,text);
        cairo_destroy(cr);cairo_surface_flush(image);return;
    }
    fitted_label(cr,24,height-36,12,width-48,"Space pause   Enter run/stop clock   Right step   R reset   L break/restore last link   1-5 boards");
    fitted_label(cr,24,height-16,11,width-48,"Simulation checks pixels and protocol logic; electrical timing and optical output require the real boards.");
    cairo_destroy(cr); cairo_surface_flush(image);
}

static bool snapshot(struct app *a, const char *path)
{
    cairo_surface_t *s=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,a->width,a->height);
    if (cairo_surface_status(s)!=CAIRO_STATUS_SUCCESS) { cairo_surface_destroy(s); return false; }
    paint(a,s,a->width,a->height);
    cairo_status_t result=cairo_surface_write_to_png(s,path);
    cairo_surface_destroy(s); return result==CAIRO_STATUS_SUCCESS;
}

static void destroy_buffer(struct app *a, struct buffer *b)
{
    struct buffer **p=&a->buffers;
    while (*p && *p!=b) p=&(*p)->next;
    if (*p) *p=b->next;
    wl_buffer_destroy(b->wl); cairo_surface_destroy(b->image);
    munmap(b->data,b->size); free(b);
}
static void buffer_release(void *data, struct wl_buffer *wl)
{
    (void)wl;
    struct app *a=data;
    for (struct buffer *b=a->buffers; b; b=b->next)
        if (b->wl==wl) { destroy_buffer(a,b); return; }
}
static const struct wl_buffer_listener buffer_listener={.release=buffer_release};
static void frame_done(void *data, struct wl_callback *cb, uint32_t time)
{
    (void)time; struct app *a=data; wl_callback_destroy(cb); a->frame=NULL;
}
static const struct wl_callback_listener frame_listener={.done=frame_done};

static bool draw(struct app *a)
{
    if (!a->configured || a->frame || !a->dirty || a->headless) return true;
    unsigned outstanding=0;
    for (struct buffer *b=a->buffers; b; b=b->next) ++outstanding;
    if (outstanding>=3) return true;
    int stride=cairo_format_stride_for_width(CAIRO_FORMAT_ARGB32,a->width);
    if (stride<=0) return false;
    size_t size=(size_t)stride*a->height;
    int fd=memfd_create("letki-renderer",MFD_CLOEXEC);
    if (fd<0) return false;
    if (ftruncate(fd,(off_t)size)) { close(fd); return false; }
    void *data=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if (data==MAP_FAILED) { close(fd); return false; }
    struct buffer *b=calloc(1,sizeof *b);
    if (!b) { munmap(data,size); close(fd); return false; }
    b->data=data; b->size=size;
    b->image=cairo_image_surface_create_for_data(data,CAIRO_FORMAT_ARGB32,a->width,a->height,stride);
    struct wl_shm_pool *pool=wl_shm_create_pool(a->shm,fd,(int)size);
    b->wl=wl_shm_pool_create_buffer(pool,0,a->width,a->height,stride,WL_SHM_FORMAT_ARGB8888);
    wl_shm_pool_destroy(pool); close(fd);
    b->next=a->buffers; a->buffers=b;
    wl_buffer_add_listener(b->wl,&buffer_listener,a);
    paint(a,b->image,a->width,a->height);
    wl_surface_attach(a->surface,b->wl,0,0);
    wl_surface_damage(a->surface,0,0,a->width,a->height);
    a->frame=wl_surface_frame(a->surface); wl_callback_add_listener(a->frame,&frame_listener,a);
    wl_surface_commit(a->surface); a->dirty=false;
    return true;
}

static void wm_ping(void *data, struct xdg_wm_base *wm, uint32_t serial)
{ (void)data; xdg_wm_base_pong(wm,serial); }
static const struct xdg_wm_base_listener wm_listener={.ping=wm_ping};
static void surface_configure(void *data, struct xdg_surface *xdg, uint32_t serial)
{
    struct app *a=data; xdg_surface_ack_configure(xdg,serial); a->configured=true; a->dirty=true;
}
static const struct xdg_surface_listener surface_listener={.configure=surface_configure};
static void top_configure(void *data, struct xdg_toplevel *top, int32_t w, int32_t h, struct wl_array *states)
{
    (void)top; (void)states; struct app *a=data;
    if (w>0 && w<=8192) a->width=w;
    if (h>0 && h<=8192) a->height=h;
    a->dirty=true;
}
static void top_close(void *data, struct xdg_toplevel *top) { (void)top; ((struct app *)data)->quit=true; }
static const struct xdg_toplevel_listener top_listener={.configure=top_configure,.close=top_close};
static void keyboard_keymap(void *data, struct wl_keyboard *kb, uint32_t format, int fd, uint32_t size)
{ (void)data; (void)kb; (void)format; (void)size; close(fd); }
static void keyboard_enter(void *data, struct wl_keyboard *kb, uint32_t serial, struct wl_surface *s, struct wl_array *keys)
{ (void)data; (void)kb; (void)serial; (void)s; (void)keys; }
static void keyboard_leave(void *data, struct wl_keyboard *kb, uint32_t serial, struct wl_surface *s)
{ (void)data; (void)kb; (void)serial; (void)s; }
static void keyboard_modifiers(void *data, struct wl_keyboard *kb, uint32_t serial, uint32_t depressed, uint32_t latched, uint32_t locked, uint32_t group)
{ (void)data; (void)kb; (void)serial; (void)depressed; (void)latched; (void)locked; (void)group; }
static void keyboard_repeat(void *data, struct wl_keyboard *kb, int32_t rate, int32_t delay)
{ (void)data; (void)kb; (void)rate; (void)delay; }
static void keyboard_key(void *data, struct wl_keyboard *kb, uint32_t serial, uint32_t time, uint32_t key, uint32_t state)
{
    (void)kb; (void)serial; (void)time;
    if (state!=WL_KEYBOARD_KEY_STATE_PRESSED) return;
    struct app *a=data; struct renderer_model *m=&a->model;
    if (key==KEY_ESC || key==KEY_Q) a->quit=true;
    else if (key==KEY_SPACE) {
        bool paused=m->text_demo?m->text_scene.paused:m->paused;
        model_command(m,paused?"resume":"pause");
    }
    else if(m->pwm_audio && key!=KEY_EQUAL && key!=KEY_MINUS && key!=KEY_KPPLUS && key!=KEY_KPMINUS) {
        /* Scene/time edits would break narration alignment during playback. */
    }
    else if (key==KEY_ENTER) m->running=!m->running;
    else if (key==KEY_RIGHT) { m->running=false; model_advance(m,m->interval); }
    else if (key==KEY_R) model_reset(m);
    else if(m->pwm_demo && (key==KEY_N || key==KEY_A)) {
        static const char *const names[]={"silk","ripples","comets","lanterns","ladder","daisy"};
        char command[64];
        snprintf(command,sizeof command,"pwm scene %s",key==KEY_A?"auto":names[(pwm_show_scene(m->pwm_tick,m->pwm_choice)+1)%PWM_SHOW_SCENES]);
        model_command(m,command);
    }
    else if(m->pwm_demo && (key==KEY_EQUAL || key==KEY_MINUS || key==KEY_KPPLUS || key==KEY_KPMINUS)) {
        int delta=(key==KEY_EQUAL || key==KEY_KPPLUS)?5:-5;
        int value=(int)m->pwm_brightness+delta;
        char command[64];snprintf(command,sizeof command,"pwm brightness %d",value<0?0:value>100?100:value);model_command(m,command);
    }
    else if (key==KEY_L) m->tiles[m->count-1].link=!m->tiles[m->count-1].link;
    else if (key>=KEY_1 && key<=KEY_5) {
        char command[32]; snprintf(command,sizeof command,"boards %u",key-KEY_1+1); model_command(m,command);
    }
    a->dirty=true;
}
static const struct wl_keyboard_listener keyboard_listener={
    .keymap=keyboard_keymap,.enter=keyboard_enter,.leave=keyboard_leave,.key=keyboard_key,
    .modifiers=keyboard_modifiers,.repeat_info=keyboard_repeat
};
static void seat_capabilities(void *data, struct wl_seat *seat, uint32_t caps)
{
    struct app *a=data;
    if ((caps&WL_SEAT_CAPABILITY_KEYBOARD) && !a->keyboard) {
        a->keyboard=wl_seat_get_keyboard(seat); wl_keyboard_add_listener(a->keyboard,&keyboard_listener,a);
    } else if (!(caps&WL_SEAT_CAPABILITY_KEYBOARD) && a->keyboard) {
        wl_keyboard_destroy(a->keyboard); a->keyboard=NULL;
    }
}
static void seat_name(void *data, struct wl_seat *seat, const char *name) { (void)data; (void)seat; (void)name; }
static const struct wl_seat_listener seat_listener={.capabilities=seat_capabilities,.name=seat_name};
static void registry_global(void *data, struct wl_registry *registry, uint32_t name, const char *interface, uint32_t version)
{
    struct app *a=data;
    if (!strcmp(interface,"wl_compositor")) a->compositor=wl_registry_bind(registry,name,&wl_compositor_interface,1);
    else if (!strcmp(interface,"wl_shm")) a->shm=wl_registry_bind(registry,name,&wl_shm_interface,1);
    else if (!strcmp(interface,"xdg_wm_base")) {
        a->wm=wl_registry_bind(registry,name,&xdg_wm_base_interface,1); xdg_wm_base_add_listener(a->wm,&wm_listener,a);
    } else if (!strcmp(interface,"wl_seat") && !a->seat) {
        a->seat=wl_registry_bind(registry,name,&wl_seat_interface,version<5?version:5);
        wl_seat_add_listener(a->seat,&seat_listener,a);
    }
}
static void registry_remove(void *data, struct wl_registry *r, uint32_t name) { (void)data; (void)r; (void)name; }
static const struct wl_registry_listener registry_listener={.global=registry_global,.global_remove=registry_remove};
static bool open_window(struct app *a)
{
    a->display=wl_display_connect(NULL);
    if (!a->display) { fprintf(stderr,"Cannot connect to Wayland: %s. Run inside Hyprland, or use --headless.\n",strerror(errno)); return false; }
    a->registry=wl_display_get_registry(a->display); wl_registry_add_listener(a->registry,&registry_listener,a);
    if (wl_display_roundtrip(a->display)<0 || !a->compositor || !a->shm || !a->wm) return false;
    a->surface=wl_compositor_create_surface(a->compositor);
    a->xdg=xdg_wm_base_get_xdg_surface(a->wm,a->surface); xdg_surface_add_listener(a->xdg,&surface_listener,a);
    a->toplevel=xdg_surface_get_toplevel(a->xdg); xdg_toplevel_add_listener(a->toplevel,&top_listener,a);
    xdg_toplevel_set_title(a->toplevel,"Letki test renderer");
    xdg_toplevel_set_app_id(a->toplevel,"letki-renderer");
    xdg_toplevel_set_min_size(a->toplevel,640,320);
    wl_surface_commit(a->surface); return true;
}

static int connect_socket(const char *path)
{
    struct sockaddr_un addr={.sun_family=AF_UNIX};
    if (strlen(path)>=sizeof addr.sun_path) { errno=ENAMETOOLONG; return -1; }
    strcpy(addr.sun_path,path);
    int fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);
    if (fd<0) return -1;
    if (connect(fd,(struct sockaddr *)&addr,sizeof addr)) { int e=errno; close(fd); errno=e; return -1; }
    return fd;
}
static bool open_server(struct app *a)
{
    struct sockaddr_un addr={.sun_family=AF_UNIX}; strcpy(addr.sun_path,a->socket_path);
    a->server=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC|SOCK_NONBLOCK,0);
    if (a->server<0) return false;
    /* Never unlink an existing socket: another renderer may still own it. */
    mode_t old=umask(0077);
    int result=bind(a->server,(struct sockaddr *)&addr,sizeof addr); umask(old);
    if (result) { fprintf(stderr,"Cannot bind %s: %s (choose --socket for another instance).\n",a->socket_path,strerror(errno)); return false; }
    struct stat st;
    if (lstat(a->socket_path,&st)) return false;
    a->socket_dev=st.st_dev; a->socket_ino=st.st_ino;
    return listen(a->server,CLIENTS)==0;
}
static void respond(struct app *a, int fd, const char *command)
{
    char *reply=NULL; size_t size=0; FILE *out=open_memstream(&reply,&size);
    if (!out) return;
    bool ok=false;
    if (!strcmp(command,"quit")) { a->quit=true; ok=true; }
    else if (!strncmp(command,"snapshot ",9) && command[9]) ok=snapshot(a,command+9);
    else ok=model_command(&a->model,command);
    if (ok) { model_status(&a->model,out); a->dirty=true; }
    else fputs("{\"ok\":false,\"error\":\"Invalid command, packet or snapshot path; state preserved\"}\n",out);
    fclose(out);
    /* Bounded status (<64 KiB), nonblocking socket: a stalled reader cannot halt the UI. */
    size_t used=0;
    while (used<size) {
        ssize_t n=send(fd,reply+used,size-used,MSG_NOSIGNAL);
        if (n<=0) break;
        used+=(size_t)n;
    }
    free(reply);
}
static void accept_clients(struct app *a)
{
    for (unsigned tries=0; tries<CLIENTS; ++tries) {
        int fd=accept4(a->server,NULL,NULL,SOCK_CLOEXEC|SOCK_NONBLOCK);
        if (fd<0) break;
        struct ucred cred; socklen_t length=sizeof cred;
        if (getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&cred,&length) || cred.uid!=getuid()) { close(fd); continue; }
        unsigned i;
        for (i=0; i<CLIENTS; ++i) if (a->clients[i].fd<0) {
            a->clients[i]=(struct client){.fd=fd,.started=monotonic_ms()}; break;
        }
        if (i==CLIENTS) close(fd);
    }
}
static void read_client(struct app *a, struct client *c)
{
    ssize_t n=recv(c->fd,c->command+c->used,sizeof c->command-1-c->used,0);
    if (n<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) return;
    if (n>0) {
        if (memchr(c->command+c->used,0,(size_t)n)) { close(c->fd); c->fd=-1; return; }
        c->used+=(size_t)n; c->command[c->used]=0;
        char *end=strchr(c->command,'\n');
        if (!end && c->used<sizeof c->command-1) return;
        if (end) {
            *end=0; if (end>c->command && end[-1]=='\r') end[-1]=0;
            respond(a,c->fd,c->command);
        }
    }
    close(c->fd); c->fd=-1;
}

static int control(const char *path, int argc, char **argv)
{
    int fd=connect_socket(path);
    if (fd<0) { fprintf(stderr,"Cannot reach renderer %s: %s\n",path,strerror(errno)); return 1; }
    struct timeval timeout={.tv_sec=3};
    setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout);
    setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof timeout);
    char command[COMMAND_SIZE]; size_t used=0;
    for (int i=0; i<argc; ++i) {
        size_t len=strlen(argv[i]);
        if (used+len+2>=sizeof command || strchr(argv[i],'\n') || strchr(argv[i],'\r')) { close(fd); return 2; }
        if (i) command[used++]=' ';
        memcpy(command+used,argv[i],len); used+=len;
    }
    command[used++]='\n';
    size_t sent=0;
    while (sent<used) {
        ssize_t n=send(fd,command+sent,used-sent,MSG_NOSIGNAL);
        if (n<=0) { close(fd); return 1; }
        sent+=(size_t)n;
    }
    char reply[262144]; used=0;
    while (used<sizeof reply-1) {
        ssize_t n=recv(fd,reply+used,sizeof reply-1-used,0);
        if (n<=0) break;
        used+=(size_t)n;
    }
    close(fd); reply[used]=0;
    if (!used) { fputs("No renderer response\n",stderr); return 1; }
    fputs(reply,stdout); return strncmp(reply,"{\"ok\":true",10)?1:0;
}

static void cleanup(struct app *a)
{
    for (unsigned i=0; i<CLIENTS; ++i) if (a->clients[i].fd>=0) close(a->clients[i].fd);
    if (a->server>=0) close(a->server);
    struct stat st;
    if (a->socket_ino && !lstat(a->socket_path,&st) && st.st_dev==a->socket_dev && st.st_ino==a->socket_ino)
        unlink(a->socket_path);
    if (a->frame) wl_callback_destroy(a->frame);
    while (a->buffers) destroy_buffer(a,a->buffers);
    if (a->keyboard) wl_keyboard_destroy(a->keyboard);
    if (a->seat) wl_seat_destroy(a->seat);
    if (a->toplevel) xdg_toplevel_destroy(a->toplevel);
    if (a->xdg) xdg_surface_destroy(a->xdg);
    if (a->surface) wl_surface_destroy(a->surface);
    if (a->wm) xdg_wm_base_destroy(a->wm);
    if (a->shm) wl_shm_destroy(a->shm);
    if (a->compositor) wl_compositor_destroy(a->compositor);
    if (a->registry) wl_registry_destroy(a->registry);
    if (a->display) wl_display_disconnect(a->display);
    model_free(&a->model);
}
static void usage(void)
{
    puts("letki-renderer [--boards N] [--manual] [--headless] [--socket PATH]\n"
         "letki-renderer [--socket PATH] ctl COMMAND [ARGS...]\n"
         "Commands: demo pong/text/pwm, pwm scene auto/silk/ripples/comets/lanterns/ladder/daisy, pwm brightness 0..100,\n"
         "uart COMMAND, status, boards N, run/stop, pause/resume, reset, step [N], advance MS,\n"
         "speed MS, link INDEX up/down, corrupt INDEX, mode simulation/external,\n"
         "receive INDEX PHASE, packet INDEX HEX8, frame INDEX HEX16, snapshot PATH, quit.\n"
         "Board indices are zero-based. Default socket: build/renderer/control.sock");
}
int main(int argc, char **argv)
{
    struct app a={.server=-1,.width=1100,.height=520,.dirty=true};
    for (unsigned i=0; i<CLIENTS; ++i) a.clients[i].fd=-1;
    strcpy(a.socket_path,"build/renderer/control.sock");
    unsigned boards=2; bool manual=false;
    for (int i=1; i<argc; ++i) {
        if (!strcmp(argv[i],"--help")) { usage(); return 0; }
        if (!strcmp(argv[i],"--headless")) a.headless=true;
        else if (!strcmp(argv[i],"--manual")) manual=true;
        else if (!strcmp(argv[i],"--boards") && i+1<argc) {
            char *end; unsigned long n=strtoul(argv[++i],&end,10);
            if (!*argv[i] || *end || !n || n>PONG_MAX_TILES) { usage(); return 2; }
            boards=(unsigned)n;
        } else if (!strcmp(argv[i],"--socket") && i+1<argc) {
            if (strlen(argv[++i])>=sizeof a.socket_path) return 2;
            strcpy(a.socket_path,argv[i]);
        } else if (!strcmp(argv[i],"ctl") && i+1<argc) return control(a.socket_path,argc-i-1,argv+i+1);
        else { usage(); return 2; }
    }
    signal(SIGINT,interrupt_handler); signal(SIGTERM,interrupt_handler);
    signal(SIGPIPE,SIG_IGN);
    if (!model_init(&a.model,boards)) return 1;
    a.model.running=!manual;
    if (!open_server(&a) || (!a.headless && !open_window(&a))) { cleanup(&a); return 1; }
    printf("READY %s %u boards %s\n",a.socket_path,boards,a.headless?"headless":"Wayland"); fflush(stdout);
    uint64_t last=monotonic_ms(), last_paint=last; int result=0;
    while (!a.quit && !interrupted) {
        if (!draw(&a)) { result=1; break; }
        short display_events=POLLIN;
        if (a.display) {
            while (wl_display_prepare_read(a.display)!=0)
                if (wl_display_dispatch_pending(a.display)<0) { result=1; goto finish; }
            if (wl_display_flush(a.display)<0) {
                if (errno==EAGAIN) display_events|=POLLOUT;
                else { wl_display_cancel_read(a.display); result=1; break; }
            }
        }
        struct pollfd fds[CLIENTS+2]={{.fd=a.display?wl_display_get_fd(a.display):-1,.events=display_events},
                                    {.fd=a.server,.events=POLLIN}};
        for (unsigned i=0; i<CLIENTS; ++i) fds[i+2]=(struct pollfd){.fd=a.clients[i].fd,.events=POLLIN};
        int ready=poll(fds,CLIENTS+2,16);
        if (a.display) {
            if (ready>0 && (fds[0].revents&POLLIN)) {
                if (wl_display_read_events(a.display)<0) { result=1; break; }
            } else wl_display_cancel_read(a.display);
            if (wl_display_dispatch_pending(a.display)<0 || (fds[0].revents&(POLLERR|POLLHUP))) { result=1; break; }
        }
        if (ready<0 && errno!=EINTR) { result=1; break; }
        uint64_t now=monotonic_ms();
        if (a.model.running) model_advance(&a.model,(unsigned)(now-last));
        last=now;
        if (a.model.running && now-last_paint>=50) { a.dirty=true; last_paint=now; }
        for (unsigned i=0; i<CLIENTS; ++i) if (a.clients[i].fd>=0) {
            if (fds[i+2].revents&(POLLIN|POLLHUP|POLLERR)) read_client(&a,&a.clients[i]);
            if (a.clients[i].fd>=0 && now-a.clients[i].started>2000) { close(a.clients[i].fd); a.clients[i].fd=-1; }
        }
        if (fds[1].revents&POLLIN) accept_clients(&a);
    }
finish:
    cleanup(&a); return result;
}
