#!/usr/bin/env python3
"""Check the fresh v3.1 placement, without adding or accepting routing.

Native ERC/DRC/parity and the independent circuit audit remain separate.
The saved routed predecessor protects the agreed mechanical interfaces.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def mm(point):
    return tuple(pcbnew.ToMM(point))


def courtyard(fp):
    layer = pcbnew.F_CrtYd if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd
    fp.BuildCourtyardCaches()
    poly = fp.GetCourtyard(layer)
    assert poly.OutlineCount(), ('Missing courtyard', fp.GetReference())
    # Separate loop boxes preserve the seven individual edge-contact courts.
    # The circular M2 outline is conservatively bounded, not treated as a disc.
    boxes = []
    for i in range(poly.OutlineCount()):
        box = poly.COutline(i).BBox()
        boxes.append((*mm(box.GetOrigin()), *mm(box.GetEnd())))
    return boxes


def pad_geometry(fp):
    return sorted([
        (p.GetNumber(), mm(p.GetPosition()), mm(p.GetDrillSize()),
         p.GetAttribute(), p.GetOrientationDegrees(),
         tuple((layer, mm(p.GetSize(layer)), p.GetShape(layer))
               for layer in [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
               if p.IsOnLayer(layer)), p.GetLocalZoneConnection())
        for p in fp.Pads()
    ], key=repr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, default=ROOT/'hw/ledkiv3.1/ledkiv3_1.kicad_pcb')
    parser.add_argument('--baseline', type=Path, default=ROOT/'archive/hw/ledkiv3.1-routed-before-placement-20261015/ledkiv3_1.kicad_pcb')
    parser.add_argument('--output', type=Path, default=ROOT/'build/hardware/v3_1-placement-20261015/placement-audit.json')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('{"status":"NOT_PASSED"}\n')
    board = pcbnew.LoadBoard(str(args.board.resolve()))
    before = pcbnew.LoadBoard(str(args.baseline.resolve()))
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    old = {f.GetReference(): f for f in before.GetFootprints()}
    fixed = {f'D{i}' for i in range(1,65)} | {'J1','J2','J3','H1','H2'}
    assert len(fps) == len(list(board.GetFootprints())) == 146
    assert not list(board.GetTracks()), 'Placement phase must have no tracks or vias'
    assert not list(board.Zones()), 'Placement phase must have no copper zones'
    assert board.GetCopperLayerCount() == 4
    for ref in fixed:
        f, original = fps[ref], old[ref]
        assert (mm(f.GetPosition()), f.GetOrientationDegrees(), f.GetLayer()) == (
            mm(original.GetPosition()), original.GetOrientationDegrees(), original.GetLayer()), ref
        assert pad_geometry(f) == pad_geometry(original), ('Fixed pad geometry changed',ref)
        assert f.IsLocked(), ('Fixed placement should be locked',ref)
    outline = pcbnew.SHAPE_POLY_SET()
    assert board.GetBoardPolygonOutlines(outline, False) and outline.OutlineCount() == 1
    bounds = outline.BBox()
    assert (*mm(bounds.GetOrigin()), *mm(bounds.GetEnd())) == (0.,0.,40.64,49.27)
    assert all(fps[r].GetLayer() == pcbnew.B_Cu for r in set(fps)-fixed)
    courts = {r: courtyard(f) for r,f in fps.items()}
    minimum_gap = None
    pairs = 0
    for i,(ref,fp) in enumerate(fps.items()):
        for ref2,other in list(fps.items())[i+1:]:
            if fp.GetLayer() != other.GetLayer():
                continue
            gap = min(math.hypot(max(a[0]-b[2],b[0]-a[2],0.),
                                 max(a[1]-b[3],b[1]-a[3],0.))
                      for a in courts[ref] for b in courts[ref2])
            assert gap >= .05-1e-5, ('Courtyards too close',ref,ref2,gap)
            minimum_gap = gap if minimum_gap is None else min(minimum_gap,gap)
            pairs += 1
    # Keep the complete fastener exclusion, including rear copper and bodies.
    for name in ['H1','H2']:
        centre = fps[name].GetPosition()
        for ref,fp in fps.items():
            if ref in ['H1','H2']:
                continue
            for pad in fp.Pads():
                for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]:
                    if pad.IsOnLayer(layer):
                        assert not pcbnew.SHAPE.Collide(pad.GetEffectiveShape(layer),centre,pcbnew.FromMM(2.45)), (name,ref,pad.GetNumber())
    hole_counts = {'PTH':0, 'NPTH':0}
    for fp in fps.values():
        for pad in fp.Pads():
            if pad.GetDrillSize().x:
                hole_counts['NPTH' if pad.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH else 'PTH'] += 1
            bb = pad.GetBoundingBox()
            lo,hi = mm(bb.GetOrigin()),mm(bb.GetEnd())
            assert lo[0] >= 0 and lo[1] >= 0 and hi[0] <= 40.64 and hi[1] <= 49.27, (fp.GetReference(),'pad outside board')
    assert hole_counts == {'PTH':17,'NPTH':2}
    for ref in set(fps)-fixed:
        f = fps[ref].GetField('AssemblyLabel')
        assert f and f.IsVisible() and f.IsMirrored() and f.GetLayer()==pcbnew.B_SilkS, ref
        assert mm(f.GetTextSize()) == (1.,1.) and abs(pcbnew.ToMM(f.GetTextThickness())-.15)<1e-6, ref
    report = {
        'status':'PLACEMENT_PASS; UNROUTED',
        'board_sha256':hashlib.sha256(args.board.read_bytes()).hexdigest(),
        'baseline_sha256':hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        'footprints':146, 'fixed_locked_footprints':len(fixed), 'rear_movable_parts':77,
        'agreed_padstacks_and_positions_preserved':True,
        'tracks':0, 'vias':0, 'copper_zones':0, 'hole_counts':hole_counts,
        'same_side_courtyard_pairs_checked':pairs,
        'minimum_courtyard_gap_mm':round(minimum_gap,6),
        'courtyard_method':'Conservative per-loop native bounding boxes; no aggregation across edge-contact loops',
        'M2_all_layer_pad_keepout_radius_mm':2.45,
        'silkscreen':'77 rear assembly labels,1mm/0.15mm; R numbers use R=# legend',
        'scope':'Placement/nominal geometry only; native findings, routing, power integrity and physical qualification remain separate',
    }
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
