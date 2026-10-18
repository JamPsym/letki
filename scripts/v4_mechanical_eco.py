#!/usr/bin/env python3
"""Apply the bounded mounting/SWIO revision in an isolated project copy.

Never overwrites the source project or discards existing routing. Review ERC,
DRC and geometry before promoting the copy. The source/library UUIDs survive.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil

import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v4_buffer_rows import field, instance, lib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'hw/ledkiv4'
HEADER = 'Molex_PicoBlade_53047-0310_1x03_P1.25mm_Vertical'
COMBINED = HEADER + '_SWIO_LetkiFab'
MOUNT = 'MountingHole_2.2mm_M2_LetkiFab'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == SOURCE.resolve() or output.exists():
        parser.error('output must be a new isolated directory')
    pcb_source = SOURCE / 'ledkiv4.kicad_pcb'
    board = pcbnew.LoadBoard(str(pcb_source))
    assert len(list(board.GetTracks())) > 1000, 'Expected the reviewed routed board'
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    assert 'H1' not in fps and 'H2' not in fps, 'Mounting revision already applied'
    assert len(list(fps['J2'].Pads())) == 3, 'SWIO revision already applied'
    geometry = json.loads((ROOT / 'config/v4-mechanics.json').read_text())
    shutil.copytree(SOURCE, output, ignore=shutil.ignore_patterns('exports', '.history', '*-backups', '*.bak', '*.lck'))
    baseline = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in SOURCE.glob('ledkiv4.kicad_*') if p.is_file()}
    (output / 'eco-baseline.json').write_text(json.dumps(baseline, indent=2)+'\n')
    project_file = output / 'ledkiv4.kicad_pro'
    settings = json.loads(project_file.read_text())
    for check, severity in settings['board']['design_settings']['rule_severities'].items():
        if severity == 'ignore': settings['board']['design_settings']['rule_severities'][check] = 'warning'
    settings['erc']['rule_severities']['footprint_filter'] = 'warning'
    project_file.write_text(json.dumps(settings, indent=2)+'\n')

    # Preserve the manufacturer's THT lands and body, adding separate bare
    # test pads without stencil apertures. All six pads are explicitly routed.
    header = read(Path('/usr/share/kicad/footprints/Connector_Molex.pretty') / (HEADER+'.kicad_mod'))
    header[1] = Q(COMBINED)
    child(header, 'descr')[1] = Q('Molex 53047-0310 plus optional bare SWIO pads; 0.5 mm finished holes, 1.25 mm pitch')
    for line in children(header, 'fp_line') + children(header, 'fp_rect'):
        if child(line, 'layer')[1] == 'F.SilkS':
            child(child(line, 'stroke'), 'width')[1] = '0.15'
    prop(header, 'Value')[2] = Q('53047-0310')
    for name in ('Reference', 'Value'):
        child(prop(header, name), 'layer')[1] = Q('F.Fab')
        if name == 'Value': prop(header, name).append(['hide', 'yes'])
    origin = geometry['swio_header_pin1_mm']
    for number, (x, y) in enumerate(geometry['swio_test_pads_mm'], 1):
        header.append(['pad', Q(str(number)), 'smd', 'circle',
                       ['at', str(round(x-origin[0], 6)), str(round(origin[1]-y, 6))],
                       ['size', '1.6', '1.6'], ['layers', Q('F.Cu'), Q('F.Mask')]])
    # One courtyard includes the bare pads and header. No separate overlapping
    # footprint or DRC exclusion is needed for the two population options.
    courtyard = next(n for n in children(header, 'fp_rect') if child(n, 'layer')[1]=='F.CrtYd')
    child(courtyard, 'start')[1:] = ['-3.59', '-2.56']
    child(courtyard, 'end')[1:] = ['4.5', '3.35']
    write(output / 'Letki.pretty' / (COMBINED+'.kicad_mod'), header)

    mount = read('/usr/share/kicad/footprints/MountingHole.pretty/MountingHole_2.2mm_M2.kicad_mod')
    mount[1] = Q(MOUNT)
    for n in ('Reference', 'Value'):
        child(prop(mount, n), 'layer')[1] = Q('F.Fab')
        prop(mount, n).append(['hide', 'yes'])
    radius = geometry['fastener_clearance_radius_mm']
    points = [['xy', str(round(radius*math.cos(i*math.tau/64), 6)),
               str(round(radius*math.sin(i*math.tau/64), 6))] for i in range(64)]
    mount.append(['zone', ['net', '0'], ['net_name', Q('')],
                  ['layers', Q('F.Cu'), Q('In1.Cu'), Q('In2.Cu'), Q('B.Cu')],
                  ['name', Q('M2 fastener and insulating boss clearance')],
                  ['hatch', 'edge', '0.5'], ['min_thickness', '0.25'],
                  ['keepout', ['tracks', 'not_allowed'], ['vias', 'not_allowed'],
                   ['pads', 'allowed'], ['copperpour', 'not_allowed'], ['footprints', 'allowed']],
                  ['polygon', ['pts', *points]]])
    write(output / 'Letki.pretty' / (MOUNT+'.kicad_mod'), mount)

    schema = read(output / 'ledkiv4.kicad_sch')
    cached = child(schema, 'lib_symbols')
    j2 = next(n for n in children(schema, 'symbol') if prop(n, 'Reference')[2]=='J2')
    old_id = child(j2, 'lib_id')[1]
    definition = deepcopy(next(n for n in children(cached, 'symbol') if n[1]==old_id))
    local_name = 'SWIO_PicoBlade_01x03'
    definition[1] = Q('Letki:'+local_name)
    for unit in children(definition, 'symbol'):
        unit[1] = Q(str(unit[1]).replace('SWIO_Pads_01x03', local_name))
    prop(definition, 'Footprint')[2] = Q('Letki:'+COMBINED)
    prop(definition, 'ki_fp_filters')[2] = Q(COMBINED)
    prop(definition, 'Description')[2] = Q('Optional vertical PicoBlade SWIO connector, with bare test pads in parallel')
    cached.append(definition)
    symbol_library = read(output / 'Letki.kicad_sym')
    library_definition = deepcopy(definition)
    library_definition[1] = Q(local_name)
    symbol_library.append(library_definition)
    write(output / 'Letki.kicad_sym', symbol_library)
    child(j2, 'lib_id')[1] = Q('Letki:'+local_name)
    child(j2, 'in_bom')[1] = 'yes'
    prop(j2, 'Value')[2] = Q('53047-0310')
    prop(j2, 'Footprint')[2] = Q('Letki:'+COMBINED)
    for name, value in [('Manufacturer', 'MOLEX'), ('MPN', '530470310'),
                        ('LCSC', 'C122442'), ('Population', 'OPTIONAL_SWIO'),
                        ('Assembly', 'Optional hand-soldered header; bare pads remain usable')]:
        existing = prop(j2, name)
        if existing: existing[2] = Q(value)
        else: j2.append(field(name, value))
    prop(j2, 'Datasheet')[2] = Q('https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/530/53047/530470310_sd.pdf')
    hole_definition = lib('/usr/share/kicad/symbols/Mechanical.kicad_sym', 'MountingHole')
    hole_definition[1] = Q('Mechanical:MountingHole')
    cached.append(hole_definition)
    for index in range(1, 3):
        instance(schema, 'Mechanical:MountingHole', hole_definition, 'H'+str(index),
                 'M2', 'Letki:'+MOUNT, 35.56+(index-1)*20.32, 294.64, bom=False)
    write(output / 'ledkiv4.kicad_sch', schema)

    old = fps['J2']
    nets = {p.GetNumber(): p.GetNet() for p in old.Pads()}
    replacement = pcbnew.FootprintLoad(str(output/'Letki.pretty'), COMBINED)
    assert replacement
    # KiCad 10 needs a board parent before flipping a THT footprint.
    board.Add(replacement)
    replacement.SetFPID(pcbnew.LIB_ID('Letki', COMBINED))
    replacement.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(origin[0]), pcbnew.FromMM(origin[1])))
    replacement.Flip(replacement.GetPosition(), False)
    replacement.SetOrientationDegrees(0)
    replacement.SetReference('J2'); replacement.SetValue('53047-0310')
    replacement.SetPath(old.GetPath())
    replacement.SetSheetfile(old.GetSheetfile()); replacement.SetSheetname(old.GetSheetname())
    for p in replacement.Pads(): p.SetNet(nets[p.GetNumber()])
    for number, expected in enumerate(geometry['swio_test_pads_mm'], 1):
        pad = next(p for p in replacement.Pads() if p.GetNumber()==str(number) and p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD)
        assert all(abs(a-b)<1e-5 for a,b in zip(pcbnew.ToMM(pad.GetPosition()), expected)), 'Bare SWIO pad moved'
    for f in children(j2, 'property'):
        if f[1] not in ('Reference', 'Value', 'Footprint'):
            replacement.SetField(str(f[1]), str(f[2])); replacement.GetField(str(f[1])).SetVisible(False)
    for f in replacement.GetFields():
        f.SetLayer(pcbnew.B_Fab); f.SetMirrored(True)
    replacement.Value().SetVisible(False)
    board.Remove(old)
    for item in list(board.GetDrawings()):
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetLayer()==pcbnew.B_SilkS and item.GetText()=='USB HEAD':
            item.SetLayer(pcbnew.F_SilkS); item.SetMirrored(False)
            item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(31.5),pcbnew.FromMM(44.1)))
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetLayer()==pcbnew.B_SilkS and item.GetText() in ('REF', 'SW', 'GND', 'REF ONLY'):
            x,y = pcbnew.ToMM(item.GetPosition())
            if x<12 and y>43: board.Remove(item)
    legend = pcbnew.PCB_TEXT(board)
    legend.SetText('1REF 2SW 3GND'); legend.SetLayer(pcbnew.B_SilkS)
    legend.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(31),pcbnew.FromMM(48.5)))
    legend.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1),pcbnew.FromMM(1)))
    legend.SetTextThickness(pcbnew.FromMM(.15)); legend.SetMirrored(True); board.Add(legend)
    for number, (x, y) in enumerate(geometry['swio_test_pads_mm'], 1):
        target = next(p for p in replacement.Pads() if p.GetNumber()==str(number) and p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH)
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        track.SetEnd(target.GetPosition()); track.SetLayer(pcbnew.B_Cu)
        track.SetWidth(pcbnew.FromMM(.2)); track.SetNet(nets[str(number)])
        board.Add(track)
    for index, (x, y) in enumerate(geometry['mounting_holes_mm'], 1):
        ref = 'H'+str(index)
        f = pcbnew.FootprintLoad(str(output/'Letki.pretty'), MOUNT)
        f.SetFPID(pcbnew.LIB_ID('Letki', MOUNT)); f.SetReference(ref); f.SetValue('M2')
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        key = pcbnew.KIID_PATH(); key.push_back(pcbnew.KIID(str(child(schema,'uuid')[1])))
        inst = next(n for n in children(schema, 'symbol') if prop(n, 'Reference')[2]==ref)
        key.push_back(pcbnew.KIID(str(child(inst,'uuid')[1]))); f.SetPath(key)
        f.SetSheetfile('ledkiv4.kicad_sch'); f.SetSheetname(''); board.Add(f)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output/'ledkiv4.kicad_pcb'), board)
    print('Isolated mounting/SWIO candidate:', output)


if __name__ == '__main__':
    main()
