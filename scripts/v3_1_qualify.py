#!/usr/bin/env python3
"""Prepare/exercise v3.1 pulse-tile patterns. No port means offline plan only.

Does not flash, set option bytes, switch programmer power or establish analog
qualification. A live --port is an explicit operator-controlled hardware action.
"""
import argparse
import json
from pathlib import Path
import time

PROFILE='FW LETKI_V3_1_PULSE expects=33R/3V3'


def patterns(name):
    if name=='off':return [('off',bytes(8))]
    if name=='single':return [('top-left',bytes([1,0,0,0,0,0,0,0]))]
    if name=='all':return [('all-on',bytes([255]*8))]
    if name=='rows':return [(f'row-{r+1}-from-top',bytes([1<<r]*8)) for r in range(8)]
    if name=='columns':return [(f'column-{c+1}-from-left',bytes(255 if i==c else 0 for i in range(8))) for c in range(8)]
    if name=='walk':return [(f'pixel-{c+1}-{r+1}',bytes((1<<r) if i==c else 0 for i in range(8))) for r in range(8) for c in range(8)]
    raise ValueError(name)


def counters(line):
    values=dict(token.split('=',1) for token in line.split())
    return {key:int(values[key]) for key in ['uart_errors','tx_dropped']}


def exercise(link,frames,brightness,hold,sleep=time.sleep):
    verified=False
    try:
        reply=link.wait(link.send('hw'),PROFILE,3)
        if reply!=PROFILE:raise RuntimeError('Wrong firmware profile; no display command sent')
        verified=True
        link.set_brightness(0)
        link.set_frame(bytes(8))
        before=counters(link.wait(link.send('status'),'speed_ms=',3))
        link.set_brightness(brightness)
        for name,frame in frames:
            link.set_frame(frame)
            print(name,frame.hex(),flush=True)
            sleep(hold)
        after=counters(link.wait(link.send('status'),'speed_ms=',3))
        if after!=before:raise RuntimeError(f'UART diagnostics changed: {before} -> {after}')
        return {'profile':reply,'patterns_exercised':len(frames),'brightness_pct':brightness,
                'UART_before':before,'UART_after':after,
                'scope':'Acknowledged pattern delivery only; current, pulse width/duty, temperature and optical results require external measurements'}
    finally:
        if verified:
            # A failed connection may prevent this request; propagate the
            # error rather than claiming that the physical board is blank.
            link.set_brightness(0)
            link.set_frame(bytes(8))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',help='Explicit live UART port; omit for a safe offline pattern plan')
    parser.add_argument('--pattern',choices=['off','single','rows','columns','walk','all'],default='single')
    parser.add_argument('--brightness',type=int,default=25)
    parser.add_argument('--hold-ms',type=int,default=500)
    parser.add_argument('--output',type=Path,default=Path('build/v3_1-qualification'))
    args=parser.parse_args()
    if not 0<=args.brightness<=100:parser.error('brightness must be 0..100')
    if not 20<=args.hold_ms<=60000:parser.error('hold-ms must be 20..60000')
    frames=patterns(args.pattern)
    if not args.port:
        print(json.dumps({'mode':'OFFLINE; no device opened','required_profile':PROFILE,
            'brightness_pct':args.brightness,'hold_ms':args.hold_ms,
            'frames':[{'name':name,'hex':frame.hex()} for name,frame in frames]},indent=2))
        return
    from uart_link import UartLink
    args.output.mkdir(parents=True,exist_ok=True)
    with UartLink(args.port,args.output/'uart.log') as link:
        report=exercise(link,frames,args.brightness,args.hold_ms/1000)
    report['final_display']='Acknowledged blank frame at brightness 0'
    (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
