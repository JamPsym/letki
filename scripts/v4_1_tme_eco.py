#!/usr/bin/env python3
"""One-time TME component ECO on the isolated v4.1 project.

Refuses to replay over the new circuit. Preserves original v4 and its archive.
Footprint geometry comes from installed KiCad libraries and manufacturer lands.
Routing is deliberately preserved for subsequent, independently checked repair.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import uuid
import xml.etree.ElementTree as ET

import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v4_buffer_rows import field, label, pins
from v4_logic_supply import box_symbol

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'hw/ledkiv4.1'
STEM = 'ledkiv4_1'
ART = ROOT / 'build/hardware/v4_1'


def setfield(node, name, value):
    previous = prop(node, name)
    if previous is None:
        node.append(field(name, value))
    else:
        previous[2] = Q(value)


def local_footprint(library, original, name):
    node = read(Path('/usr/share/kicad/footprints') / (library + '.pretty') / (original + '.kicad_mod'))
    node[1] = Q(name)
    for item in children(node, 'fp_line') + children(node, 'fp_arc'):
        if 'SilkS' in child(item, 'layer')[1]:
            child(child(item, 'stroke'), 'width')[1] = '0.15'
    for item in children(node, 'property') + children(node, 'fp_text'):
        effect = child(item, 'effects')
        if effect:
            child(child(effect, 'font'), 'size')[1:] = ['1', '1']
            thick = child(child(effect, 'font'), 'thickness')
            if thick: thick[1] = '0.15'
    write(PROJECT / 'Letki.pretty' / (name + '.kicad_mod'), node)
    return 'Letki:' + name


def alps_footprint():
    # ALPS SKRP series drawing No.1: 5.2 x 2.8 outer lands, 3.1 x 1.5 inner gaps.
    # Physical pins 1/2 are the same top-row contact; 3/4 the bottom-row contact.
    name = 'SW_ALPS_SKRPABE010_LetkiFab'
    text = f'''(footprint "{name}" (version 20241229) (generator pcbnew) (layer "F.Cu")
      (descr "ALPS SKRPABE010; catalogue drawing No.1; physical pins 1/2=logical1, 3/4=logical2; body 4.2x3.2x2.5; lands 1.05x0.65")
      (tags "ALPS SKRP 4.2mm dry circuit") (attr smd)
      (property "Reference" "REF**" (at 0 -2.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
      (property "Value" "SKRPABE010" (at 0 2.5) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
      (fp_rect (start -2.1 -1.6) (end 2.1 1.6) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))
      (fp_rect (start -2.85 -1.85) (end 2.85 1.85) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))
      (fp_line (start -1.4 -1.75) (end 1.4 -1.75) (stroke (width 0.15) (type default)) (layer "F.SilkS"))
      (fp_line (start -1.4 1.75) (end 1.4 1.75) (stroke (width 0.15) (type default)) (layer "F.SilkS"))
    '''
    for number, y in [('1', -1.075), ('2', 1.075)]:
        for x in [-2.075, 2.075]:
            text += f'(pad "{number}" smd rect (at {x} {y}) (size 1.05 0.65) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
    write(PROJECT / 'Letki.pretty' / (name + '.kicad_mod'), read_text(text + ')'))
    return 'Letki:' + name


def read_text(text):
    from kicad_sexpr import parse
    return parse(text)


def main():
    path = PROJECT / (STEM + '.kicad_sch')
    schema = read(path)
    insts = {str(prop(n, 'Reference')[2]): n for n in children(schema, 'symbol')}
    assert child(insts['U4'], 'lib_id')[1] == 'Letki:SN74LVC2G125DCUR', 'ECO already applied or source unexpected'
    assert child(insts['U6'], 'lib_id')[1] == 'Letki:ME6206A33M3G'
    ART.mkdir(parents=True, exist_ok=True)
    uart = box_symbol('74LVC2G34GW', [
        ('1','1A_TX','input',-12.7,5.08,0),
        ('6','1Y_TX','output',12.7,5.08,180),
        ('3','2A_RX','input',-12.7,-2.54,0),
        ('4','2Y_RX','output',12.7,-2.54,180),
        ('2','GND','power_in',0,-15.24,90),
        ('5','VCC','power_in',0,15.24,270)], width=7.62)
    ldo = box_symbol('MIC5504-3.3YM5', [
        ('1','VIN','power_in',-12.7,0,0),
        ('5','VOUT','power_out',12.7,0,180),
        ('2','GND','power_in',0,-12.7,90),
        ('3','EN','input',-12.7,5.08,0),
        ('4','NC','no_connect',12.7,-5.08,180)], width=7.62, height=7.62)
    local = read(PROJECT / 'Letki.kicad_sym')
    cache = child(schema, 'lib_symbols')
    for ref, definition in [('U4', uart), ('U6', ldo)]:
        oldid = child(insts[ref], 'lib_id')[1]
        cache[:] = [n for n in cache if not(isinstance(n,list) and n[0]=='symbol' and n[1]==oldid)]
        local.append(deepcopy(definition))
        cached = deepcopy(definition); cached[1] = Q('Letki:' + str(definition[1])); cache.append(cached)
        child(insts[ref], 'lib_id')[1] = cached[1]
        insts[ref][:] = [n for n in insts[ref] if not(isinstance(n,list) and n[0]=='pin')]
        for num in pins(definition): insts[ref].append(['pin',Q(num),['uuid',Q(str(uuid.uuid4()))]])
    for point in [(401.32,58.42),(436.88,58.42)]:
        matches = [n for n in children(schema,'global_label') if n[1]=='GND' and tuple(map(float,child(n,'at')[1:3]))==point]
        assert len(matches)==1, point
        schema.remove(matches[0])
        for wire in list(children(schema,'wire')):
            endpoints=[tuple(map(float,p[1:])) for p in children(child(wire,'pts'),'xy')]
            if point in endpoints: schema.remove(wire)
    schema.append(label('VCC',426.72,297.18))
    schema.append(['wire',['pts',['xy','426.72','297.18'],['xy','431.8','297.18']],
        ['stroke',['width','0'],['type','default']],['uuid',Q(str(uuid.uuid4()))]])
    for wire in children(schema,'wire'):
        for point in children(child(wire,'pts'),'xy'):
            if tuple(map(float,point[1:]))==(444.5,312.42):point[2]='314.96'
    for name,y in [('Reference','35.56'),('Value','38.1')]:
        node=prop(insts['U4'],name);child(node,'at')[1:4]=['392.7',y,'0']
        effect=child(node,'effects');justify=child(effect,'justify')
        if justify:justify[1:]=['left']
        else:effect.append(['justify','left'])
    schema.append(['no_connect',['at','457.2','307.34'],['uuid',Q(str(uuid.uuid4()))]])
    write(PROJECT / 'Letki.kicad_sym', local)
    footprints = {
        'U2':local_footprint('Package_SO','SOIC-16_3.9x9.9mm_P1.27mm','SOIC-16_3.9x9.9mm_P1.27mm_LetkiFab'),
        'U4':local_footprint('Package_TO_SOT_SMD','SOT-363_SC-70-6','SOT-363_SC-70-6_LetkiFab'),
        'U6':local_footprint('Package_TO_SOT_SMD','SOT-23-5','SOT-23-5_LetkiFab'),
        'J4':local_footprint('Connector_USB','USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal','USB_C_Receptacle_GCT_USB4105_Head_LetkiFab'),
        'SW1':alps_footprint()}
    footprints['SW2'] = footprints['SW1']
    groups = {
        'column decoder':['U2'], 'row source buffer':['U3'], 'UART dual buffer':['U4'],
        'column sink MOSFET':[f'Q{i}' for i in range(1,9)], '3.3V regulator':['U6'],
        '100nF bypass':['C1','C3','C6','C7','C10'], 'LDO input/output capacitor':['C8','C9'],
        'buttons':['SW1','SW2'], 'row resistors':[f'R{i}' for i in range(1,9)],
        'idle pulls':['R9','R14'], 'selectable I2C pulls':['R11','R12'],
        'startup pulls':[f'R{i}' for i in range(15,26)]+['R28','R29'],
        'UART series resistors':['R26','R27'], 'USB CC pulls':['R30','R31'],
        'USB current limit resistor':['R32'], 'USB-C head connector':['J4'],
        'USB input current limiter':['U5'], 'optional SWIO header':['J2']}
    profile_path = ROOT / 'config/v4_1-parts.json'
    profile = json.loads(profile_path.read_text())
    for part in profile['selected_parts']:
        if part['role']=='buttons':
            part.update(tme_symbol='SKRPABE010',mpn='SKRPABE010',package='4.2x3.2x2.5mm SMD; ALPS recommended lands',
                supplier_url='https://www.tme.eu/pl/details/skrpabe010/mikroprzelaczniki-tact/alps/',minimum=1,multiple=1,
                stock_snapshot=63,source_age='3-week catalogue snapshot, not live cart',
                currency='PLN',price_breaks=[{'quantity':1,'unit_net':'0.73'},{'quantity':10,'unit_net':'0.64'},{'quantity':50,'unit_net':'0.58'}],
                review_note='ALPS minimum 10uA/1V; button loop nominal 33uA at 3.3V. Physical pins1/2 and3/4 internally common.')
        if part['role']=='USB-C head connector':
            part.update(stock_snapshot=35730,source_age='TME product page crawled today, 2026-10-12',
                price_breaks=[{'quantity':1,'unit_net':'2.85'},{'quantity':10,'unit_net':'2.44'},{'quantity':25,'unit_net':'2.25'},{'quantity':60,'unit_net':'2.08'}])
        part['references']=groups[part['role']]
        part['status']='CAD_SELECTION; validate availability at checkout'
        for ref in part['references']:
            node=insts[ref]
            for name,text in [('MPN',part['mpn']),('TME',part['tme_symbol']),('SupplierURL',part['supplier_url']),('Sourcing','TME; prototype selection')]:setfield(node,name,text)
            # A different MPN must not carry its predecessor's LCSC order code.
            node[:]=[n for n in node if not(isinstance(n,list) and n[0]=='property' and n[1]=='LCSC')]
    specs = {
        'U2':('74HCT238D,653','Nexperia','https://assets.nexperia.com/documents/data-sheet/74HC_HCT238.pdf'),
        'U4':('74LVC2G34GW,125','Nexperia','https://assets.nexperia.com/documents/data-sheet/74LVC2G34.pdf'),
        'U6':('MIC5504-3.3YM5-TR','Microchip','https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MIC550x-300mA-Single-Output-LDO-DS20006006.pdf'),
        'J4':('USB4105-GF-A','GCT','https://gct.co/connector/usb4105'),
        'SW1':('SKRPABE010','ALPS','https://tech.alpsalpine.com/cms.media/product_catalog_ta_02_skrp_en_2cd80f610b.pdf'),
        'SW2':('SKRPABE010','ALPS','https://tech.alpsalpine.com/cms.media/product_catalog_ta_02_skrp_en_2cd80f610b.pdf')}
    for ref,(value,maker,datasheet) in specs.items():
        for name,text in [('Value',value),('Manufacturer',maker),('Datasheet',datasheet)]:setfield(insts[ref],name,text)
    for ref in [f'Q{i}' for i in range(1,9)]:
        setfield(insts[ref],'Value','DMG2302UK-7');setfield(insts[ref],'Manufacturer','Diodes Incorporated');setfield(insts[ref],'Datasheet','https://www.diodes.com/assets/Datasheets/DMG2302UK.pdf')
    for ref in ['C8','C9']:
        setfield(insts[ref],'Value','4.7u 25V X7R');setfield(insts[ref],'Rating','25V X7R 10%; confirm effective capacitance >=1uF')
    setfield(insts['U2'],'Description','3-to-8 decoder, active HIGH outputs; 5V HCT TTL inputs')
    for ref in ['U1']+[f'D{i}' for i in range(1,65)]:setfield(insts[ref],'Sourcing','USER_STOCK; excluded from TME purchases')
    for ref,fp in footprints.items():setfield(insts[ref],'Footprint',fp)
    # New resistor S-series MPNs are Royalohm; old LCSC datasheet links no longer describe them.
    for ref,node in insts.items():
        if ref.startswith('R') and prop(node,'TME'):
            setfield(node,'Manufacturer','Royalohm');setfield(node,'Datasheet',prop(node,'SupplierURL')[2])
    for ref in ['R26','R27']:setfield(insts[ref],'Value','220')
    write(path,schema)
    profile['status']='Component ECO applied; PCB rerouting and independent checks pending'
    profile_path.write_text(json.dumps(profile,indent=2)+'\n')
    update_pcb(schema, footprints)


def update_pcb(schema, footprints):
    path = PROJECT / (STEM + '.kicad_sch')
    insts = {str(prop(n,'Reference')[2]):n for n in children(schema,'symbol')}
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(ART/'netlist.xml'),str(path)],check=True)
    netlist=ET.parse(ART/'netlist.xml').getroot()
    board=pcbnew.LoadBoard(str(PROJECT/(STEM+'.kicad_pcb')))
    fps={f.GetReference():f for f in board.GetFootprints()}
    # Retain removed native proxies until SaveBoard; Python 3.14/SWIG bindings
    # otherwise invalidate type wrappers when the last old proxy is collected.
    retained_old=list(fps.values())
    replacements={ref:pcbnew.FootprintLoad(str(PROJECT/'Letki.pretty'),fpname.split(':')[1]) for ref,fpname in footprints.items()}
    changes=[]
    for ref,fpname in footprints.items():
        print('Updating footprint',ref,flush=True)
        old=fps[ref];pos=old.GetPosition();angle=old.GetOrientationDegrees();layer=old.GetLayer()
        fp=replacements[ref];assert fp
        fp.SetReference(ref);fp.SetValue(str(prop(insts[ref],'Value')[2]));fp.SetFPID(pcbnew.LIB_ID('Letki',fpname.split(':')[1]))
        fp.SetUuid(old.m_Uuid)
        board.Remove(old)
        board.Add(fp);fp.SetPosition(pos)
        if layer==pcbnew.B_Cu:fp.Flip(pos,False)
        fp.SetOrientationDegrees(angle);fp.SetPath(old.GetPath())
        fp.SetAttributes(old.GetAttributes());fp.SetSheetfile(STEM+'.kicad_sch')
        if ref=='J4':fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(20.32),pcbnew.FromMM(46.17)))
        for fld in fp.GetFields():fld.SetVisible(False);fld.SetLayer(pcbnew.B_Fab);fld.SetMirrored(True)
        fp.Reference().SetVisible(True);fp.Reference().SetLayer(pcbnew.B_SilkS)
        fp.Reference().SetPosition(old.Reference().GetPosition());fp.Reference().SetTextSize(old.Reference().GetTextSize())
        changes.append({'ref':ref,'old':str(old.GetFPID()),'new':fpname})
        fps[ref]=fp
    for ref,node in insts.items():
        if ref not in fps:continue
        fp=fps[ref];fp.SetValue(str(prop(node,'Value')[2]))
        for fld in children(node,'property'):
            if fld[1] not in ['Reference','Value','Footprint']:
                fp.SetField(str(fld[1]),str(fld[2]));fp.GetField(str(fld[1])).SetVisible(False)
        # Removed legacy supplier fields must not persist as stale PCB metadata.
        if prop(node,'TME') and fp.HasField('LCSC'):fp.Remove(fp.GetField('LCSC'))
    for net in netlist.find('nets'):
        ni=board.FindNet(net.attrib['name'])
        if not ni:ni=pcbnew.NETINFO_ITEM(board,net.attrib['name']);board.Add(ni)
        for node in net.findall('node'):
            matched=[p for p in fps[node.attrib['ref']].Pads() if p.GetNumber()==node.attrib['pin']]
            assert matched,node.attrib
            for pad in matched:pad.SetNet(ni);pad.SetPinFunction(node.attrib.get('pinfunction',''));pad.SetPinType(node.attrib.get('pintype',''))
    pcbnew.SaveBoard(str(PROJECT/(STEM+'.kicad_pcb')),board)
    (ART/'component-eco.json').write_text(json.dumps({'changes':changes,'status':'Routing repair pending'},indent=2)+'\n')
    print('Applied isolated v4.1 TME ECO; existing routing retained for repair.')


if __name__=='__main__':main()
