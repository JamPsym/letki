#!/usr/bin/env python3
"""Export experimental single-layer FDM paste stencils from the archived v3 PCB.

Run with .tools/kicad-routing-env/bin/python (KiCad, Shapely, FreeCAD).
Never changes the board. Back stencil is mirrored into rear component view.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import pcbnew
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'archive/hw/ledkiv3/ledkiv3.kicad_pcb'
OUT = ROOT / 'archive/hw/ledkiv3/exports/stencil-fdm'
THICKNESS = 0.20


def main():
    sys.path.append('/usr/lib/freecad/lib')
    import FreeCAD as App
    import Part
    import MeshPart
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    board = pcbnew.LoadBoard(str(SOURCE))
    edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    assert len(edges) == 1 and edges[0].GetShapeStr() == 'Rect'
    start, end = edges[0].GetStart(), edges[0].GetEnd()
    x0, y0 = pcbnew.ToMM(start.x), pcbnew.ToMM(start.y)
    width, height = pcbnew.ToMM(end.x-start.x), pcbnew.ToMM(end.y-start.y)
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(source=str(SOURCE.relative_to(ROOT)), source_sha256=source_hash,
                  board_mm=[width, height], thickness_mm=THICKNESS,
                  aperture_policy='About 60% pad area for nominal 0.12 mm equivalent paste volume; IC short dimension 0.25 mm, 0.40 mm webs at 0.65 mm pitch',
                  limitations='Experimental FDM stencil; physical aperture clearance, paste release and alignment unqualified. Flat bed side against PCB. Tape to scrap PCB supports at equal height. Corner L slots mark board corners. Front/back filenames refer to component side. Existing PCB DRC findings are not repaired.',
                  sides={})
    fig, axes = plt.subplots(1, 2, figsize=(11, 6))
    for ax, (name, layer) in zip(axes, [('front-led', pcbnew.F_Paste), ('back-components', pcbnew.B_Paste)]):
        def coordinates(x, y):
            x, y = x-x0, height-(y-y0)
            return (width-x if layer == pcbnew.B_Paste else x), y
        apertures, records = [], []
        for fp in board.GetFootprints():
            for original in fp.Pads():
                if not original.IsOnLayer(layer):
                    continue
                assert tuple(original.GetSolderPasteMargin(layer)) == (0, 0)
                p = pcbnew.PAD(original)
                sx, sy = pcbnew.ToMM(p.GetSize().x), pcbnew.ToMM(p.GetSize().y)
                if fp.GetReference() in ('U1', 'U2'):
                    assert abs(sy-.4) < 1e-6
                    nx, ny = sx*sy*.6/.25, .25
                else:
                    nx, ny = sx*math.sqrt(.6), sy*math.sqrt(.6)
                p.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(nx), pcbnew.FromMM(ny)))
                poly = p.GetEffectivePolygon(layer)
                assert poly.OutlineCount() == 1
                outline = poly.COutline(0)
                points = [coordinates(pcbnew.ToMM(outline.CPoint(i).x), pcbnew.ToMM(outline.CPoint(i).y)) for i in range(outline.PointCount())]
                aperture = Polygon(points)
                assert aperture.is_valid and box(0, 0, width, height).contains(aperture)
                apertures.append(aperture)
                records.append(dict(ref=fp.GetReference(), pad=original.GetNumber(), polygon_mm=points,
                                    area_mm2=aperture.area))
        expected = 128 if layer == pcbnew.F_Paste else 82
        assert len(apertures) == expected, (name, len(apertures))
        merged = unary_union(apertures)
        assert len(merged.geoms) == len(apertures), 'Apertures overlap'
        # L-shaped through slots just outside the four nominal board corners.
        markers = []
        for x, y in [(0, 0), (width, 0), (0, height), (width, height)]:
            dx, dy = (-1 if x == 0 else 1), (-1 if y == 0 else 1)
            pts = [(x+dx*a, y+dy*b) for a, b in [(.4,.4),(3,.4),(3,1), (1,1),(1,3),(.4,3)]]
            markers.append(Polygon(pts))
        sheet = box(-6, -6, width+6, height+6).difference(unary_union(apertures+markers))
        assert sheet.is_valid and sheet.geom_type == 'Polygon'
        def wire(ring):
            return Part.makePolygon([App.Vector(x, y, 0) for x, y in ring.coords])
        solid = Part.Face(wire(sheet.exterior)).extrude(App.Vector(0, 0, THICKNESS))
        cutters = [Part.Face(wire(r)).extrude(App.Vector(0, 0, THICKNESS)) for r in sheet.interiors]
        solid = solid.cut(Part.makeCompound(cutters)).removeSplitter()
        assert solid.isValid() and len(solid.Solids) == 1
        assert abs(solid.Volume-sheet.area*THICKNESS) < 1e-5
        mesh = MeshPart.meshFromShape(Shape=solid, LinearDeflection=.005, AngularDeflection=.1, Relative=False)
        assert mesh.isSolid()
        path = OUT / f'letki-v3-stencil-{name}.stl'
        mesh.write(str(path))
        solid.exportStep(str(path.with_suffix('.step')))
        ax.fill(*sheet.exterior.xy, color='lightgray')
        for r in sheet.interiors:
            ax.fill(*r.xy, color='white')
        ax.plot([0,width,width,0,0], [0,0,height,height,0], '--', color='tab:blue', linewidth=.6)
        ax.set(title=name, aspect='equal', xlabel='mm', ylabel='mm')
        report['sides'][name] = dict(apertures=len(apertures), mirrored=(layer == pcbnew.B_Paste),
            volume_mm3=solid.Volume, mesh_solid=True, min_web_mm=min(a.distance(b) for i,a in enumerate(apertures) for b in apertures[i+1:]),
            stl_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), pads=records)
    fig.tight_layout()
    fig.savefig(OUT / 'preview.png', dpi=180)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    (OUT / 'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: {f:v for f,v in s.items() if f != 'pads'} for k,s in report['sides'].items()}, indent=2))


if __name__ == '__main__':
    main()
