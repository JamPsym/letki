#!/usr/bin/env python3
"""Build a new editable v4 optical-grid prototype; never edits archived models."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def optical_shapes(App, Part, pitch=5.08, wall=0.8, depth=6.2, face_thickness=0.6):
    """Opaque cell walls contact the PCB at z=0; LED clearance is inside cells."""
    width, height = 8*pitch, 8*pitch+pitch/2
    body = Part.makeBox(width, height, depth, App.Vector(0, 0, 0))
    cutters = [Part.makeBox(pitch-wall, pitch-wall, depth+2,
               App.Vector(col*pitch+wall/2, pitch/2+row*pitch+wall/2, -1))
               for row in range(8) for col in range(8)]
    grid = body.cut(Part.makeCompound(cutters)).removeSplitter()
    face = Part.makeBox(width, height, face_thickness, App.Vector(0, 0, depth))
    return grid, face


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('build/hardware/v4/mechanical'))
    args = parser.parse_args()
    sys.path.append('/usr/lib/freecad/lib')
    import FreeCAD as App
    import Part
    import MeshPart

    args.output.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument('LetkiV4OpticalPrototype')
    params = doc.addObject('App::FeaturePython', 'Dimensions')
    geometry=json.loads((ROOT/'config/v4-mechanics.json').read_text())
    for name, value in [('Pitch', geometry['led_pitch_mm']), ('Wall', geometry['grid_wall_mm']),
                        ('Clearance', 0.0), ('Depth', geometry['grid_depth_mm']),
                        ('FaceThickness', geometry['face_thickness_mm'])]:
        params.addProperty('App::PropertyLength', name, 'Prototype dimensions')
        setattr(params, name, value)
    params.addProperty('App::PropertyString', 'Qualification', 'Prototype dimensions')
    params.Qualification = 'Unprinted optical prototype; LED clearance, brightness and fit unverified'
    grid,face=optical_shapes(App,Part,float(params.Pitch),float(params.Wall),
                            float(params.Depth),float(params.FaceThickness))
    for name, shape, material in [('OpaqueGrid', grid, 'Opaque PLA/PETG'),
                                  ('TranslucentFace', face, 'Translucent white; qualify transmission')]:
        if not shape.isValid() or len(shape.Solids) != 1:
            raise RuntimeError(f'{name}: invalid or disconnected solid')
        obj = doc.addObject('PartDesign::Feature', name)
        obj.Shape = shape
        obj.addProperty('App::PropertyString', 'Material', 'Printing')
        obj.Material = material
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05,
                                     AngularDeflection=0.1, Relative=False)
        if not mesh.isSolid():
            raise RuntimeError(f'{name}: STL is not closed')
        mesh.write(str(args.output / f'{name}.stl'))
        Part.export([obj], str(args.output / f'{name}.step'))
        print(f'{name}: valid solid, closed STL, volume {shape.Volume:.2f} mm³')
    doc.recompute()
    doc.saveAs(str(args.output / 'letkiv4-optical-prototype.FCStd'))
    print('Cell walls now reach the PCB; use v4_mechanics.py for retention and carrier geometry.')


if __name__ == '__main__':
    main()
