#!/usr/bin/env python3
"""One-shot creation of the complete v3.1 tile context from preserved Study C.

Never run this on an existing candidate. Placement and routing ECOs are separate.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v3_1_transistor_study import field, label, pin_point, uid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'archive/hw/ledkiv3.1-studies-20261015/pulse-study'
DEST = ROOT / 'hw/ledkiv3.1'
ART = ROOT / 'build/hardware/v3_1-integration'
PROJECT = 'ledkiv3_1'
LIB = 'Letki31'


def vector(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    if DEST.exists():
        raise SystemExit('Candidate exists; edit it, never replay creation/placement.')
    ART.mkdir(parents=True, exist_ok=True)
    protected = {}
    for directory in ['hw', 'archive/hw', 'firmware/v3']:
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and 'exports' not in path.parts:
                protected[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (ART / 'protected-inputs.json').write_text(json.dumps(protected, indent=2)+'\n')
    DEST.mkdir()
    footprints = DEST / (LIB+'.pretty')
    footprints.mkdir()
    schematic = read(SOURCE / 'ledkiv3_1_pulse.kicad_sch')
    cache = child(schematic, 'lib_symbols')
    definitions = {str(s[1]): s for s in children(cache, 'symbol')}
    instances = {str(prop(s, 'Reference')[2]): s for s in children(schematic, 'symbol')}
    root_id = str(child(schematic, 'uuid')[1])

    def update(inst, name, value):
        node = prop(inst, name)
        if node:
            node[2] = Q(value)
        else:
            inst.append(field(name, value))

    def add_definition(library, name):
        key = library+':'+name
        if key not in definitions:
            definition = deepcopy(next(s for s in children(read('/usr/share/kicad/symbols/'+library+'.kicad_sym'), 'symbol') if s[1] == name))
            definition[1] = Q(key)
            cache.append(definition)
            definitions[key] = definition
        return key

    def wire(a, b):
        schematic.append(['wire', ['pts', ['xy', *map(str, a)], ['xy', *map(str, b)]],
                          ['stroke', ['width', '0'], ['type', 'default']], ['uuid', uid()]])

    def net_label(name, at):
        node = label(name, *at)
        if name == 'GND':
            node[0] = 'global_label'
            node.insert(2, ['shape', 'input'])
        schematic.append(node)

    def place(ref, value, lib_id, x, y, angle, footprint, nets, bom=True, metadata=()):
        inst = ['symbol', ['lib_id', Q(lib_id)], ['at', str(x), str(y), str(angle)], ['unit', '1'],
                ['in_bom', 'yes' if bom else 'no'], ['on_board', 'yes'], ['dnp', 'no'], ['uuid', uid()],
                field('Reference', ref, x+3.81, y-1.27, False),
                field('Value', value, x+3.81, y+1.27, False), field('Footprint', footprint),
                *[field(k, v) for k, v in metadata],
                ['instances', ['project', Q(PROJECT), ['path', Q('/'+root_id), ['reference', Q(ref)], ['unit', '1']]]]]
        schematic.append(inst)
        instances[ref] = inst
        if not nets:
            return inst
        for unit in children(definitions[lib_id], 'symbol'):
            for pin in children(unit, 'pin'):
                number = str(child(pin, 'number')[1])
                pt = pin_point(inst, pin)
                dx, dy = pt[0]-x, pt[1]-y
                sx, sy = ((1 if dx > 0 else -1), 0) if abs(dx) > abs(dy) else (0, (1 if dy > 0 else -1))
                tip = (round(pt[0]+5.08*sx, 6), round(pt[1]+5.08*sy, 6))
                wire(pt, tip)
                net_label(nets[number], tip)
                inst.append(['pin', Q(number), ['uuid', uid()]])
        return inst

    # Change only the edge labels; the MCU-side labels remain the core nets.
    for node in children(schematic, 'label'):
        x, y = map(float, child(node, 'at')[1:3])
        if node[1] == 'UTX' and y > 140:
            node[1] = Q('UTX_EDGE')
        elif node[1] == 'URX' and y > 140:
            node[1] = Q('URX_EDGE')
    # Remove the power symbol directly on each pull-up's supply pin. The new
    # solder jumper makes the pair head-selectable, open on ordinary tiles.
    for ref, name in [('R11', 'I2C_SCL_PULL'), ('R12', 'I2C_SDA_PULL')]:
        r = instances[ref]
        point = pin_point(r, next(p for u in children(definitions['Device:R'], 'symbol')
                                 for p in children(u, 'pin') if child(p, 'number')[1] == '1'))
        power = [s for s in children(schematic, 'symbol') if child(s, 'lib_id')[1] == 'power:VCC'
                 and tuple(map(float, child(s, 'at')[1:3])) == point]
        assert len(power) == 1, (ref, point)
        schematic.remove(power[0])
        wire(point, (point[0], point[1]-5.08))
        net_label(name, (point[0], point[1]-5.08))

    resistor = 'Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'
    for ref, x, y, nets, value, mpn in [
        ('R66', 355.6, 195.58, {'1':'UTX', '2':'UTX_EDGE'}, '1k 1%', 'RC0805FR-071KL'),
        ('R67', 406.4, 195.58, {'1':'URX_EDGE', '2':'URX'}, '1k 1%', 'RC0805FR-071KL'),
        ('R68', 457.2, 195.58, {'1':'VCC', '2':'URX_EDGE'}, '10k', 'RC0805FR-0710KL')]:
        place(ref, value, 'Device:R', x, y, 90, resistor, nets,
              metadata=[('MPN', mpn), ('Sourcing', 'USER_STOCK' if ref == 'R68' else 'UNREGISTERED_1K_OR_PURCHASE')])
    jumper = add_definition('Jumper', 'SolderJumper_2_Open')
    for ref, x, name in [('JP1',355.6,'I2C_SCL_PULL'), ('JP2',406.4,'I2C_SDA_PULL')]:
        place(ref, 'I2C pull enable', jumper, x, 236.22, 0,
              'Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm', {'1':'VCC', '2':name}, bom=False,
              metadata=[('Assembly', 'OPEN on tiles; close one pair per common I2C bus only')])
    mount = add_definition('Mechanical', 'MountingHole')
    for number in (1, 2):
        place('H'+str(number), 'M2', mount, 355.6+25.4*(number-1), 271.78, 0,
              'Letki31:MountingHole_2.2mm_M2_LetkiFab', {}, bom=False)

    # Retain assessed native padstack, connector and fastener geometry from v4.1.
    special = ['EdgeWire_1x07_P5.08mm_D0.8mm',
               'Molex_PicoBlade_53047-0310_1x03_P1.25mm_Vertical_SWIO_LetkiFab',
               'MountingHole_2.2mm_M2_LetkiFab', 'LED_0805_2012Metric_LetkiFab']
    for name in special:
        shutil.copy2(ROOT / 'hw/ledkiv4.1/Letki.pretty' / (name+'.kicad_mod'), footprints)
    for ref in ['J1','J3']:
        update(instances[ref], 'Footprint', LIB+':'+special[0])
        child(instances[ref], 'in_bom')[1] = 'no'
        update(instances[ref], 'Assembly', 'PCB wire contacts; no purchased connector, no edge plating')
    j2 = instances['J2']
    update(j2, 'Value', '53047-0310')
    update(j2, 'Footprint', LIB+':'+special[1])
    child(j2, 'in_bom')[1] = 'yes'
    for name, value in [('MPN','530470310'),('Manufacturer','Molex'),('Supplier','TME'),
                        ('Supplier code','MX-53047-0310'),('Sourcing','ORDERED_FOR_V4_1; no automatic reassignment'),
                        ('Assembly','Fit one header per tile; parallel bare pads remain available'),
                        ('Datasheet','https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/530/53047/530470310_sd.pdf')]:
        update(j2, name, value)
    # Local symbol copies keep exact footprint filters enabled and portable.
    for original, name, refs in [('Connector_Generic:Conn_01x07','EdgeWire_01x07',['J1','J3']),
                                ('Connector_Generic:Conn_01x03','SWIO_PicoBlade_01x03',['J2']),
                                ('Mechanical:MountingHole','M2_MountingHole',['H1','H2'])]:
        definition = deepcopy(definitions[original])
        definition[1] = Q(LIB+':'+name)
        old_name = original.split(':')[1]
        for unit in children(definition, 'symbol'):
            unit[1] = Q(str(unit[1]).replace(old_name, name))
        update(definition, 'Footprint', str(prop(instances[refs[0]], 'Footprint')[2]))
        update(definition, 'ki_fp_filters', str(prop(instances[refs[0]], 'Footprint')[2]).split(':')[1])
        cache.append(definition)
        definitions[str(definition[1])] = definition
        for ref in refs:
            child(instances[ref], 'lib_id')[1] = Q(LIB+':'+name)

    # Materialize all used footprint and nonstandard symbol dependencies.
    for ref, inst in instances.items():
        if ref.startswith('#') or ref not in {str(prop(s,'Reference')[2]) for s in children(schematic,'symbol')}:
            continue
        fpfield = prop(inst, 'Footprint')
        if not fpfield or not fpfield[2]:
            continue
        library, name = str(fpfield[2]).split(':')
        if ref.startswith('D'):
            name = special[3]
        elif library != LIB:
            source = SOURCE / 'LetkiStudy.pretty' / (name+'.kicad_mod') if library == 'LetkiStudy' else Path('/usr/share/kicad/footprints') / (library+'.pretty') / (name+'.kicad_mod')
            if not (footprints / (name+'.kicad_mod')).exists():
                shutil.copy2(source, footprints)
        fpfield[2] = Q(LIB+':'+name)
        for instance in children(inst, 'instances'):
            for project in children(instance, 'project'):
                project[1] = Q(PROJECT)
    local_symbols = []
    for definition in children(cache, 'symbol'):
        name = str(definition[1])
        if name.startswith(('LetkiStudy:', LIB+':')):
            local = deepcopy(definition)
            local[1] = Q(name.split(':')[1])
            local_symbols.append(local)
    shutil.copy2(SOURCE / 'LetkiStudy.kicad_sym', DEST / 'LetkiStudy.kicad_sym')
    write(DEST / (LIB+'.kicad_sym'), ['kicad_symbol_lib', ['version','20241209'],
          ['generator','kicad_symbol_editor'], *[s for s in local_symbols if s[1] not in ['CH32V003F4P6','SN74HC138PWR']]])
    table = ['sym_lib_table']
    for name in ['LetkiStudy',LIB]:
        table.append(['lib',['name',Q(name)],['type',Q('KiCad')],['uri',Q('${KIPRJMOD}/'+name+'.kicad_sym')],['options',Q('')],['descr',Q('v3.1 project-local symbols')]])
    write(DEST/'sym-lib-table',table)
    write(DEST/'fp-lib-table',['fp_lib_table',['lib',['name',Q(LIB)],['type',Q('KiCad')],['uri',Q('${KIPRJMOD}/'+LIB+'.pretty')],['options',Q('')],['descr',Q('v3.1 complete local footprint context')]]])
    child(child(schematic,'title_block'),'title')[1] = Q('Letki v3.1 — pulsed LED tile')
    child(child(schematic,'title_block'),'rev')[1] = Q('v3.1 development')
    for item in list(children(schematic,'text')):
        if str(item[1]).startswith('STUDY C:'):
            schematic.remove(item)
    schematic.append(['text',Q('v3.1: external regulated 3.3V +/-5% only.\n'
        'Two 68R per row in parallel; ONLY v3_1-pulse OPM/PWM2 firmware.\n'
        'Nominal gate pulse <=80us / pixel period 1ms; qualify LED/gate waveforms.\n'
        'JP1/JP2: close only one pair per I2C chain; otherwise leave OPEN.\n'
        'J2: 1 REF, 2 SWIO/PD1, 3 GND; current LinkE cable uses SWIO/GND.\n'
        'Same-supply chain only; no hot-plug or 5V interface qualification.\n'
        'ESP-12F / USB-C buck head deferred by user until hardware qualification.\n'
        'Prototype in development; not a fabrication release.'),['at','340.36','302.26','0'],
        ['effects',['font',['size','1.2','1.2']],['justify','left']],['uuid',uid()]])
    write(DEST / (PROJECT+'.kicad_sch'), schematic)
    settings = json.loads((ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_pro').read_text())
    settings['erc'] = json.loads((SOURCE/'ledkiv3_1_pulse.kicad_pro').read_text())['erc']
    settings['board']['design_settings']['drc_exclusions'] = []
    assert 'ignore' not in settings['board']['design_settings']['rule_severities'].values()
    (DEST/(PROJECT+'.kicad_pro')).write_text(json.dumps(settings,indent=2)+'\n')
    shutil.copy2(ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_dru', DEST/(PROJECT+'.kicad_dru'))
    # Use the four-layer stackup/settings, without any reference board objects.
    template = read(ROOT/'hw/ledkiv4.1/ledkiv4_1.kicad_pcb')
    keep = {'version','generator','generator_version','general','paper','layers','setup','embedded_fonts'}
    blank = [template[0], *[deepcopy(x) for x in template[1:] if isinstance(x,list) and x[0] in keep]]
    write(ART/'blank.kicad_pcb',blank)
    board = pcbnew.LoadBoard(str(ART/'blank.kicad_pcb'))
    outline = pcbnew.PCB_SHAPE(board)
    outline.SetShape(pcbnew.SHAPE_T_RECT); outline.SetLayer(pcbnew.Edge_Cuts)
    outline.SetStart(vector(0,0)); outline.SetEnd(vector(40.64,49.27)); outline.SetWidth(pcbnew.FromMM(.05))
    board.Add(outline)
    netlist = ART/'netlist.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(netlist),str(DEST/(PROJECT+'.kicad_sch'))], check=True)
    netroot = ET.parse(netlist).getroot()
    poses = {'U1':(20.32,26.8,0),'U2':(20.32,17.1,0),
             'C3':(14.5,24.525,0),'C1':(26.1,19.375,180),'C4':(20.32,1.6,0),
             'SW1':(16.0,45.9,0),'SW2':(29.1,45.9,0),
             'C2':(14.0,40.3,0),'R9':(18.1,40.3,0),'R10':(18.1,43.1,0),
             'C5':(27.1,40.3,0),'R13':(27.1,43.1,0),'R14':(31.6,40.3,0),
             'R39':(16,21,0),'R40':(20.5,21,0),'R41':(25,21,0),
             'J1':(39.37,7.62,0),'J3':(1.27,7.62,0),'J2':(7.62,46.75,0),
             'H1':(2.54,46.75,0),'H2':(38.1,46.75,0),
             'JP1':(30,14.1,0),'JP2':(35,14.1,0),
             'R11':(30,17.1,0),'R12':(35,17.1,0),
             'R66':(35,23.1,0),'R67':(5,30,0),'R68':(10,30,0)}
    for n in range(1,9):
        x = 4.6+4.5*(n-1)
        poses[f'Q{n}']=(x,4.8,0)
        poses[f'R{14+n}']=(x,8.5,0)
        poses[f'R{22+n}']=(x,11.5,0)
        poses[f'Q{8+n}']=(x,37.8,0)
        poses[f'R{41+n}']=(x,34.2,0)
        poses[f'R{30+n}']=(x,31.2,0)
        y = 17+3*((n-1)%4)
        left = n<=4
        poses[f'R{n}']=(5.0 if left else 30.0,y,0)
        poses[f'R{57+n}']=(10.0 if left else 35.0,y,0)
        poses[f'R{49+n}']=(5+5*((n-1)%4),14.2 if n<=4 else 29.8,0)
    fps = {}
    for comp in netroot.find('components'):
        ref = comp.attrib['ref']; inst = instances[ref]
        name = comp.findtext('footprint').split(':')[1]
        fp = pcbnew.FootprintLoad(str(footprints),name)
        assert fp, (ref,name)
        board.Add(fp); fp.SetReference(ref); fp.SetValue(comp.findtext('value'))
        fp.SetFPID(pcbnew.LIB_ID(LIB,name))
        if ref.startswith('D'):
            index=int(ref[1:])-1; row,col=divmod(index,8)
            x,y,angle=2.54+5.08*col,40.64-5.08*row,180
            layer=pcbnew.F_Cu
        else:
            x,y,angle=poses[ref];layer=pcbnew.B_Cu
        fp.SetPosition(vector(x,y))
        if fp.GetLayer()!=layer:
            fp.Flip(fp.GetPosition(),False)
        fp.SetOrientationDegrees(angle)
        path=pcbnew.KIID_PATH();path.push_back(pcbnew.KIID(root_id));path.push_back(pcbnew.KIID(str(child(inst,'uuid')[1])))
        fp.SetPath(path); fp.SetSheetfile(PROJECT+'.kicad_sch');fp.SetSheetname('')
        if child(inst,'in_bom')[1]=='no':
            fp.SetAttributes(fp.GetAttributes()|pcbnew.FP_EXCLUDE_FROM_BOM|pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        for f in children(inst,'property'):
            if f[1] not in ['Reference','Value','Footprint']:
                fp.SetField(str(f[1]),str(f[2]));fp.GetField(str(f[1])).SetVisible(False)
        for f in fp.GetFields():
            f.SetLayer(pcbnew.F_Fab if layer==pcbnew.F_Cu else pcbnew.B_Fab)
            f.SetMirrored(layer==pcbnew.B_Cu)
        fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
        fps[ref]=fp
    for node in netroot.find('nets'):
        net=pcbnew.NETINFO_ITEM(board,node.attrib['name']);board.Add(net)
        for endpoint in node.findall('node'):
            pads=[p for p in fps[endpoint.attrib['ref']].Pads() if p.GetNumber()==endpoint.attrib['pin']]
            assert pads,endpoint.attrib
            for p in pads:
                p.SetNet(net);p.SetPinFunction(endpoint.attrib.get('pinfunction',''));p.SetPinType(endpoint.attrib.get('pintype',''))
    pcbnew.SaveBoard(str(DEST/(PROJECT+'.kicad_pcb')),board)
    # LoadBoard of the blank context owns default project settings; SaveBoard
    # can write them beside a new destination. Restore authored settings last.
    (DEST/(PROJECT+'.kicad_pro')).write_text(json.dumps(settings,indent=2)+'\n')
    (ART/'initial-placements.json').write_text(json.dumps({ref:[*pcbnew.ToMM(fp.GetPosition()),fp.GetOrientationDegrees(),fp.GetLayerName()] for ref,fp in fps.items()},indent=2)+'\n')
    print(f'Created {DEST}: {len(fps)} footprints, four layers; routing pending.')


if __name__ == '__main__':
    main()
