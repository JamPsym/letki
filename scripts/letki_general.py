#!/usr/bin/env python3
"""General Letki driver: inspect, load, standalone play, preview and streaming."""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import struct
import statistics
import time
from general_link import Driver, Simulation, Serial, ROOT, PAUSE, QUEUE, FLUSH, BRIGHTNESS
from general_program import compile_show, text_show, pwm_pixels

OUT=ROOT/'build/general'

def preview(path, output=None, fps=25):
    if not 1<=fps<=50:raise ValueError('FPS must be 1..50')
    from PIL import Image, ImageDraw
    show=json.loads(Path(path).read_text());sim=None;program=b''
    if show.get('source')=='pwm-show':allocation=dict(storage='PC-stream',source='original C PWM core')
    else:
        program=compile_show(show);sim=Simulation();driver=Driver(sim)
        allocation=driver.load(program);driver.play(lead=0)
    frames=[];hashes=[];samples=[];duration=show['duration_ms']
    if duration*fps//1000>3000: raise ValueError('Preview export is limited to 3000 frames; split long shows or use streaming')
    for now in range(0,duration,max(1,1000//fps)):
        if sim is None:tiles=pwm_pixels(now)
        else:sim.now=now;tiles=sim.pixels()
        hashes.append(hashlib.sha256(b''.join(tiles)).hexdigest())
        image=Image.new('RGB',(840,240),(12,17,24));draw=ImageDraw.Draw(image)
        draw.text((20,12),f'LETKI  |  general firmware simulation  |  {now/1000:.2f}s',fill=(220,228,240))
        for tile,pixels in enumerate(tiles):
            for y in range(8):
                for x in range(8):
                    v=pixels[y*8+x]/100
                    color=(int(24+231*v),int(20+115*v),int(16+20*v))
                    px=20+(tile*8+x)*20;py=45+y*20
                    draw.ellipse((px+2,py+2,px+17,py+17),fill=color)
        frames.append(image)
        if now in (1000,5000,9000): samples.append(image.copy())
    output=Path(output or OUT/'preview.gif');output.parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(output,save_all=True,append_images=frames[1:],duration=1000//fps,loop=0)
    if samples:
        sheet=Image.new('RGB',(840,240*len(samples)))
        for i,im in enumerate(samples):sheet.paste(im,(0,i*240))
        sheet.save(output.with_suffix('.png'))
    report=dict(allocation=allocation,frames=len(frames),seconds=duration/1000,pixel_hashes=hashes)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Preview: {output} ({len(program)} loaded bytes per tile; {allocation.get("source","shared MCU interpreter")})')
    return report

def render_at(sim, now):
    sim.now=now
    return sim.pixels()

def stream(driver, show, seconds=None, fps='auto', fmt='gray4', audio=None, loop=False):
    """Bounded future frames; old independent frames are skipped, never queued late."""
    if fps!='auto':
        fps=int(fps)
        if not 1<=fps<=50:raise ValueError('FPS must be 1..50')
    source=None
    if show.get('source')!='pwm-show':
        source=Simulation();source.set_source(compile_show(show))
    # Flash programs consume no arena space and can remain active underneath
    # raw frames. Only RAM programs need replacing to maximize queue space.
    idle=compile_show(dict(duration_ms=1,tracks=[]))
    driver.all(PAUSE);driver.all(FLUSH)
    infos=[driver.info(i) for i in range(driver.tiles)]
    retained=all(i['storage'] in (1,2) and i['program_bytes'] for i in infos)
    if not retained:driver.load(idle,storage='ram',replace='capacity')
    kind={'mono1':0,'gray4':1,'level8':2}[fmt]
    stride=(24,48,80)[kind]
    slots=min(16,min((i['arena_total']-(0 if retained else len(idle)))//stride for i in infos))
    driver.all(QUEUE,bytes([slots,kind]))
    if fps=='auto':
        costs=[]
        for _ in range(3):
            start=driver.now();driver.frame([bytes(64)]*driver.tiles,start+2000,fmt)
            costs.append(driver.now()-start);driver.all(FLUSH)
        fps=min(25,max(1,int(800/max(1,statistics.median(costs)))))
        print(f'Automatic streaming rate: {fps} fps ({fmt}); based on acknowledged uploads.',flush=True)
    duration=seconds or show['duration_ms']/1000
    output=None;state={'warnings':deque(maxlen=128),'warning_count':0};checks=deque(maxlen=4096);status='interrupted'
    totals=dict(frames=0,late=0,upload_ms=0,max_upload_ms=0)
    if audio:
        import sounddevice as sd
        import soundfile as sf
        import threading
        data,rate=sf.read(audio,dtype='float32',always_2d=True)
        silence=round(.5*rate)
        state.update(position=0,dac=None,silence=silence)
        ready=threading.Event();finished=threading.Event()
        def callback(out,frames,clock,warning):
            out.fill(0)
            if warning:
                state['warnings'].append(str(warning));state['warning_count']+=1
            if state['dac'] is None:
                state['dac']=float(clock.outputBufferDacTime)+silence/rate;ready.set()
            written=min(frames,state['silence']);state['silence']-=written
            while written<frames:
                index=state['position']%len(data) if loop else state['position']
                count=min(frames-written,len(data)-index)
                if count<=0:raise sd.CallbackStop
                out[written:written+count]=data[index:index+count]
                state['position']+=count;written+=count
        output=sd.OutputStream(samplerate=rate,channels=data.shape[1],dtype='float32',blocksize=512,
                               latency=.15,callback=callback,finished_callback=finished.set)
        duration=len(data)/rate
    simulation=isinstance(driver.link,Simulation)
    wall=time.monotonic();origin=driver.now()
    def service():
        if simulation:
            driver.link.now=origin+round((time.monotonic()-wall)*1000)
            driver.link.pixels()
    lead=round((slots-1)*1000/fps)-10;clock_reanchors=0;reanchor=False
    start_host=driver.now()+500;next_frame=0;skipped=0;last_sync=driver.now()
    try:
        if output:
            output.start()
            if not ready.wait(5):raise RuntimeError('Audio did not start')
            service();start_host=driver.now()+round((state['dac']-output.time)*1000)
        while True:
            service()
            if driver.now()-last_sync>=1000:
                jumped=driver.synchronize(timeout=.1,require_fresh=False,flush_on_jump=True)
                if jumped:clock_reanchors+=1;reanchor=True
                service();last_sync=driver.now()
                if output:start_host=driver.now()+round((state['dac']-output.time)*1000)
            elapsed=(output.time-state['dac'])*1000 if output else driver.now()-start_host
            if not loop and elapsed>=duration*1000:break
            if reanchor:
                future=max(0,int((elapsed+max(100,2000/fps))*fps/1000)+1)
                skipped+=max(0,future-next_frame);next_frame=future;reanchor=False
            current=max(0,int(elapsed*fps//1000))
            if next_frame<current:
                skipped+=current-next_frame;next_frame=current
            horizon=max(0,int((elapsed+lead)*fps//1000))
            if next_frame>horizon:
                time.sleep(.002);continue
            when=start_host+round(next_frame*1000/fps)
            before=driver.now()
            position=round(next_frame*1000/fps)%show['duration_ms']
            pixels=pwm_pixels(position) if source is None else render_at(source,position)
            try:driver.frame(pixels,when,fmt)
            except Exception as error:
                from general_link import ProtocolError
                if isinstance(error,ProtocolError) and error.status==2:
                    time.sleep(.003);continue
                raise
            after=driver.now();checks.append(dict(frame=next_frame,deadline=when,upload_ms=after-before,late=after>when))
            totals['frames']+=1;totals['late']+=int(after>when)
            totals['upload_ms']+=after-before;totals['max_upload_ms']=max(totals['max_upload_ms'],after-before)
            next_frame+=1
        status='completed'
    finally:
        if output:output.stop();output.close()
        if source is not None:source.close()
        try:driver.all(FLUSH)
        finally:
            report=dict(status=status,frames=list(checks),frame_count=totals['frames'],telemetry_limit=4096,skipped_frames=skipped,clock_reanchors=clock_reanchors,persistent_program_retained=bool(retained),
                        late_uploads=totals['late'],mean_upload_ms=totals['upload_ms']/max(1,totals['frames']),
                        max_upload_ms=totals['max_upload_ms'],audio_warnings=list(state['warnings']),audio_warning_count=state['warning_count'],format=fmt,fps=fps,
                        hardware_access=not simulation,physical_timing_measured=False)
            OUT.mkdir(parents=True,exist_ok=True);(OUT/'stream.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port');parser.add_argument('--simulate',action='store_true')
    parser.add_argument('--baud',type=int,choices=(115200,230400,460800,921600),default=115200)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('inspect')
    p=sub.add_parser('preview');p.add_argument('show');p.add_argument('--output');p.add_argument('--fps',type=int,default=25)
    p=sub.add_parser('load');p.add_argument('show');p.add_argument('--storage',choices=('auto','ram','flash'),default='auto');p.add_argument('--replace',choices=('safe','capacity'),default='safe');p.add_argument('--play',action='store_true')
    p=sub.add_parser('text');p.add_argument('text');p.add_argument('--mode',choices=('scroll','bounce','fall'),default='scroll');p.add_argument('--speed',type=int,default=75);p.add_argument('--brightness',type=int,default=100)
    p=sub.add_parser('audio');p.add_argument('show');p.add_argument('audio');p.add_argument('--loop',action='store_true');p.add_argument('--storage',choices=('auto','ram','flash'),default='auto');p.add_argument('--replace',choices=('safe','capacity'),default='safe')
    p=sub.add_parser('play');p.add_argument('--position',type=int,default=0);p.add_argument('--once',action='store_true')
    sub.add_parser('pause')
    p=sub.add_parser('seek');p.add_argument('milliseconds',type=int)
    p=sub.add_parser('stream');p.add_argument('show');p.add_argument('--fps',default='auto');p.add_argument('--format',choices=('mono1','gray4','level8'),default='gray4');p.add_argument('--audio');p.add_argument('--loop',action='store_true')
    args=parser.parse_args()
    if args.command=='preview':preview(args.show,args.output,args.fps);return
    link=Simulation() if args.simulate else Serial(args.port)
    driver=None
    try:
        driver=Driver(link)
        if args.baud!=115200:driver.set_baud(args.baud)
        if args.command=='inspect':
            nodes=[dict(driver.info(i),uid=driver.capabilities[i]['uid']) for i in range(5)]
            print(json.dumps(dict(nodes=nodes,clocks=driver.clocks),indent=2))
        elif args.command=='load':
            print(json.dumps(driver.load(compile_show(args.show),args.storage,args.replace),indent=2))
            if args.play:driver.play()
        elif args.command=='play':driver.play(args.position,False if args.once else None)
        elif args.command=='text':
            show=text_show(args.text,args.mode,args.speed,args.brightness)
            driver.load(compile_show(show));driver.play()
        elif args.command=='audio':
            from general_audio import play_audio
            play_audio(driver,json.loads(Path(args.show).read_text()),args.audio,args.loop,args.storage,args.replace)
        elif args.command=='pause':driver.all(PAUSE)
        elif args.command=='seek':driver.seek(args.milliseconds)
        elif args.command=='stream':stream(driver,json.loads(Path(args.show).read_text()),fps=args.fps,fmt=args.format,audio=args.audio,loop=args.loop)
    finally:
        if driver is not None:driver.close()
        else:link.close()

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nStopped; last complete frame held.')
    except (ValueError,RuntimeError,TimeoutError,OSError) as error:raise SystemExit(str(error))
