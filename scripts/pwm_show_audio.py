#!/usr/bin/env python3
"""Original bell music/narration, sample-clock synchronized to the PC preview."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/pwm-show/audio'
CONFIG=ROOT/'config/pwm-show-audio.json'
os.environ.setdefault('HF_HOME',str(ROOT/'.tools/native-huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_XET','1')

def prepare():
    import numpy as np
    import onnxruntime as ort
    import soundfile as sf
    from supertonic import TTS
    ort.disable_telemetry_events()
    config=json.loads(CONFIG.read_text());OUT.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(CONFIG.read_bytes()+Path(__file__).read_bytes()).hexdigest()
    if (OUT/'score.json').exists() and (OUT/'score.wav').exists():
        old=json.loads((OUT/'score.json').read_text())
        if old.get('source_hash')==digest:return old
    tts=TTS(model='supertonic-3',model_dir=ROOT/'.tools/supertonic3',auto_download=False,intra_op_num_threads=4,inter_op_num_threads=1)
    voice=tts.get_voice_style(voice_name=config['voice']);rate=tts.sample_rate
    act=round(config['act_seconds']*rate);total=act*len(config['scenes'])
    music=np.zeros((total,2),dtype=np.float32);speech=np.zeros(total,dtype=np.float32)
    voice_windows=[];cues=[]
    for n,scene in enumerate(config['scenes']):
        np.random.seed(420+n)
        audio,_=tts.synthesize(scene['speech'],voice_style=voice,lang='en',total_steps=8,speed=config['native_speed'])
        audio=np.asarray(audio,dtype=np.float32).reshape(-1)
        audio*=.55/max(.00001,float(np.max(np.abs(audio))))
        start=n*act+round(config['voice_delay_seconds']*rate)
        assert len(audio)<act-round(.7*rate), 'Narration must fit; synthesize at a natural faster native rate'
        speech[start:start+len(audio)]+=audio
        sf.write(OUT/f'voice-{n+1}.wav',audio,rate)
        voice_windows.append((start,start+len(audio)))
        cues.append({'scene':scene['name'],'scene_sample':n*act,'voice_sample':start,'voice_end_sample':start+len(audio),'text':scene['speech']})
        print(f"Narration {n+1}/6: {scene['name']}, {len(audio)/rate:.2f}s",flush=True)
    # Original seven-note minor ostinato against six 6.4-second visual acts.
    # Additive detuned bell partials, a warm low pad, and left-to-right chimes.
    roots=[45,48,50,41,52,45]
    motif=[0,7,15,3,10,19,5]
    eighth=round(.2*rate)
    def bell(start,midi,gain,pan,seconds=1.8):
        count=min(round(seconds*rate),total-start)
        if count<=0:return
        t=np.arange(count,dtype=np.float32)/rate
        hz=440*2**((midi-69)/12)
        sound=np.zeros(count,dtype=np.float32)
        for partial,weight,decay in [(1,1,1.5),(2.01,.42,2.3),(2.76,.2,3.4),(3.92,.13,4.5),(5.43,.07,6)]:
            sound+=weight*np.sin(2*np.pi*hz*partial*t)*np.exp(-decay*t)
        sound*=gain*np.minimum(t/.006,1)
        music[start:start+count,0]+=sound*np.sqrt((1-pan)/2)
        music[start:start+count,1]+=sound*np.sqrt((1+pan)/2)
    for beat,start in enumerate(range(0,total,eighth)):
        scene=min(start//act,5);root=roots[scene]
        pan=.65*np.sin(2*np.pi*beat/21)
        bell(start,root+12+motif[beat%7],.065,pan)
        if beat%8==0:bell(start,root,.085,0,3.2)
        if scene==5 and beat%4==0:
            bell(start,root+24+(beat//4%5)*3,.10,-.8+1.6*((beat//4)%5)/4,2.1)
    for n,root in enumerate(roots):
        t=np.arange(act,dtype=np.float32)/rate
        env=np.sin(np.pi*np.arange(act,dtype=np.float32)/act)**2
        pad=np.zeros(act,dtype=np.float32)
        for semi in [0,3,7]:pad+=np.sin(2*np.pi*(440*2**((root-69+semi)/12))*t)
        music[n*act:(n+1)*act,:]+=(pad*env*.012)[:,None]
    # Smooth ducking leaves the narration clear without chopping the score.
    duck=np.ones(total,dtype=np.float32)
    ramp=round(.12*rate)
    for start,end in voice_windows:
        lo=max(0,start-ramp);hi=min(total,end+ramp)
        duck[lo:start]=np.minimum(duck[lo:start],np.linspace(1,.35,start-lo,dtype=np.float32))
        duck[start:end]=.35
        duck[end:hi]=np.minimum(duck[end:hi],np.linspace(.35,1,hi-end,dtype=np.float32))
    score=music*duck[:,None]+speech[:,None]
    fade=round(.15*rate)
    score[:fade]*=np.linspace(0,1,fade,dtype=np.float32)[:,None]
    score[-fade:]*=np.linspace(1,0,fade,dtype=np.float32)[:,None]
    peak=float(np.max(np.abs(score)));score*=config['master_gain']/max(1.,peak)
    sf.write(OUT/'score.wav',score,rate,subtype='PCM_16')
    report={'source_hash':digest,'sample_rate':rate,'samples':total,'seconds':total/rate,'act_samples':act,'cues':cues,'original_composition':True,'voice':'Local Supertonic M1','native_speed':config['native_speed'],'waveform_time_stretch':False,'peak':float(np.max(np.abs(score)))}
    (OUT/'score.json').write_text(json.dumps(report,indent=2)+'\n');return report

def play(loop=False):
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    from demo_pwm_show import control,start,configure
    import threading
    info=prepare();audio,rate=sf.read(OUT/'score.wav',dtype='float32',always_2d=True)
    path=ROOT/'build/pwm-show/control.sock';start(path);configure(path,'auto',100)
    control(path,'pwm audio on')
    state={'position':0,'paused':False,'warnings':[],'dac_start':None,'loop_start':0}
    started=threading.Event();done=threading.Event();checks=[]
    def callback(out,frames,clock,status):
        out.fill(0)
        if status:state['warnings'].append(str(status))
        if state['paused']:
            state['dac_start']=None
            return
        if state['dac_start'] is None:
            state['dac_start']=float(clock.outputBufferDacTime)
            state['loop_start']=state['position'];started.set()
        written=0
        while written<frames:
            index=state['position']%len(audio) if loop else state['position']
            count=min(frames-written,len(audio)-index)
            if count<=0:raise sd.CallbackStop
            out[written:written+count]=audio[index:index+count]
            state['position']+=count;written+=count
    try:
        with sd.OutputStream(samplerate=rate,channels=2,dtype='float32',blocksize=512,latency=.08,callback=callback,finished_callback=done.set) as stream:
            if not started.wait(5):raise RuntimeError('Audio did not start')
            while not done.is_set():
                # Drive visuals from DAC presentation time, not CPU submission
                # time. Pausing holds both tracks; no accumulated wall-clock drift.
                if state['dac_start'] is None:sample=state['position']
                else:sample=state['loop_start']+round(max(0,stream.time-state['dac_start'])*rate)
                sample=sample%len(audio) if loop else max(0,min(len(audio)-1,sample))
                result=control(path,'pwm seek '+str(sample*1000//rate))
                state['paused']=result['paused']
                if not checks or sample-checks[-1]['sample']>=rate:
                    checks.append({'sample':sample,'tick':result['pwm_tick'],'scene':result['pwm_scene']})
                time.sleep(.015)
    finally:
        try:
            control(path,'pwm audio off');control(path,'resume');control(path,'run')
        except (OSError,RuntimeError):pass
        (OUT/'playback.json').write_text(json.dumps({'checks':checks,'audio_warnings':state['warnings'],'synchronization':'PortAudio DAC sample presentation clock -> native renderer absolute PWM time','hardware_access':False},indent=2)+'\n')
    print('Synchronized sound and light playback finished.',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--loop',action='store_true')
    args=parser.parse_args()
    if args.prepare_only:print(json.dumps(prepare(),indent=2))
    else:play(args.loop)
if __name__=='__main__':main()
