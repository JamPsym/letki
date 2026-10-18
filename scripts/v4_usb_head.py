#!/usr/bin/env python3
"""Add an optional 5 V USB-C chain-head supply with current limiting.

Development transformation, not a fabrication-release generator. Head-only
population is an assembly variant; do not fit/connect several USB feeds.
"""
from copy import deepcopy
from pathlib import Path
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v4_buffer_rows import field, instance, label, lib, pins, endpoint, uid
from v4_logic_supply import box_symbol

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'hw/ledkiv4'


def main():
    path=PROJECT/'ledkiv4.kicad_sch';s=read(path)
    assert not children(read(PROJECT/'ledkiv4.kicad_pcb'),'segment'), 'PCB already routed'
    assert not any(prop(i,'Reference')[2]=='U5' for i in children(s,'symbol')), 'Head supply already applied'
    definitions=child(s,'lib_symbols')
    # U5 now drives VCC; the inherited external-source flag would falsely
    # claim a second power output on that net.
    oldflag=next(i for i in children(s,'symbol') if prop(i,'Reference')[2]=='#FLG03')
    s.remove(oldflag)
    oldpoint=child(oldflag,'at')[1:3]
    branches=[w for w in children(s,'wire') if any(x[1:]==oldpoint for x in children(child(w,'pts'),'xy'))]
    assert len(branches)==1
    s.remove(branches[0])
    power=box_symbol('TPS2553DBVR', [
        ('1','IN','power_in',-12.7,5.08,0),
        ('2','GND','power_in',0,-15.24,90),
        ('3','EN','input',-12.7,0,0),
        ('4','~{FAULT}','open_collector',12.7,0,180),
        ('5','ILIM','passive',12.7,-5.08,180),
        ('6','OUT','power_out',12.7,5.08,180)])
    local=read(PROJECT/'Letki.kicad_sym');local.append(deepcopy(power));write(PROJECT/'Letki.kicad_sym',local)
    cached=deepcopy(power);cached[1]=Q('Letki:TPS2553DBVR');definitions.append(cached)
    usb=lib('/usr/share/kicad/symbols/Connector.kicad_sym','USB_C_Receptacle_USB2.0_16P')
    usb[1]=Q('Connector:USB_C_Receptacle_USB2.0_16P');definitions.append(usb)
    u5=instance(s,'Letki:TPS2553DBVR',power,'U5','TPS2553DBVR',
                'Package_TO_SOT_SMD:SOT-23-6',116.84,205.74)
    j4=instance(s,'Connector:USB_C_Receptacle_USB2.0_16P',usb,'J4','TYPE-C-31-M-12',
                'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12',25.4,157.48)
    prop(u5,'Datasheet')[2]=Q('https://www.ti.com/lit/ds/symlink/tps2553.pdf')
    prop(j4,'Datasheet')[2]=Q('https://en.krhro.com/Product-Details/726.html')
    u5.extend([field('Manufacturer','TI'),field('LCSC','C55266')])
    j4.extend([field('Manufacturer','HRO'),field('LCSC','C165948')])
    head=[u5,j4]
    def connect(node,definition,pin,net):
        s.append(label(net,*endpoint(node,pins(definition)[str(pin)])))
    for pin,net in {1:'USB_VBUS',2:'GND',3:'USB_VBUS',5:'USB_ILIM',6:'VCC'}.items():
        connect(u5,power,pin,net)
    s.append(['no_connect',['at',*[str(v) for v in endpoint(u5,pins(power)['4'])]],['uuid',uid()]])
    # Stacked USB power pins share geometry; one label per physical endpoint.
    for pin,net in {'A1':'GND','SH':'GND','A4':'USB_VBUS','A5':'USB_CC1','B5':'USB_CC2'}.items():
        connect(j4,usb,pin,net)
    for pin in ('A6','A7','A8','B6','B7','B8'):
        s.append(['no_connect',['at',*[str(v) for v in endpoint(j4,pins(usb)[pin])]],['uuid',uid()]])
    resistor=next(n for n in children(definitions,'symbol') if n[1]=='Device:R')
    for ref,value,x,y,net in [('R30','5.1k 1%',25.4,205.74,'USB_CC1'),
                            ('R31','5.1k 1%',50.8,205.74,'USB_CC2'),
                            ('R32','61.9k 1%',152.4,228.6,'USB_ILIM')]:
        r=instance(s,'Device:R',resistor,ref,value,'Resistor_SMD:R_0603_1608Metric',x,y)
        connect(r,resistor,1,net);connect(r,resistor,2,'GND');head.append(r)
    cap=next(n for n in children(definitions,'symbol') if n[1]=='Device:C')
    c10=instance(s,'Device:C',cap,'C10','100n','Capacitor_SMD:C_0603_1608Metric',109.22,228.6)
    connect(c10,cap,1,'USB_VBUS');connect(c10,cap,2,'GND');head.append(c10)
    for node in head:node.append(field('Population','HEAD_ONLY'))
    # The connector is passive: flag the external supply, not its switched output.
    flag=next(n for n in children(definitions,'symbol') if n[1]=='power:PWR_FLAG')
    f=instance(s,'power:PWR_FLAG',flag,'#FLG05','PWR_FLAG','',119.38,243.84,bom=False)
    child(f,'on_board')[1]='no';connect(f,flag,1,'USB_VBUS')
    write(path,s)
    print('Added optional USB-C chain head: two 5.1k CC pulls, TPS2553 and 61.9k limit resistor.')


if __name__=='__main__':main()
