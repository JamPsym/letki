"""Compile declarative text/bitmap tracks to the bounded LGS1 timeline."""
import json
from pathlib import Path
import struct
from general_link import library

DIGITS = {
 '0':[31,17,31],'1':[18,31,16],'2':[29,21,23],'3':[21,21,31],
 '4':[7,4,31],'5':[23,21,29],'6':[31,21,29],'7':[1,1,31],
 '8':[31,21,31],'9':[23,21,31],'.':[0,16,0],',':[0,24,0],
 '!':[0,23,0],'?':[1,21,3],'-':[4,4,4],':':[0,10,0],
 '+':[4,14,4],'/':[16,14,1],"'": [0,3,0],
}

def text_bitmap(text):
    lib = library(); columns=[]
    for ch in text.upper():
        if ch == ' ': columns.extend((0,0)); continue
        glyph=[v<<1 for v in DIGITS[ch]] if ch in DIGITS else [lib.font_compact_column(ord(ch), x) for x in range(3)]
        if not any(glyph): raise ValueError(f'No built-in glyph for {ch!r}; supply a bitmap font/image')
        columns.extend(glyph+[0])
    if not columns: raise ValueError('Text cannot be empty')
    width=len(columns); data=bytearray((width*8+7)//8)
    for x,column in enumerate(columns):
        for y in range(8):
            if column&(1<<y): data[(y*width+x)//8] |= 1<<((y*width+x)%8)
    return width,8,bytes(data)

def bitmap(value):
    rows=value
    if not rows or not rows[0] or any(len(row)!=len(rows[0]) for row in rows): raise ValueError('Bitmap rows must have equal positive width')
    height=len(rows);width=len(rows[0]);flat=[v for row in rows for v in row]
    if any(not isinstance(v,int) or not 0<=v<=100 for v in flat): raise ValueError('Bitmap levels must be integers 0..100')
    return width,height,bytes(flat)

def compile_show(show):
    if isinstance(show,(str,Path)): show=json.loads(Path(show).read_text())
    if show.get('version',1)!=1: raise ValueError('Unsupported show version')
    duration=show['duration_ms'];tracks=show.get('tracks',[])
    if not isinstance(duration,int) or not 0<duration<=0x7fffffff or len(tracks)>16: raise ValueError('Invalid duration or more than 16 tracks')
    records=[];assets=bytearray();dedup={}
    asset_start=16+32*len(tracks)
    for track in tracks:
        kind=track.get('type','text');op=1 if kind=='fill' else 2
        start=track.get('start_ms',0);length=track.get('duration_ms',duration-start)
        flags={'hold':0,'linear':1,'triangle':2}[track.get('motion','hold')]
        if track.get('repeat_x'): flags|=4
        period=track.get('period_ms',length if flags&3 else 0)
        if not 0<=start<duration or not 0<length<=duration-start or not 0<=period<=60000 or (flags&3 and not period): raise ValueError('Invalid track timing; motion periods must fit 1..60000 ms')
        x,y=track.get('from',[0,0]);x1,y1=track.get('to',[x,y])
        levels=track.get('levels',[100,100]);level,level1=levels
        if any(not isinstance(v,int) or not 0<=v<=100 for v in levels): raise ValueError('Levels must be 0..100')
        width=height=offset=fmt=0
        if kind=='text': width,height,data=text_bitmap(track['text'])
        elif kind=='bitmap': width,height,data=bitmap(track['pixels']);fmt=2
        elif kind=='fill': data=b''
        else: raise ValueError('Unknown track type')
        if data:
            if data not in dedup: dedup[data]=asset_start+len(assets);assets.extend(data)
            offset=dedup[data]
        if width>4096 or height>255: raise ValueError('Asset dimensions exceed firmware limits')
        records.append(struct.pack('<BBBBIIIHHBBhhhhBB',op,fmt,flags,0,start,length,period,offset,width,height,0,x,y,x1,y1,level,level1))
    size=asset_start+len(assets)
    if size>65535: raise ValueError('Show object exceeds address range')
    return struct.pack('<4sHBBII',b'LGS1',size,len(tracks),int(show.get('loop',True)),duration,0)+b''.join(records)+assets

def text_show(text,mode='scroll',speed=75,brightness=100):
    width,_,_=text_bitmap(text)
    if not 10<=speed<=500 or not 0<=brightness<=100:raise ValueError('Speed must be 10..500, brightness 0..100')
    if mode=='scroll':
        duration=(width+40)*speed;start=[40,0];end=[-width,0];motion='linear'
    elif mode=='bounce':
        duration=max(1000,2*abs(width-40)*speed);start=[max(0,(40-width)//2),0];end=[min(0,40-width),0];motion='triangle'
    elif mode=='fall':
        duration=16*speed;start=[max(0,(40-width)//2),-8];end=[start[0],8];motion='linear'
    else:raise ValueError('Unknown text mode')
    if duration>60000:raise ValueError('Text motion exceeds 60 seconds; split the text into segments or reduce speed')
    return dict(version=1,duration_ms=duration,loop=True,tracks=[dict(type='text',text=text,motion=motion,period_ms=duration,**{'from':start,'to':end},levels=[brightness,brightness])])


def pwm_pixels(milliseconds):
    import ctypes
    lib=library()
    lib.pwm_show_tile.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint,ctypes.c_uint,ctypes.c_int]
    tiles=[]
    for tile in range(5):
        frame=(ctypes.c_uint8*64)()
        lib.pwm_show_tile(frame,(milliseconds//40)%960,tile,5,-1)
        tiles.append(bytes(frame))
    return tiles
