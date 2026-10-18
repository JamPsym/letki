#!/usr/bin/env python3
"""Replace unused ADC-style button dividers with defined full-swing GPIO inputs."""
from pathlib import Path
import uuid
import math
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'hw/ledkiv4/ledkiv4.kicad_sch';s=read(p)
for series,cap,pulldown in [('R10','C2','R9'),('R13','C5','R14')]:
 r=next((n for n in children(s,'symbol') if prop(n,'Reference')[2]==series),None)
 if r is None:raise SystemExit('Button change already applied; refusing to modify it again')
 lib=next(n for n in children(child(s,'lib_symbols'),'symbol') if n[1]=='Device:R')
 pins={child(pin,'number')[1]:pin for unit in children(lib,'symbol') for pin in children(unit,'pin')}
 at=child(r,'at');angle=math.radians(float(at[3]));points=[]
 for number in ('1','2'):
  pos=child(pins[number],'at');x,y=float(pos[1]),float(pos[2]);points.append((round(float(at[1])+math.cos(angle)*x+math.sin(angle)*y,6),round(float(at[2])+math.sin(angle)*x-math.cos(angle)*y,6)))
 s.remove(r)
 s.append(['wire',['pts',*([['xy',str(x),str(y)] for x,y in points])],['stroke',['width','0'],['type','default']],['uuid',Q(str(uuid.uuid4()))]])
 c=next(n for n in children(s,'symbol') if prop(n,'Reference')[2]==cap);s.remove(c)
 pull=next(n for n in children(s,'symbol') if prop(n,'Reference')[2]==pulldown);prop(pull,'Value')[2]=Q('100k')
write(p,s)
print('Removed two series divider resistors and two button capacitors; presses now drive full VCC, idle is pulled low.')
