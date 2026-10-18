#!/usr/bin/env python3
"""Specify researched passive MPNs and apply the reviewed current-budget change.

The PCB pads stay unchanged. This does not release the BOM: capacitor bias,
switch footprint, operating envelope and physical qualification remain gates.
"""
from pathlib import Path
from kicad_sexpr import Quoted as Q, children, prop, read, write
from v4_buffer_rows import field

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'hw/ledkiv4/ledkiv4.kicad_sch'


def main():
    s=read(PATH);insts={prop(n,'Reference')[2]:n for n in children(s,'symbol')}
    groups=[
        ([f'R{i}' for i in range(1,9)],'1.2k 1%','UNI-ROYAL','0805W8F1201T5E','C17379','125mW, 150V, 1%, 100ppm/C'),
        (['R9','R14'],'100k','UNI-ROYAL','0805W8F1003T5E','C149504','125mW, 150V, 1%, 100ppm/C'),
        (['R11','R12'],'2.2k','UNI-ROYAL','0805W8F2201T5E','C17520','125mW, 150V, 1%, 100ppm/C'),
        ([f'R{i}' for i in range(15,26)]+['R28','R29'],'100k','UNI-ROYAL','0603WAF1003T5E','C25803','100mW, 75V, 1%, 100ppm/C'),
        (['R26','R27'],'2.2k','UNI-ROYAL','0603WAF2201T5E','C4190','100mW, 75V, 1%, 100ppm/C'),
        (['R30','R31'],'5.1k 1%','UNI-ROYAL','0603WAF5101T5E','C23186','100mW, 75V, 1%, 100ppm/C'),
        (['R32'],'33k 1%','UNI-ROYAL','0603WAF3302T5E','C4216','100mW, 75V, 1%, 100ppm/C'),
        (['C1','C3','C6','C7','C10'],'100n','YAGEO','CC0603KRX7R9BB104','C14663','50V, X7R, 10%, 0603'),
        (['C8','C9'],'4.7u 16V X7R','Samsung','CL21B475KOFNNNE','C107365','16V, X7R, 10%, 0805; effective capacitance qualification pending')]
    for refs,value,maker,mpn,code,rating in groups:
        for ref in refs:
            node=insts[ref];prop(node,'Value')[2]=Q(value)
            for name,text in [('Manufacturer',maker),('MPN',mpn),('LCSC',code),('Rating',rating),('Sourcing','Candidate; not released')]:
                f=prop(node,name)
                if f:f[2]=Q(text)
                else:node.append(field(name,text))
            prop(node,'Datasheet')[2]=Q('https://www.lcsc.com/datasheet/'+code+'.pdf')
    mcu=insts['U1']
    for name,text in [('Manufacturer','WCH'),('MPN','CH32V003F4P6'),('LCSC','C5187096')]:
        f=prop(mcu,name)
        if f:f[2]=Q(text)
        else:mcu.append(field(name,text))
    write(PATH,s)
    print('Specified passive candidates; 1.2k row resistors and 33k head current limit applied.')


if __name__=='__main__':main()
