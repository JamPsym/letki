#!/usr/bin/env python3
"""Local song/speech transcription, timestamp search, audition clips and Letki cues.

Playback stays native C++. This optional offline authoring tool reuses the CPU
Whisper environment; it does not install packages or alter the ROCm environment.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='letki-transcript-v1'

def read_json(path):
    return json.loads(Path(path).read_text())

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def timestamp(seconds):
    n=round(seconds*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,n=divmod(n,1000)
    return f'{h:02}:{m:02}:{s:02},{n:03}'

def normalize(text):
    return re.sub(r'[^\w]+',' ',text.casefold()).strip()

def checked_segment(segment,offset,chunk_end):
    words=[]
    for w in segment.get('words',[]):
        start=max(offset,float(w['start'])+offset);end=min(chunk_end,float(w['end'])+offset)
        p=float(w.get('probability',0))
        if not all(map(math.isfinite,(start,end,p))) or end<=start:continue
        words.append(dict(word=str(w['word']).strip(),start=round(start,3),end=round(end,3),probability=round(p,4)))
    start=max(offset,float(segment['start'])+offset);end=min(chunk_end,float(segment['end'])+offset)
    flags=[]
    if segment.get('no_speech_prob',1)>.5:flags.append('possible_music_or_silence')
    if segment.get('avg_logprob',-10)<-.8:flags.append('low_segment_confidence')
    if not words or sum(w['probability'] for w in words)/len(words)<.6:flags.append('low_word_confidence')
    if any(w['end']-w['start']>2 for w in words):flags.append('suspicious_word_duration')
    return dict(start=round(start,3),end=round(end,3),text=str(segment['text']).strip(),
                avg_logprob=segment.get('avg_logprob'),no_speech_prob=segment.get('no_speech_prob'),
                words=words,flags=flags,reviewed=False)

def transcribe(args):
    import numpy as np
    import torch
    import whisper
    source=Path(args.audio).resolve();sha=digest(source)
    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(source)],text=True).strip())
    end=min(duration,args.end if args.end is not None else duration)
    if not 0<=args.start<end or not 15<=args.chunk<=120 or not 1<=args.threads<=8:raise ValueError('Invalid range, chunk (15..120s) or thread count (1..8)')
    model_path=ROOT/'.tools/whisper'/f'{args.model}.pt'
    if not model_path.exists():raise RuntimeError(f'Model not cached: {model_path}; choose base or prepare the desired Whisper model separately')
    settings=dict(model=args.model,language=args.language,start=args.start,end=end,chunk=args.chunk)
    report=dict(schema=SCHEMA,audio=str(source),sha256=sha,duration=duration,settings=settings,
                timing='absolute seconds within this exact recording; intro excluded',segments=[],completed_until=args.start)
    if args.output.exists():
        old=read_json(args.output)
        if old.get('sha256')!=sha or old.get('settings')!=settings:raise ValueError('Output belongs to another source/settings; choose another output path')
        report=old
    torch.set_num_threads(args.threads)
    model=whisper.load_model(str(model_path),device='cpu')
    at=report['completed_until']
    while at<end:
        stop=min(end,at+args.chunk)
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(source),'-t',str(stop-at),'-vn','-ac','1','-ar','16000','-f','f32le','pipe:1'])
        audio=np.frombuffer(raw,dtype='<f4').copy()
        result=model.transcribe(audio,language=args.language,word_timestamps=True,fp16=False,verbose=None,
                condition_on_previous_text=False,temperature=0,beam_size=5,hallucination_silence_threshold=2)
        for segment in result['segments']:
            s=checked_segment(segment,at,stop)
            if s['end']<=s['start'] or not s['text']:continue
            # Two-second overlap: discard duplicate recognitions of the same
            # phrase at nearly the same source time, keeping the first record.
            if any(normalize(p['text'])==normalize(s['text']) and abs(p['start']-s['start'])<3 for p in report['segments'][-6:]):continue
            s['id']=len(report['segments']);report['segments'].append(s)
        report['completed_until']=stop;report['complete']=stop>=end;save(args.output,report)
        print(f'{stop:.1f}/{end:.1f}s: {len(report["segments"])} candidate segments',flush=True)
        if stop>=end:break
        at=stop-2
    export(report,args.output.with_suffix('.srt'),args.output.with_suffix('.csv'))

def export(report,srt,csv_path):
    lines=[]
    for i,s in enumerate(report['segments'],1):lines.extend([str(i),f'{timestamp(s["start"])} --> {timestamp(s["end"])}',s['text'],''])
    Path(srt).write_text('\n'.join(lines))
    with Path(csv_path).open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['segment','start','end','text','probability','flags','reviewed'])
        for s in report['segments']:
            for word in s.get('words',[]):w.writerow([s['id'],word['start'],word['end'],word['word'],word['probability'],';'.join(s['flags']),s.get('reviewed',False)])

def search(args):
    report=read_json(args.transcript);pattern=re.compile(args.pattern,re.I)
    for s in report['segments']:
        if pattern.search(s['text']):print(f'{s["id"]:4}  {s["start"]:9.3f}..{s["end"]:9.3f}  {s["text"]}  [{", ".join(s["flags"]) or "candidate"}]')

def clean_text(text):
    # Compact firmware font supports uppercase Latin/Polish letters and spaces.
    text=text.upper();out=[]
    for c in text:
        if 'A'<=c<='Z' or c in 'ĄĆĘŁŃÓŚŹŻ':out.append(c)
        elif c.isspace() or unicodedata.category(c).startswith('P'):out.append(' ')
    return ' '.join(''.join(out).split())

def width(text):
    return sum(2 if c==' ' else 3 for c in text)

def cue_groups(words,max_width=40):
    groups=[];group=[]
    for w in words:
        text=clean_text(w['word'])
        if not text:continue
        item=dict(w,word=text)
        if group and (width(' '.join(x['word'] for x in group+[item]))>max_width or item['start']-group[-1]['end']>1.2):groups.append(group);group=[]
        group.append(item)
    if group:groups.append(group)
    return groups

def cues(args):
    report=read_json(args.transcript);show=read_json(args.show);out=Path(args.output).resolve()
    if report.get('schema')!=SCHEMA:raise ValueError('Unsupported transcript schema')
    if not all(math.isfinite(v) for v in (args.min_probability,args.lead,args.tail,args.hold)) or not 0<=args.min_probability<=1 or min(args.lead,args.tail,args.hold)<0:raise ValueError('Invalid cue probability or timing')
    # Preserve paths when writing a derived show outside config/player/.
    for key in ('audio','video'):
        if show.get(key):show[key]=str((Path(args.show).resolve().parent/show[key]).resolve())
    if show.get('audio') and digest(show['audio'])!=report['sha256']:raise ValueError('Transcript and show use different audio recordings')
    selected=set(args.segment or []);added=[]
    if selected-set(s['id'] for s in report['segments']):raise ValueError('Unknown segment ID')
    for s in report['segments']:
        if selected and s['id'] not in selected:continue
        if args.reviewed_only and not s.get('reviewed'):continue
        if not selected and s['flags'] and not s.get('reviewed'):continue
        words=[w for w in s.get('words',[]) if w.get('probability',0)>=args.min_probability or s.get('reviewed')]
        if args.phrases:
            groups=[[dict(word=clean_text(s['text']),start=s['start'],end=s['end'])]]
        else:groups=cue_groups(words)
        for group in groups:
            text=' '.join(w['word'] for w in group);start=max(0,group[0]['start']-args.lead)
            duration=max(args.hold,group[-1]['end']-start+args.tail)
            added.append(dict(at=round(start,3),duration=round(duration,3),text=text,
                              mode='center' if width(text)<=40 else 'scroll'))
    show['cues']=sorted(show.get('cues',[])+added,key=lambda c:c['at'])
    show['transcript_source']=dict(path=str(Path(args.transcript).resolve()),sha256=report['sha256'],
        draft=not args.reviewed_only,recognized_text_requires_review=True)
    save(out,show);print(f'{len(added)} cues -> {out}')

def clip(args):
    report=read_json(args.transcript);s=next(s for s in report['segments'] if s['id']==args.segment)
    start=max(0,s['start']-args.padding);end=min(report['duration'],s['end']+args.padding)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(start),'-i',report['audio'],'-t',str(end-start),'-vn','-c:a','pcm_s16le',str(args.output)],check=True)
    print(f'{start:.3f}..{end:.3f}s: {s["text"]} -> {args.output}')

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('transcribe');a.add_argument('audio',type=Path);a.add_argument('--output',type=Path,required=True);a.add_argument('--language',default='en');a.add_argument('--model',default='base');a.add_argument('--start',type=float,default=0);a.add_argument('--end',type=float);a.add_argument('--chunk',type=float,default=60);a.add_argument('--threads',type=int,default=2);a.set_defaults(fn=transcribe)
    a=sub.add_parser('search');a.add_argument('transcript',type=Path);a.add_argument('pattern');a.set_defaults(fn=search)
    a=sub.add_parser('cues');a.add_argument('transcript',type=Path);a.add_argument('--show',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--segment',type=int,action='append');a.add_argument('--reviewed-only',action='store_true');a.add_argument('--min-probability',type=float,default=.6);a.add_argument('--phrases',action='store_true');a.add_argument('--lead',type=float,default=.1);a.add_argument('--tail',type=float,default=.5);a.add_argument('--hold',type=float,default=1.2);a.set_defaults(fn=cues)
    a=sub.add_parser('clip');a.add_argument('transcript',type=Path);a.add_argument('segment',type=int);a.add_argument('--padding',type=float,default=1);a.add_argument('--output',type=Path,required=True);a.set_defaults(fn=clip)
    args=p.parse_args()
    try:args.fn(args)
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as e:p.exit(1,f'player_words: {e}\n')
if __name__=='__main__':main()
