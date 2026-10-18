"""Audio-clock synchronization for a loaded general-firmware timeline."""
import json
from collections import deque
from pathlib import Path
import struct
import threading
import time
from general_link import Simulation, PLAY, PAUSE, ROOT
from general_program import compile_show


def play_audio(driver, show, audio_path, loop=False, storage='auto', replace='safe'):
    import sounddevice as sd
    import soundfile as sf
    audio,rate=sf.read(audio_path,dtype='float32',always_2d=True)
    driver.load(compile_show(show),storage,replace)
    def require_clock():
        stale=[i for i,c in driver.clocks.items() if c['clock_age_ms']>500]
        if stale:raise RuntimeError(f'Stale I2C clock on tiles {stale}; check SDA/SCL or use UART frame streaming')
    require_clock()
    silence=round(.5*rate)
    state={'position':0,'silence':silence,'dac':None,'warnings':deque(maxlen=128),'warning_count':0}
    ready=threading.Event();done=threading.Event();checks=deque(maxlen=1024);check_count=0
    def callback(out,frames,clock,status):
        out.fill(0)
        if status:
            state['warnings'].append(str(status));state['warning_count']+=1
        if state['dac'] is None:
            state['dac']=float(clock.outputBufferDacTime)+silence/rate;ready.set()
        offset=min(frames,state['silence']);state['silence']-=offset
        while offset<frames:
            index=state['position']%len(audio) if loop else state['position']
            count=min(frames-offset,len(audio)-index)
            if count<=0:raise sd.CallbackStop
            out[offset:offset+count]=audio[index:index+count]
            offset+=count;state['position']+=count
    simulation=isinstance(driver.link,Simulation)
    wall=time.monotonic();origin=driver.now()
    def service():
        if simulation:
            driver.link.now=origin+round((time.monotonic()-wall)*1000)
            driver.link.pixels()
    status='interrupted'
    try:
        with sd.OutputStream(samplerate=rate,channels=audio.shape[1],dtype='float32',blocksize=512,
                             latency=.15,callback=callback,finished_callback=done.set) as output:
            if not ready.wait(5):raise RuntimeError('Audio did not start')
            last_sync=-1e9
            print('Loaded timeline follows PC audio. Ctrl+C stops.',flush=True)
            while not done.is_set() or (not loop and output.time<state['dac']+len(audio)/rate):
                service();elapsed=output.time-state['dac']
                if elapsed-last_sync>=5:
                    driver.synchronize();service();require_clock()
                    epoch=driver.now()+round((state['dac']-output.time)*1000)
                    driver.batch([(i,PLAY,struct.pack('<IIB',driver.local_time(i,epoch),0,int(show.get('loop',True)))) for i in range(driver.tiles)])
                    checks.append(dict(audio_ms=round(elapsed*1000),epoch=epoch,
                                       clocks=driver.clocks.copy()))
                    check_count+=1
                    last_sync=elapsed
                time.sleep(.01)
            status='completed'
    finally:
        try:driver.all(PAUSE)
        finally:
            report=dict(status=status,audio_warnings=list(state['warnings']),audio_warning_count=state['warning_count'],
                        checks=list(checks),check_count=check_count,telemetry_limit=1024,
                        hardware_access=not simulation,synchronization='DAC presentation clock -> absolute loaded timeline epoch',
                        optical_timing_measured=False)
            out=ROOT/'build/general';out.mkdir(parents=True,exist_ok=True)
            (out/'audio.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
