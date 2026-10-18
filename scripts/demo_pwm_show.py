#!/usr/bin/env python3
"""Open or record the native five-tile PWM light show; no hardware access."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
BIN=ROOT/'build/renderer/letki-renderer'
OUT=ROOT/'build/pwm-show'
SCENES=('auto','silk','ripples','comets','lanterns','ladder','daisy')

def control(path,command):
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(str(path))
        client.sendall((command+'\n').encode())
        data=bytearray()
        while part:=client.recv(65536): data.extend(part)
    state=json.loads(data)
    if not state['ok']: raise RuntimeError(command+': '+str(state))
    return state

def start(path,headless=False):
    if path.exists():
        control(path,'status')
        if headless: raise RuntimeError('Recorder socket is already in use')
        return None
    with (OUT/('record.log' if headless else 'window.log')).open('ab',buffering=0) as log:
        process=subprocess.Popen([str(BIN),'--boards','5','--manual','--socket',str(path),*(['--headless'] if headless else [])],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    end=time.monotonic()+5
    while not path.exists():
        if process.poll() is not None or time.monotonic()>end:
            process.terminate();process.wait(timeout=3)
            raise RuntimeError('Renderer did not start; inspect build/pwm-show logs')
        time.sleep(.01)
    return process

def configure(path,scene,brightness):
    for command in ('stop','boards 5','demo pwm','pwm scene '+scene,'pwm brightness '+str(brightness)):
        control(path,command)

def record(brightness):
    from PIL import Image
    path=OUT/'record.sock';process=start(path,True)
    frames=[];states=[];stills=[]
    try:
        configure(path,'auto',brightness)
        # One 38.4-second sequence, sampled at 12.5 fps; native window runs 25 fps.
        for n in range(480):
            state=control(path,'status');states.append(state)
            png=OUT/'record-frame.png';control(path,'snapshot '+str(png))
            with Image.open(png) as im:
                im.thumbnail((900,500));frames.append(im.convert('P',palette=Image.Palette.ADAPTIVE))
            if n in (20,100,180,260,340,420):
                still=OUT/(state['pwm_scene'].lower().replace(' ','-')+'.png')
                with Image.open(png) as im: im.save(still);stills.append(im.copy())
            control(path,'step 2')
        frames[0].save(OUT/'pwm-show.gif',save_all=True,append_images=frames[1:],duration=80,loop=0,disposal=2)
        sheet=Image.new('RGB',(1100,6*520))
        for n,im in enumerate(stills):sheet.paste(im,(0,n*520))
        sheet.save(OUT/'scene-sheet.png')
        (OUT/'recording.json').write_text(json.dumps({'frames':480,'duration_seconds':38.4,'brightness':brightness,'states':states},indent=2)+'\n')
        print('Recorded build/pwm-show/pwm-show.gif and scene-sheet.png')
    finally:
        if process: process.terminate();process.wait(timeout=3)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',choices=SCENES,default='auto')
    parser.add_argument('--brightness',type=int,default=100,choices=range(101))
    parser.add_argument('--record',action='store_true',help='Record independently without changing the open window')
    args=parser.parse_args()
    if not BIN.exists():raise SystemExit('Run make renderer first')
    OUT.mkdir(parents=True,exist_ok=True)
    if args.record:record(args.brightness);return
    path=OUT/'control.sock';start(path);configure(path,args.scene,args.brightness);control(path,'run')
    print('Five-tile PWM show running. Space pause; N next; A auto; +/- brightness; Q close.')

if __name__=='__main__':main()
