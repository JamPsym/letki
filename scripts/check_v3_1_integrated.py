#!/usr/bin/env python3
"""Audit the current v3.1 schematic and, by default, its matching PCB.

--schematic-only checks the electrical design during a pending PCB update.
It never substitutes for the full PCB pin/pad, geometry and parity audit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--board',type=Path,default=ROOT/'hw/ledkiv3.1/ledkiv3_1.kicad_pcb')
parser.add_argument('--output',type=Path,default=ROOT/'build/hardware/v3_1-integration/circuit-geometry.json')
parser.add_argument('--schematic-only',action='store_true',help='Audit the schematic only; do not qualify the PCB')
args=parser.parse_args()
args.output.parent.mkdir(parents=True,exist_ok=True)
# A failed rerun must not leave an earlier PASS at the requested report path.
args.output.write_text(json.dumps({'status':'NOT_PASSED',
                                 'scope':'Audit has not completed; see command failure output',
                                 'PCB_checked':False},indent=2)+'\n')


def netlist(path,target):
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(target),str(path)],check=True,stdout=subprocess.DEVNULL)
    root=ET.parse(target).getroot()
    parts={c.attrib['ref']:c for c in root.findall('components/comp')}
    nets={n.attrib['name']:{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node')} for n in root.findall('nets/net')}
    bypin={pin:(name,pins) for name,pins in nets.items() for pin in pins}
    return parts,nets,bypin


before,before_nets,before_pins=netlist(ROOT/'archive/hw/ledkiv3.1-studies-20261015/pulse-study/ledkiv3_1_pulse.kicad_sch',args.output.parent/'audit-study-c.xml')
parts,nets,pins=netlist(args.board.with_suffix('.kicad_sch'),args.output.parent/'audit-integrated.xml')
node_types={(node.attrib['ref'],node.attrib['pin']):node.attrib.get('pintype','')
            for net in ET.parse(args.output.parent/'audit-integrated.xml').getroot().findall('nets/net')
            for node in net.findall('node')}
removed_parallel={f'R{i}' for i in range(58,66)}
removed_buttons={'SW1','SW2','R9','R10','R13','R14','C2','C5'}
removed=removed_parallel|removed_buttons
gate_series={f'R{i}' for i in [*range(15,23),*range(42,50)]}
gate_bias={f'R{i}' for i in [*range(23,39),*range(50,58)]}
gate_resistors=gate_series|gate_bias
row_resistors={f'R{i}' for i in range(1,9)}
assert set(parts)-set(before)=={'R66','R67','R68','H1','H2'}
assert set(before)-set(parts)==removed, 'Unexpected removed component population'
boundaries={('J1','5'),('J3','5'),('R11','1'),('R12','1')}
retained={pin for pin in before_pins if pin[0] not in removed}-boundaries
for pin in retained:
    assert (before_pins[pin][1]&retained)==(pins[pin][1]&retained), ('Study-C connectivity changed',pin)
for ref,component in before.items():
    if ref in ['J1','J2','J3'] or ref in removed:continue
    assert parts[ref].findtext('value')==('33R 1%' if ref in row_resistors else component.findtext('value')),ref
    expected_footprint=('Letki31:R_0603_1608Metric_Pad0.98x0.95mm_HandSolder'
                        if ref in gate_resistors else 'Letki31:LED_0805_2012Metric_LetkiFab'
                        if ref.startswith('D') else 'Letki31:'+component.findtext('footprint').split(':',1)[1])
    assert parts[ref].findtext('footprint')==expected_footprint, ('Schematic footprint mismatch',ref)
assert {r for r in parts if r.startswith('U')}=={'U1','U2'}
assert len(parts)==146
assert len(gate_resistors)==40


def same(*endpoints):
    group=pins[endpoints[0]][1]
    assert all(pin in group for pin in endpoints),endpoints
    return group


same(('U1','2'),('R66','1'))
assert pins['J1','5'][1]=={('J1','5'),('R66','2')}
same(('U1','3'),('R67','2'))
assert pins['J3','5'][1]=={('J3','5'),('R67','1'),('R68','2')}
same(('R68','1'),('U1','9'))
for resistor in ['R11','R12']:same((resistor,'1'),('U1','9'))
assert 'JP1' not in parts and 'JP2' not in parts
same(('U1','18'),('J2','2'));same(('U1','9'),('J2','1'));same(('U1','7'),('J2','3'))
# Each removed button GPIO is intentionally isolated and marked NC.
for pin in [('U1','6'),('U1','8')]:
    assert pins[pin][1]=={pin}, ('Removed button GPIO unexpectedly connected',pin)
    assert node_types[pin].endswith('+no_connect'), ('Missing no-connect marker',pin)
# Check the two Astra regressions explicitly, including all eight LED rows.
same(('R39','1'),('U1','9'))
same(('R39','2'),('U1','17'),('U2','1'))
for row in range(8):
    expected={(f'R{row+1}','1')}|{(f'D{row*8+col+1}','1') for col in range(8)}
    assert pins[f'R{row+1}','1'][1]==expected, ('LED cathode row disconnected',row+1)
for ref in ['R66','R67']:assert parts[ref].findtext('value')=='1k 1%'
assert parts['R68'].findtext('value')=='10k'
for ref in row_resistors|{'R11','R12','R39','R40','R41','R66','R67','R68'}:
    assert parts[ref].findtext('footprint')=='Letki31:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder',ref
assert parts['J2'].findtext('footprint')=='Letki31:Molex_PicoBlade_53047-0310_1x03_P1.25mm_Vertical_SWIO_LetkiFab'
for ref,component in parts.items():
    library,item=component.findtext('footprint').split(':',1)
    assert library=='Letki31' and (args.board.parent/'Letki31.pretty'/f'{item}.kicad_mod').is_file(), ('Missing local footprint',ref)
# Conservative UART low budget: pull is BEFORE RX series resistor, so its
# current crosses only the upstream TX resistor. Include 1uA input leakage
# across both series resistors; GPIO VOL<=0.4V remains a bench condition.
receiver_low=.4+(3.465-.4)*(1030/(9700+1030))+1e-6*2060
assert receiver_low<.3*3.135

settings=json.loads(args.board.with_suffix('.kicad_pro').read_text())
assert not settings['board']['design_settings']['drc_exclusions']
assert not settings['erc']['erc_exclusions']
assert all(v!='ignore' for v in settings['board']['design_settings']['rule_severities'].values())
assert all(v!='ignore' for v in settings['erc']['rule_severities'].values())
assert settings['board']['design_settings']['rules']['min_copper_edge_clearance']==.2

schematic_report={
    'status':'SCHEMATIC_PASS; PCB_NOT_CHECKED',
    'scope':'Current schematic core equivalence, exact population, footprints, LED rows, interfaces and project rule settings',
    'PCB_checked':False,
    'PCB_synchronization_qualified':False,
    'schematic_components':len(parts),
    'removed_parallel_resistors':sorted(removed_parallel),
    'removed_button_network':sorted(removed_buttons),
    'gate_bias_0603':len(gate_resistors),
    'row_current_0805':len(row_resistors),
    'retained_core_pins_checked':len(retained),
    'UART_conditional_low_V':receiver_low,
    'UART_VIL_limit_at_minimum_supply_V':.3*3.135,
    'schematic_sha256':hashlib.sha256(args.board.with_suffix('.kicad_sch').read_bytes()).hexdigest(),
    'project_sha256':hashlib.sha256(args.board.with_suffix('.kicad_pro').read_bytes()).hexdigest(),
    'physical_qualification':'PENDING',
}
if args.schematic_only:
    args.output.write_text(json.dumps(schematic_report,indent=2)+'\n')
    print(json.dumps(schematic_report))
    raise SystemExit(0)

import pcbnew
board=pcbnew.LoadBoard(str(args.board))
fps={f.GetReference():f for f in board.GetFootprints()}
assert set(fps)==set(parts), ('PCB synchronization required',
                            {'PCB_only':sorted(set(fps)-set(parts)),
                             'schematic_only':sorted(set(parts)-set(fps))})
pad_count=0
for ref,fp in fps.items():
    assert str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName())==parts[ref].findtext('footprint'),ref
    for pad in fp.Pads():
        number=pad.GetNumber()
        if not number:continue
        assert pad.GetNetname()==pins[ref,number][0],(ref,number,pad.GetNetname(),pins[ref,number][0])
        pad_count+=1
for n in range(1,65):
    fp=fps[f'D{n}'];row,col=divmod(n-1,8)
    assert fp.GetLayer()==pcbnew.F_Cu and abs(fp.GetOrientationDegrees()-180)<1e-5
    assert all(abs(a-b)<2e-6 for a,b in zip(pcbnew.ToMM(fp.GetPosition()),(2.54+5.08*col,40.64-5.08*row)))
for ref,x in [('J3',1.27),('J1',39.37)]:
    fp=fps[ref]
    assert fp.GetLayer()==pcbnew.B_Cu
    for pad in fp.Pads():
        n=int(pad.GetNumber())
        assert all(abs(a-b)<2e-6 for a,b in zip(pcbnew.ToMM(pad.GetPosition()),(x,7.62+(n-1)*5.08)))
        assert pcbnew.ToMM(pad.GetDrillSize())==(.8,.8)
        assert all(abs(a-b)<1e-5 for a,b in zip(pcbnew.ToMM(pad.GetSize(pcbnew.B_Cu)),(2.04,1.6)))
        for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu]:
            assert pcbnew.ToMM(pad.GetSize(layer))==(1.4,1.4)
        assert pad.GetLocalZoneConnection()==pcbnew.ZONE_CONNECTION_FULL
header=fps['J2']
assert len(list(header.Pads()))==6
for number,net in [('1','VCC'),('2','/SWDIO'),('3','GND')]:
    p=[p for p in header.Pads() if p.GetNumber()==number]
    assert len(p)==2 and all(pad.GetNetname()==net for pad in p)
    assert sum(pad.GetAttribute()==pcbnew.PAD_ATTRIB_PTH for pad in p)==1
for ref,x in [('H1',2.54),('H2',38.1)]:
    pad=list(fps[ref].Pads())[0]
    assert pcbnew.ToMM(pad.GetDrillSize())==(2.2,2.2)
    assert pcbnew.ToMM(pad.GetPosition())==(x,46.75)
assert board.GetCopperLayerCount()==4
in1_tracks=[t for t in board.GetTracks() if not isinstance(t,pcbnew.PCB_VIA) and t.IsOnLayer(pcbnew.In1_Cu)]
exceptions_path=args.board.parent/'in1-exceptions.json'
in1_audit=None
if in1_tracks:
    assert exceptions_path.exists(),'In1 signal needs an explicit scoped exception manifest'
    exceptions=json.loads(exceptions_path.read_text())
    expected={t['uuid']:t for t in exceptions['allowed_tracks']}
    allowed_nets=set(exceptions.get('allowed_nets',[exceptions.get('allowed_net')]))
    assert {t.m_Uuid.AsString() for t in in1_tracks}==set(expected),'Unreviewed In1 copper'
    for track in in1_tracks:
        target=expected[track.m_Uuid.AsString()]
        assert track.GetNetname() in allowed_nets
        if 'net' in target:assert track.GetNetname()==target['net']
        assert abs(pcbnew.ToMM(track.GetWidth())-target['width_mm'])<1e-6
        for actual,key in [(track.GetStart(),'start_mm'),(track.GetEnd(),'end_mm')]:
            assert all(abs(a-b)<1e-6 for a,b in zip(pcbnew.ToMM(actual),target[key]))
    length=sum(pcbnew.ToMM(t.GetLength()) for t in in1_tracks)
    assert length<=exceptions['max_total_length_mm']
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    planes=[z for z in board.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(pcbnew.In1_Cu)]
    assert len(planes)==1
    copper=planes[0].GetFilledPolysList(pcbnew.In1_Cu)
    reviewed_regions=exceptions.get('reviewed_GND_polygon_count',1)
    assert copper.OutlineCount()==reviewed_regions,'GND topology changed after review'
    if reviewed_regions>1:
        assert exceptions.get('review',{}).get('isolated_regions'),'Multiple GND regions need an explicit stitch review'
        bridges=exceptions.get('reviewed_GND_bridges',[])
        assert bridges,'Reviewed GND regions need bound physical bridges'
        board_tracks={t.m_Uuid.AsString():t for t in board.GetTracks() if not isinstance(t,pcbnew.PCB_VIA)}
        for row in bridges:
            t=board_tracks[row['uuid']]
            assert t.GetNetname()=='GND' and t.GetLayerName()==row['layer']
            assert pcbnew.ToMM(t.GetWidth())>=row['width_mm']-1e-6
            for actual,key in [(t.GetStart(),'start_mm'),(t.GetEnd(),'end_mm')]:
                assert all(abs(x-y)<1e-6 for x,y in zip(pcbnew.ToMM(actual),row[key]))
    # A plane may have separate regions joined on another layer. Check actual
    # conductive continuity independently; merely listing regions is insufficient.
    power_path=args.output.parent/'power-connectivity-for-core.json'
    subprocess.run([sys.executable,ROOT/'scripts/check_v3_1_power.py',
                    '--board',str(args.board),'--output',str(power_path)],check=True)
    power_audit=json.loads(power_path.read_text())
    assert power_audit['status']=='PASS'
    assert all(power_audit['nets'][net]['connected_components']==1 for net in ['GND','VCC'])
    assert copper.Area()/1e12>=exceptions.get('minimum_GND_area_mm2',0)
    in1_audit={'nets':sorted(allowed_nets),'track_count':len(in1_tracks),
               'length_mm':length,'GND_filled_regions':copper.OutlineCount(),
               'GND_multilayer_connected_components':power_audit['nets']['GND']['connected_components'],
               'GND_area_mm2':copper.Area()/1e12,
               'exception_manifest_sha256':hashlib.sha256(exceptions_path.read_bytes()).hexdigest()}
report={**schematic_report,'status':'PASS','scope':'Core equivalence, interface additions, native pin/pad geometry and rule settings; not routing or physical qualification',
        'PCB_checked':True,'PCB_synchronization_qualified':True,
        'retained_core_pins_checked':len(retained),'electrical_pads_checked':pad_count,'footprints':len(fps),
        'UART_conditional_low_V':receiver_low,'UART_VIL_limit_at_minimum_supply_V':.3*3.135,
        'board_sha256':hashlib.sha256(args.board.read_bytes()).hexdigest(),
        'schematic_sha256':hashlib.sha256(args.board.with_suffix('.kicad_sch').read_bytes()).hexdigest(),
        'scoped_In1_audit':in1_audit}
args.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
