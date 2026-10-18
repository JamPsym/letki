#!/usr/bin/env python3
"""Create an isolated pulsed-current schematic from Study B2; never overwrite."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v3_1_transistor_study import field, label, uid

ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'hw/ledkiv3.1/tme-study'
dest=ROOT/'hw/ledkiv3.1/pulse-study'
assert not dest.exists(), 'Edit the existing study; do not replay this creator.'
dest.mkdir()
for name in ['LetkiStudy.kicad_sym','sym-lib-table','fp-lib-table']:
    shutil.copy2(src/name,dest/name)
shutil.copytree(src/'LetkiStudy.pretty',dest/'LetkiStudy.pretty')
s=read(src/'ledkiv3_1_tme.kicad_sch')
root_id=child(s,'uuid')[1]
project='ledkiv3_1_pulse'
parts={str(prop(x,'Reference')[2]):x for x in children(s,'symbol')}
def update(inst,k,v):
    node=prop(inst,k)
    if node:node[2]=Q(v)
    else:inst.append(field(k,v))
for i in range(1,9):
    r=parts[f'R{i}']
    for k,v in [('Value','68 1%'),('MPN','0805W8F680JT5E'),('Supplier','LCSC'),('Supplier code','C17802'),('Sourcing','USER_STOCK; two in parallel per row')]:
        update(r,k,v)
    at=child(r,'at'); x,y=map(float,at[1:3])
    s.append(label(f'L{i}',x,round(y-3.81,6)))
    # Second 68R is drawn in a labelled bank on the unused right of the sheet.
    extra=deepcopy(r); ref=f'R{57+i}';ex,ey=355.6+25.4*(i-1),101.6
    child(extra,'at')[1:]=[str(ex),str(ey),'0']
    child(extra,'uuid')[1]=uid()
    update(extra,'Reference',ref)
    for name,dy in [('Reference',-1.27),('Value',1.27)]:
        child(prop(extra,name),'at')[1:]=[str(ex+3.81),str(ey+dy),'0']
    for pin in children(extra,'pin'):child(pin,'uuid')[1]=uid()
    child(extra,'instances')[1:]=[['project',Q(project),['path',Q('/'+root_id),['reference',Q(ref)],['unit','1']]]]
    s.append(extra)
    for name,ypin,ytip in [(f'L{i}',ey-3.81,ey-8.89),(f'K{i}',ey+3.81,ey+8.89)]:
        s.append(['wire',['pts',['xy',str(ex),str(ypin)],['xy',str(ex),str(ytip)]],['stroke',['width','0'],['type','default']],['uuid',uid()]])
        s.append(label(name,ex,ytip))
for inst in children(s,'symbol'):
    for instances in children(inst,'instances'):
        for p in children(instances,'project'):p[1]=Q(project)
child(child(s,'title_block'),'title')[1]=Q('Letki v3.1 — pulsed-current candidate')
child(child(s,'title_block'),'rev')[1]=Q('Study C')
for node in list(children(s,'text')):
    if str(node[1]).startswith('STUDY B:'):s.remove(node)
s.append(['text',Q('STUDY C: requires v3_1-pulse firmware, NOT v3_1-mosfet or original v3.\n'
    'R1-R8 + R58-R65: two 68R in parallel per row = 34R nominal.\n'
    'Hardware OPM/PWM2: <=80us GPIO gate pulses every nominal 1ms per pixel.\n'
    'LED rating: 80mA max ONLY for <=100us and duty<=10%, at 25C.\n'
    'Expected current is illustrative ~35mA pulse; current/temperature/gate tails need scope checks.\n'
    'Common regulated 3.3V +/-5%. Five-tile power head target >=3A, recheck transients.\n'
    'NO PCB, FLASH, ORDER OR PHYSICAL QUALIFICATION.'),['at','342.9','266.7','0'],
    ['effects',['font',['size','1.2','1.2']],['justify','left']],['uuid',uid()]])
write(dest/(project+'.kicad_sch'),s)
p=json.loads((src/'ledkiv3_1_tme.kicad_pro').read_text())
assert not p['erc']['erc_exclusions'] and 'ignore' not in p['erc']['rule_severities'].values()
(dest/(project+'.kicad_pro')).write_text(json.dumps(p,indent=2)+'\n')
print(dest/(project+'.kicad_sch'))
