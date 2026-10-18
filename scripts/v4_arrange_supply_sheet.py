#!/usr/bin/env python3
"""Give new power/UART sections readable space without changing their nets.

One-time annotation/layout operation, checked against exported net node sets.
"""
from pathlib import Path
import math
import subprocess
import xml.etree.ElementTree as E
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v4_buffer_rows import uid, pins, endpoint

ROOT=Path(__file__).resolve().parents[1];P=ROOT/'hw/ledkiv4/ledkiv4.kicad_sch'
ART=ROOT/'build/hardware/v4'


def export_groups(name):
    path=ART/name
    with open(ART/'arrange-netlist.log','w') as log:
        subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(path),str(P)],check=True,stdout=log,stderr=log)
    xml=E.parse(path).getroot()
    return {frozenset((n.attrib['ref'],n.attrib['pin']) for n in net.findall('node')) for net in xml.find('nets')}


def main():
    before=export_groups('pre-arrange-netlist.xml')
    s=read(P);child(s,'paper')[1]=Q('A2')
    targets={'U4':(419.1,50.8),'R26':(474.98,25.4),'R27':(474.98,76.2),
             'R28':(363.22,25.4),'R29':(363.22,76.2),'C7':(523.24,50.8),
             'J4':(370.84,175.26),'U5':(444.5,175.26),'R30':(358.14,233.68),
             'R31':(396.24,233.68),'R32':(482.6,233.68),'C10':(523.24,175.26),
             'U6':(444.5,302.26),'C8':(396.24,302.26),'C9':(500.38,302.26),
             '#FLG05':(523.24,233.68)}
    defs=child(s,'lib_symbols');insts={prop(i,'Reference')[2]:i for i in children(s,'symbol')}
    # All new sections have angle-zero instances and direct pin labels/NCs.
    moves={};newpins={}
    for ref,(x,y) in targets.items():
        i=insts[ref];at=child(i,'at');assert at[3]=='0'
        definition=next(n for n in children(defs,'symbol') if n[1]==child(i,'lib_id')[1])
        dx,dy=x-float(at[1]),y-float(at[2])
        for pin in pins(definition).values():
            point=endpoint(i,pin)
            assert point not in moves or moves[point]==(dx,dy)
            moves[point]=(dx,dy)
            newpins[(round(point[0]+dx,6),round(point[1]+dy,6))]=pin
        at[1:3]=[str(x),str(y)]
        for f in children(i,'property'):
            if f[1] not in ('Reference','Value'):continue
            pos=child(f,'at');pos[1:3]=[str(x+3.81),str(y+(-1.27 if f[1]=='Reference' else 1.27))]
            font=child(child(f,'effects'),'font');child(font,'size')[1:]=['1.0','1.0']
        if ref.startswith('U'):
            height=5.08 if ref=='U6' else 10.16
            for key,offset in [('Reference',7.62),('Value',5.08)]:
                at=child(prop(i,key),'at');at[1:3]=[str(x),str(round(y-height-offset,6))]
        if ref=='J4':
            for key,offset in [('Reference',23),('Value',20.46)]:
                at=child(prop(i,key),'at');at[1:3]=[str(x),str(round(y-offset,6))]
    for tag in ('label','global_label','no_connect'):
        for n in children(s,tag):
            at=child(n,'at');point=tuple(map(float,at[1:3]))
            if point not in moves:continue
            dx,dy=moves[point];at[1:3]=[str(round(point[0]+dx,6)),str(round(point[1]+dy,6))]
    for tag in ('label','global_label'):
        for n in children(s,tag):
            at=child(n,'at');point=tuple(map(float,at[1:3]))
            pin=newpins.get(point)
            if pin is None:continue
            angle=float(child(pin,'at')[3]);dx=-5.08*round(math.cos(math.radians(angle)));dy=5.08*round(math.sin(math.radians(angle)))
            tip=(round(point[0]+dx,6),round(point[1]+dy,6))
            at[1:3]=list(map(str,tip))
            if tag=='label':
                ef=child(n,'effects');old=child(ef,'justify')
                if old:ef.remove(old)
                ef.append(['justify','right' if dx<0 else 'left','bottom'])
            s.append(['wire',['pts',['xy',*map(str,point)],['xy',*map(str,tip)]],
                      ['stroke',['width','0'],['type','default']],['uuid',uid()]])
    title=child(s,'title_block')
    if not title:title=['title_block'];s.append(title)
    title[:]=['title_block',['title',Q('Letki v4 - orange LED tile (development)')],['date',Q('2026-10-11')],['rev',Q('v4 candidate')]]
    backup=P.read_text();write(P,s)
    if export_groups('netlist.xml')!=before:
        (ART/'failed-arrange-netlist.xml').write_bytes((ART/'netlist.xml').read_bytes())
        P.write_text(backup)
        raise SystemExit('Connectivity changed; restored source')
    print('New UART and power sections arranged on A2; all component net groups unchanged.')


if __name__=='__main__':main()
