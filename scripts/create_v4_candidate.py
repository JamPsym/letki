#!/usr/bin/env python3
"""Create the initial v4 circuit/layout candidate without editing predecessors.

Refuses to overwrite an existing v4 project. This is a candidate generator,
not a fabrication release: placement, routing and USB power remain unfinished.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
from kicad_sexpr import Quoted as Q, child, children, prop, read, write

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'archive/hw/ledkiv3.1-ground-repair-20261014'
DEST=ROOT/'hw/ledkiv4'
ART=ROOT/'build/hardware/v4'

def uid(): return Q(str(uuid.uuid4()))
def effects(hidden=False):
    return ['effects',['font',['size','1.27','1.27']]]+([['hide','yes']] if hidden else [])
def property_(name,value,x=0,y=0,hidden=True):
    return ['property',Q(name),Q(value),['at',str(x),str(y),'0'],effects(hidden)]
def label(name,x,y):
    return ['label',Q(name),['at',str(x),str(y),'0'],effects(),['uuid',uid()]]
def library(path,name):
    return deepcopy(next(n for n in children(read(path),'symbol') if n[1]==name))

def main():
    if DEST.exists(): raise SystemExit('V4 already exists; refusing to overwrite source work')
    DEST.mkdir();ART.mkdir(parents=True,exist_ok=True)
    schema=read(SOURCE/'ledkiv3_1.kicad_sch')
    child(schema,'paper')[1]=Q('A3')
    root_id=child(schema,'uuid')[1]
    libs=child(schema,'lib_symbols')
    # Keep the original, verified pin geometry in a project-local MCU symbol.
    old_mcu=next(n for n in children(libs,'symbol') if 'CH32V003' in n[1])
    old_name=str(old_mcu[1]).split(':')[-1]
    old_mcu[1]=Q('Letki:CH32V003F4P6')
    for unit in children(old_mcu,'symbol'):
        unit[1]=Q(str(unit[1]).replace(old_name,'CH32V003F4P6'))
    prop(old_mcu,'Value')[2]=Q('CH32V003F4P6')
    local_mcu=deepcopy(old_mcu);local_mcu[1]=Q('CH32V003F4P6')
    write(DEST/'Letki.kicad_sym',['kicad_symbol_lib',['version','20241209'],['generator','kicad_symbol_editor'],local_mcu])
    write(DEST/'sym-lib-table',['sym_lib_table',['lib',['name',Q('Letki')],['type',Q('KiCad')],['uri',Q('${KIPRJMOD}/Letki.kicad_sym')],['options',Q('')],['descr',Q('Project-local CH32V003 symbol')]]])
    # Preserve the existing custom switch geometry as a portable footprint.
    old_pcb=read(SOURCE/'ledkiv3_1.kicad_pcb')
    switch=deepcopy(next(fp for fp in children(old_pcb,'footprint') if prop(fp,'Reference') and prop(fp,'Reference')[2]=='SW1'))
    switch[1]=Q('SW_tactile_TS-1089S')
    switch[:]=[v for v in switch if not(isinstance(v,list) and v[0] in ('at','uuid','path','sheetfile','sheetname'))]
    switch.insert(2,['version','20241229']);switch.insert(3,['generator','pcbnew'])
    prop(switch,'Reference')[2]=Q('REF**')
    for pad in children(switch,'pad'):
        pad[:]=[v for v in pad if not(isinstance(v,list) and v[0] in ('net','pinfunction','pintype','uuid'))]
    (DEST/'Letki.pretty').mkdir()
    write(DEST/'Letki.pretty/SW_tactile_TS-1089S.kicad_mod',switch)
    write(DEST/'fp-lib-table',['fp_lib_table',['lib',['name',Q('Letki')],['type',Q('KiCad')],['uri',Q('${KIPRJMOD}/Letki.pretty')],['options',Q('')],['descr',Q('Project-local switch footprint')]]])
    decoder=library('/usr/share/kicad/symbols/74xx.kicad_sym','74HC238')
    decoder[1]=Q('74xx:74HC238')
    libs[:] = [n for n in libs if not(isinstance(n,list) and n[0]=='symbol' and n[1]=='74xx:74HC138')]
    libs.append(decoder)
    mos=library('/usr/share/kicad/symbols/Transistor_FET.kicad_sym','Q_NMOS_GSD')
    mos[1]=Q('Transistor_FET:Q_NMOS_GSD');libs.append(mos)
    instances=children(schema,'symbol')
    output_numbers=['15','14','13','12','11','10','9','7']
    transistor_ids={}
    for inst in instances:
        ref=prop(inst,'Reference')[2]
        if ref in {f'R{n}' for n in range(1,9)}:
            prop(inst,'Value')[2]=Q('1k 1%')
            inst.append(property_('Specification','1 kOhm, 1%, >=0.125 W; MPN pending'))
        elif ref.startswith('D'):
            prop(inst,'Value')[2]=Q('XL-2012UOC')
            inst.append(property_('Manufacturer','XINGLIGHT'))
            inst.append(property_('LCSC','C965813'))
        elif ref=='U1':
            child(inst,'lib_id')[1]=Q('Letki:CH32V003F4P6')
            prop(inst,'Value')[2]=Q('CH32V003F4P6')
            inst.append(property_('Manufacturer','WCH'))
        elif ref in ('SW1','SW2'):
            prop(inst,'Footprint')[2]=Q('Letki:SW_tactile_TS-1089S')
        elif ref=='U2':
            child(inst,'lib_id')[1]=Q('74xx:74HC238')
            prop(inst,'Value')[2]=Q('74HC238PW,118')
            prop(inst,'Datasheet')[2]=Q('https://assets.nexperia.com/documents/data-sheet/74HC_HCT238.pdf')
            inst.append(property_('Manufacturer','Nexperia'))
            inst.append(property_('LCSC','C60434'))
            origin=child(inst,'at');ox,oy=map(float,origin[1:3])
            for unit in children(decoder,'symbol'):
                for pin in children(unit,'pin'):
                    number=child(pin,'number')[1]
                    if number not in output_numbers:continue
                    column=output_numbers.index(number)+1
                    at=child(pin,'at');x=ox+float(at[1]);y=oy-float(at[2])
                    endpoint=(round(x,6),round(y,6))
                    attached=[]
                    for wire in children(schema,'wire'):
                        pts=child(wire,'pts');ends=[tuple(round(float(v),6) for v in xy[1:]) for xy in children(pts,'xy')]
                        if endpoint in ends:attached.append((wire,ends))
                    assert len(attached)==1,(number,attached)
                    wire,ends=attached[0];schema.remove(wire)
                    other=ends[1] if ends[0]==endpoint else ends[0]
                    schema.append(label(f'S{column}',*other))
                    schema.append(label(f'COL_GATE{column}',x,y))
        for insts in children(inst,'instances'):
            for project in children(insts,'project'):project[1]=Q('ledkiv4')
    for n in range(1,9):
        x=45.72+35.56*((n-1)%4);y=175.26+35.56*((n-1)//4)
        ident=uid();transistor_ids[f'Q{n}']=str(ident)
        inst=['symbol',['lib_id',Q('Transistor_FET:Q_NMOS_GSD')],['at',str(x),str(y),'0'],['unit','1'],
              ['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',ident],
              property_('Reference',f'Q{n}',x+7,y-3,False),property_('Value','BSS138BK',x+7,y,False),
              property_('Footprint','Package_TO_SOT_SMD:SOT-23'),
              property_('Datasheet','https://datasheet.lcsc.com/datasheet/pdf/9d90026c4a547e4de8cc26451c8db995.pdf?productCode=C5224267'),
              property_('Manufacturer','ElecSuper'),property_('LCSC','C5224267'),
              ['instances',['project',Q('ledkiv4'),['path',Q('/'+root_id),['reference',Q(f'Q{n}')],['unit','1']]]]]
        for pin in ('1','2','3'):inst.append(['pin',Q(pin),['uuid',uid()]])
        ground=label('GND',x+2.54,y+5.08);ground[0]='global_label';ground.insert(2,['shape','input'])
        schema.extend([inst,label(f'COL_GATE{n}',x-5.08,y),ground,label(f'S{n}',x+2.54,y-5.08)])
    write(DEST/'ledkiv4.kicad_sch',schema)
    project=json.loads((SOURCE/'ledkiv3_1.kicad_pro').read_text())
    def rename(value):
        if isinstance(value,str):return value.replace('ledkiv3_1','ledkiv4')
        if isinstance(value,list):return [rename(v) for v in value]
        if isinstance(value,dict):return {k:rename(v) for k,v in value.items()}
        return value
    (DEST/'ledkiv4.kicad_pro').write_text(json.dumps(rename(project),indent=2)+'\n')
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(ART/'netlist.xml'),str(DEST/'ledkiv4.kicad_sch')],check=True,stdout=subprocess.DEVNULL)
    import pcbnew
    # Avoid KiCad's legacy SWIG deletion/ownership pitfalls on loaded objects.
    old_pcb[:]=[v for v in old_pcb if not(isinstance(v,list) and v[0] in ('segment','arc','via','zone'))]
    for fp in children(old_pcb,'footprint'):
        sf=child(fp,'sheetfile')
        if sf:sf[1]=Q('ledkiv4.kicad_sch')
        if fp[1]=='Library:SW_tactile_TS-1089S':fp[1]=Q('Letki:SW_tactile_TS-1089S')
    write(ART/'unrouted-base.kicad_pcb',old_pcb)
    board=pcbnew.LoadBoard(str(ART/'unrouted-base.kicad_pcb'))
    for ref,ident in transistor_ids.items():
        fp=pcbnew.FootprintLoad('/usr/share/kicad/footprints/Package_TO_SOT_SMD.pretty','SOT-23')
        fp.SetReference(ref);fp.SetValue('BSS138BK')
        index=int(ref[1:])-1
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(35+9*(index%4)),pcbnew.FromMM(95+4*(index//4))))
        board.Add(fp)
        fp.Flip(fp.GetPosition(),False)
        path=pcbnew.KIID_PATH();path.push_back(pcbnew.KIID(str(root_id)));path.push_back(pcbnew.KIID(ident));fp.SetPath(path)
    netlist=ET.parse(ART/'netlist.xml').getroot()
    footprints={f.GetReference():f for f in board.GetFootprints()}
    for comp in netlist.find('components'):
        fp=footprints[comp.attrib['ref']];fp.SetValue(comp.findtext('value'))
    for net in netlist.find('nets'):
        name=net.attrib['name'];ni=board.FindNet(name)
        if not ni:ni=pcbnew.NETINFO_ITEM(board,name);board.Add(ni)
        for node in net.findall('node'):
            fp=footprints[node.attrib['ref']]
            pads=[p for p in fp.Pads() if p.GetNumber()==node.attrib['pin']]
            assert pads,(node.attrib['ref'],node.attrib['pin'])
            for pad in pads:pad.SetNet(ni)
    pcbnew.SaveBoard(str(DEST/'ledkiv4.kicad_pcb'),board)
    print('Created v4 schematic and unrouted four-layer PCB candidate.')

if __name__=='__main__':main()
