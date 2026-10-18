#!/usr/bin/env python3
"""Validate and export the v4 prototype manufacturing review package.

Exports do not release the hardware, order boards, or program a device.
"""
import csv
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'hw/ledkiv4'
PCB = PROJECT / 'ledkiv4.kicad_pcb'
SCH = PROJECT / 'ledkiv4.kicad_sch'
OUTPUT = PROJECT / 'exports/prototype'


def run(*command):
    with (OUTPUT / 'commands.log').open('a') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-firmware',action='store_true',help='Build and include text and interface-test images; never flashes')
    args=parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_files=[*(PROJECT/('ledkiv4'+extension) for extension in ('.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru')),
                  PROJECT/'Letki.kicad_sym',PROJECT/'sym-lib-table',PROJECT/'fp-lib-table',
                  *sorted((PROJECT/'Letki.pretty').glob('*.kicad_mod')),
                  *sorted((PROJECT/'Letki.3dshapes').glob('*.step')),
                  *sorted((PROJECT/'mechanics').glob('letkiv4-mechanics-*.FCStd'))]
    initial_source_hashes={str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    initial_config_hash=hashlib.sha256((ROOT/'config/v4-mechanics.json').read_bytes()).hexdigest()
    (OUTPUT / 'commands.log').write_text('')
    run('kicad-cli', 'pcb', 'drc', '--refill-zones', '--schematic-parity',
        '--severity-all', '--exit-code-violations', '--format', 'json',
        '-o', str(OUTPUT / 'drc.json'), str(PCB))
    run('kicad-cli', 'sch', 'erc', '--severity-all', '--exit-code-violations',
        '--format', 'json', '-o', str(OUTPUT / 'erc.json'), str(SCH))
    drc=json.loads((OUTPUT/'drc.json').read_text())
    if drc['ignored_checks']:
        raise RuntimeError('PCB checks are disabled: '+str(drc['ignored_checks']))
    erc=json.loads((OUTPUT/'erc.json').read_text())
    erc_rule_notes={
        'single_global_label':'A single named global label is valid on this single-sheet design; explicit net checks verify its connectivity.',
        'four_way_junction':'Intentional wire junctions are allowed; pin-to-pin connectivity is checked independently.',
        'simulation_model_issue':'No SPICE simulation is claimed; vendor digital IC simulation models are not assigned.'}
    if any(item['key'] not in erc_rule_notes for item in erc['ignored_checks']):
        raise RuntimeError('An unexplained ERC check is disabled: '+str(erc['ignored_checks']))
    run(sys.executable, str(ROOT / 'scripts/check_v4_geometry.py'), str(PCB))
    run('kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
        '-o', str(ROOT / 'build/hardware/v4/netlist.xml'), str(SCH))
    run(sys.executable, str(ROOT / 'scripts/check_v4_circuit.py'))
    gerbers = OUTPUT / 'gerbers'
    gerbers.mkdir(exist_ok=True)
    run('kicad-cli', 'pcb', 'export', 'gerbers', '--check-zones', '--subtract-soldermask',
        '--layers', 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts',
        '-o', str(gerbers)+'/', str(PCB))
    job = json.loads((gerbers / 'ledkiv4-job.gbrjob').read_text())
    specs = job['GeneralSpecs']
    copper = {layer['Name']: layer['Thickness'] for layer in job['MaterialStackup']
              if layer['Type'] == 'Copper'}
    if (specs['LayerNumber'] != 4 or specs['BoardThickness'] != 1.6
            or specs['Finish'] != 'HAL lead-free'
            or copper != {'F.Cu': 0.035, 'In1.Cu': 0.0175,
                          'In2.Cu': 0.0175, 'B.Cu': 0.035}):
        raise RuntimeError('Exported stackup/finish contradict the prototype ordering baseline')
    run('kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon',
        '--excellon-units', 'mm', '--excellon-separate-th', '--excellon-oval-format', 'route',
        '--generate-report', '--report-path', str(OUTPUT / 'drill-report.txt'),
        '-o', str(gerbers)+'/', str(PCB))
    stencil = OUTPUT / 'stencil'
    stencil.mkdir(exist_ok=True)
    run('kicad-cli', 'pcb', 'export', 'gerbers', '--layers', 'F.Paste,B.Paste,Edge.Cuts',
        '-o', str(stencil)+'/', str(PCB))
    run('kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
        '--side', 'both', '-o', str(OUTPUT / 'positions-kicad.csv'), str(PCB))
    run('kicad-cli', 'sch', 'export', 'pdf', '-o', str(OUTPUT / 'schematic.pdf'), str(SCH))
    for side in ('front', 'back'):
        layers = 'F.Fab,F.Silkscreen,Edge.Cuts' if side == 'front' else 'B.Fab,B.Silkscreen,Edge.Cuts'
        command = ['kicad-cli', 'pcb', 'export', 'svg', '--mode-single', '--fit-page-to-board',
                   '--exclude-drawing-sheet', '--black-and-white', '--sketch-pads-on-fab-layers',
                   '--layers', layers, '-o', str(OUTPUT / f'assembly-{side}.svg')]
        if side == 'back':
            command.append('--mirror')
        run(*command, str(PCB))
    components = {}
    for c in ET.parse(ROOT / 'build/hardware/v4/netlist.xml').findall('./components/comp'):
        fields = {f.attrib['name']: f.text or '' for f in c.findall('./fields/field')}
        if fields.get('LCSC'):
            components[c.attrib['ref']] = (fields, c.findtext('value'), c.findtext('footprint'))
    positions = {r['Ref']: r for r in csv.DictReader((OUTPUT / 'positions-kicad.csv').open())}
    for role,with_swio in [('head',False),('follower',False),('head',True),('follower',True)]:
        population_name=role+('-swio' if with_swio else '')
        selected = {ref: data for ref, data in components.items()
                    if (role == 'head' or data[0].get('Population') != 'HEAD_ONLY')
                    and (with_swio or data[0].get('Population') != 'OPTIONAL_SWIO')}
        groups = defaultdict(list)
        for ref, (fields, value, footprint) in selected.items():
            groups[(fields['LCSC'], fields.get('MPN') or value, footprint)].append(ref)
        with (OUTPUT / f'BOM-{population_name}.csv').open('w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
            for (code, mpn, footprint), refs in sorted(groups.items()):
                writer.writerow([mpn, ','.join(refs), footprint, code])
        with (OUTPUT / f'CPL-{population_name}.csv').open('w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Designator', 'Mid X', 'Mid Y', 'Rotation', 'Layer'])
            for ref in sorted(selected):
                row = positions[ref]
                writer.writerow([ref, row['PosX'], row['PosY'], row['Rot'],
                                 'Top' if row['Side'] == 'top' else 'Bottom'])
        assert len(selected) == (118 if role == 'head' else 112)+int(with_swio)
    mechanical=OUTPUT/'mechanical';mechanical.mkdir(exist_ok=True)
    run('kicad-cli','pcb','export','step','--force','--subst-models','-o',str(mechanical/'ledkiv4-populated.step'),str(PCB))
    log=(OUTPUT/'commands.log').read_text()
    if 'Could not add 3D model' in log or 'File not found:' in log:
        raise RuntimeError('STEP export omitted a component model; review commands.log')
    for tiles in (1,4):
        run(sys.executable,str(ROOT/'scripts/v4_mechanics.py'),'--tiles',str(tiles),
            '--output',str(mechanical),'--pcb-step',str(mechanical/'ledkiv4-populated.step'))
    for name in ('assembly-exploded.png','carrier-rear.png'):
        shutil.copy2(ROOT/'build/hardware/v4/mechanical'/name,mechanical/name)
    geometry=json.loads((ROOT/'config/v4-mechanics.json').read_text())
    wire=geometry['edge_wire']
    roles=['5V','5V','SDA','SCL','TX to next RX','GND','GND']
    with (OUTPUT/'wire-staples.csv').open('w',newline='') as file:
        writer=csv.writer(file)
        writer.writerow(['Contact','Signal','Left_hole_X_mm','Right_hole_X_mm','Y_mm','Span_with_boards_touching_mm','Wire_diameter_mm','Finished_hole_mm'])
        for number,(left,right,role) in enumerate(zip(wire['left_holes_mm'],wire['right_holes_mm'],roles),1):
            writer.writerow([number,role,left[0],right[0],left[1],round(geometry['board_mm'][0]-right[0]+left[0],3),wire['wire_mm'],wire['hole_mm']])
    with (OUTPUT/'testpoints.csv').open('w',newline='') as file:
        writer=csv.writer(file);writer.writerow(['Reference','Signal','Net','Side','Front_view_X_mm','Front_view_Y_mm','Pad_diameter_mm','PCB_silk_number'])
        for point in geometry['testpoints']:
            writer.writerow([point['ref'],point['label'],point['net'],'Back',*point['xy_mm'],1,point['ref'][2:]])
    shutil.copy2(ROOT/'config/v4-mechanics.json',OUTPUT/'mechanical-dimensions.json')
    with (OUTPUT/'mechanical-parts.csv').open('w',newline='') as file:
        writer=csv.writer(file);writer.writerow(['Part','Quantity_for_five_tiles','Specification','Status'])
        for row in [('OpaqueGrid',5,'Opaque PLA/PETG; print supplied orientation','PRINT_FIT_PENDING'),
                    ('TranslucentFace',5,'0.6 mm translucent white; print separately','OPTICAL_QUALIFICATION_PENDING'),
                    ('FrontBezel',5,'Opaque PETG/PLA; top hooks and screw retention','PRINT_FIT_PENDING'),
                    ('Carrier4Tiles',1,'162.56 x 57.27 mm printed carrier','PRINT_FIT_PENDING'),
                    ('Carrier1Tiles',1,'One-tile extension','PRINT_FIT_PENDING'),
                    ('CarrierSplice',2,'Two splice plates at the 4+1 section joint','PRINT_FIT_PENDING'),
                    ('Board screws',10,'M2 x 12 mm pan head; confirm printed pilot fit','SOURCE_AND_FIT_PENDING'),
                    ('Splice screws',4,'M2 x 6 mm pan head; confirm printed pilot fit','SOURCE_AND_FIT_PENDING'),
                    ('Wire staples',28,'0.5 mm tinned solid copper; seven per joint; see wire-staples.csv','SOLDER_FIT_PENDING')]:writer.writerow(row)
    with zipfile.ZipFile(OUTPUT / 'ledkiv4-prototype-gerbers.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(gerbers.iterdir()):
            archive.write(path, path.name)
    shutil.copy2(ROOT/'docs/v4-qualification.csv',OUTPUT/'qualification-template.csv')
    bringup=OUTPUT/'v3-bringup';bringup.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'docs/interface-demo.md',bringup/'interface-demo.md')
    shutil.copy2(ROOT/'docs/interface-qualification.csv',bringup/'qualification-template.csv')
    procurement=OUTPUT/'procurement';procurement.mkdir(exist_ok=True)
    for tiles in (5,20):
        for prefix in ('lcsc-prototype','lcsc-available','lcsc-probe-accessories'):
            name=f'{prefix}-{tiles}-boards.csv'
            shutil.copy2(ROOT/'build/hardware/v4'/name,procurement/name)
    with (OUTPUT/'ORDER-AND-BRINGUP.txt').open('w') as f:
        f.write('''LETKI V4 PROTOTYPE HANDOFF - NOT A PRODUCTION RELEASE

PRE-ORDER GATE: v3 USART-to-PC passed; finish two-board I2C on v3 first.
Follow docs/interface-demo.md and record physical results. V4 is not ordered.
Those tests establish the baseline; v4 still needs its own qualification.

Five identical PCBs: one populated USB head, four followers.
Use BOM-head/CPL-head for the head and BOM-follower/CPL-follower otherwise.
Close JP1/JP2 only on the head. Populate the six HEAD_ONLY parts only there.
Default BOMs omit the optional J2 PicoBlade header. The -swio BOM/CPL files
include it; hand-soldering J2 avoids a separate factory THT assembly process.
The original bare SWIO pads remain usable with or without the header.

PCB: 40.64 x 49.27 mm, four layers, 1.6 mm, green mask, white legend.
Layer order: F.Cu / In1.Cu / In2.Cu / B.Cu; 1 oz outer, 0.5 oz inner.
Quote baseline: lead-free HASL, regular routed-outline tolerance.
Dielectric dimensions/material properties are nominal, not a controlled-
impedance specification. Confirm the fabricator's ordinary 1.6 mm stack.
Use individually routed boards for this prototype; edge copper is unsuitable
for a V-cut process. No castellated holes or plated edges are requested.
Ordinary 0.3 mm drilled plated-through vias, tented with solder mask on both
faces. No via filling, plugging or copper-capping process is requested.
Fourteen enclosed 0.8 mm wire PTHs have 1.3 mm lands; they are ordinary
through holes, not half holes. Separate plated slots and NPTH locator drills are supplied. No filled/capped
microvia process is requested. Verify exact HRO connector fit on the pilot.
Two 2.2 mm NPTH holes provide M2 mounting. J2 prototype PTH holes are 0.6 mm
with enlarged lands for regular fabrication tolerance. Molex's recommended
0.5 +/-0.05 mm hole drawing references a 0.8 mm PCB; qualify real connector
fit, pin protrusion and solder hole fill on this 1.6 mm PCB before release.

Native KiCad placement coordinates/rotations are supplied. Confirm every
part's pin 1 and LED cathode in the supplier preview before assembly.
The generic paste files include head apertures: omit those apertures for
followers according to BOM-follower. Check paste/assembly options with the
fabricator. Confirm the consigned MCU supply: CH32V003F4P6, TSSOP20.
CH32V003F4U6 is a different package and cannot replace it here.
C8/C9 use CL21B475KAB6PNE/C16194942, an active 4.7 uF/25 V X7R candidate.
Manufacturer bias curves support the design margin; first-article effective
capacitance and regulator stability still need physical evidence.

Power: one regulated 5 V, 1 A charger, one USB head per joined chain.
Start with a current-limited bench supply and inspect before charging.
Programming: WCH-LinkE GND -> J2 pad 3, SWIO -> J2 pad 2.
Leave WCH-LinkE 3.3 V/5 V outputs disconnected. J2 pad 1 is REF only.
Identify each chip and preserve its original readback before programming.
Agent flashing of new v4 units requires authorization for those identified
units; the existing v3 permission does not cover them.

If firmware images are included, active-text.bin is the initial display
application. The three interface images are separate UART/I2C tests and do
not replace the scrolling application by default. They are not physically
qualified on v4. Selecting an image is an explicit programming operation.
Build scripts never flash. Repository guides: docs/interface-demo.md and
docs/arch-setup.md. Supply and pin mapping match the active firmware.

Join corresponding edge contact numbers 1-7 using 0.5 mm tinned-wire
staples through the inward 0.8 mm holes, or the original rear solder lands:
5V / 5V / SDA / SCL / TX-to-next-RX / GND / GND. Support the chain on a
backing structure; solder joints must not carry insertion/bending loads.
Facing wire holes share Y; form the staple span for each numbered pair using
wire-staples.csv / mechanical-dimensions.json. Keep front wire ends <=0.5 mm and solder within
0.75 mm radius / 0.6 mm height before fitting the relieved optical grid.
Ten numbered rear TP pads expose USB input, 3V3, MCU UART, decoder addresses,
column-1 gate/cathode and GND. See testpoints.csv and assembly-back.svg; small silk numbers identify TP1-10.
No purchased components or paste apertures are added for the contacts/TPs.
The mechanical folder supplies an opaque grid seated on the PCB, separate
translucent face, front bezel with top hooks and a rear printed carrier.
Use a four-tile carrier plus one-tile extension for five boards, joined by
two printed splice plates and four M2 x 6 screws. Each tile uses two M2 x 12
screws into printed carrier pilots. Test one assembly before printing five.
STLs are already oriented and normalized for printing; no AMS is required.
FCStd dimensions are recorded metadata: regenerate geometry with the script.
Connector STEP models are conservative body envelopes, not supplier contact
CAD. Solder, cable overmoulds/bends, print tolerances and retention remain
physical qualification items. Earlier optical-only models are obsolete.

Use qualification-template.csv as a blank template, keeping measured records
separately. Check ground continuity, all pixels, rails, current/temperature,
USB orientation/inrush/short recovery, UART, I2C waveforms, full-chain voltage
drop and diffuser fit/legibility. Record unit IDs, lots and firmware hashes.
No production sign-off is granted by this archive.
''')
    if args.with_firmware:
        run('make','-j4')
        run('make','interface-demos','-j4')
        firmware=OUTPUT/'firmware';firmware.mkdir(exist_ok=True)
        for variant,name in [('v3','active-text'),('interface-demo','uart-test'),
                             ('interface-demo-controller','i2c-controller-test'),
                             ('interface-demo-target','i2c-target-test')]:
            shutil.copy2(ROOT/'build'/variant/'letki.bin',firmware/(name+'.bin'))
    bundle=OUTPUT/'ledkiv4-prototype-handoff.zip'
    final_source_hashes={str(p.relative_to(PROJECT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    if hashlib.sha256((ROOT/'config/v4-mechanics.json').read_bytes()).hexdigest()!=initial_config_hash:
        raise RuntimeError('Mechanical configuration changed during export; regenerate the package')
    if final_source_hashes!=initial_source_hashes:
        raise RuntimeError('An export changed the source CAD; review before packaging')
    def eligible(p):
        relative=p.relative_to(OUTPUT)
        return (p.is_file() and p!=bundle and p.name not in ('manifest.json','commands.log') and
                p.suffix.lower() not in ('.fcbak','.fcstd1','.bak') and
                (args.with_firmware or relative.parts[0]!='firmware'))
    manifest = {'status': 'PROTOTYPE_REVIEW_ONLY_NOT_PRODUCTION_RELEASE',
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'dimensions_mm': [40.64, 49.27], 'layers': 4,
                'head_components': 118, 'follower_components': 112,
                'head_with_swio_components':119,'follower_with_swio_components':113,
                'mechanical_status':'Nominal CAD/closed meshes checked; physical fit/retention/optics unqualified',
                'connector_models':'Local conservative body envelopes; not supplier CAD or contact/solder models',
                'fabrication_baseline':{'board_thickness_mm':1.6,
                    'copper_mm':copper,'finish':specs['Finish'],
                    'dielectrics':'Nominal; confirm ordinary fabricator stack, no controlled impedance'},
                'sourcing_gates':['CH32V003F4P6 source/assembly process',
                    'C8/C9 effective capacitance and regulator stability on first articles'],
                'assembly_note': 'CPL uses KiCad native coordinates/rotations; verify the supplier placement preview.',
                'erc_rule_notes':erc_rule_notes,
                'firmware_included':args.with_firmware,
                'remaining': 'Physical/power/optics/mechanical qualification, fabricator engineering review and stock resolution',
                'source_sha256':final_source_hashes,
                'source_unchanged_by_exports':True,
                'pre_order_gate':'V3 USART-to-PC passed; two-board I2C pending before ordering v4',
                'mechanical_config_sha256':hashlib.sha256((ROOT/'config/v4-mechanics.json').read_bytes()).hexdigest(),
                'files_sha256': {str(p.relative_to(OUTPUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in OUTPUT.rglob('*') if eligible(p)}}
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in OUTPUT.rglob('*'):
            if eligible(p) and p.name!='commands.log':archive.write(p,str(p.relative_to(OUTPUT)))
        archive.write(OUTPUT/'manifest.json','manifest.json')
    print(f'Validated prototype package: {OUTPUT}')
    print(f'Complete handoff archive: {bundle}')
    print('118 head / 112 follower parts. No production release or order created.')


if __name__ == '__main__':
    main()
