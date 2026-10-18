#!/usr/bin/env python3
"""Generate the removable v4 optical assembly and modular printed carrier.

Coordinates are PCB front-view x/y, front surface z=0. Nominal CAD checks do
not qualify real print tolerances, screw retention, optics or assembled PCBs.
"""
import argparse
import json
from pathlib import Path
import sys

from v4_diffuser import optical_shapes, solder_hoods

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tiles',type=int,default=4,choices=range(1,5))
    parser.add_argument('--output',type=Path,default=ROOT/'build/hardware/v4/mechanical')
    parser.add_argument('--pcb-step',type=Path,help='Optional KiCad populated STEP for component-envelope interference checks')
    parser.add_argument('--config',type=Path,default=ROOT/'config/v4-mechanics.json')
    parser.add_argument('--name',default='letkiv4',help='Output model basename, e.g. letkiv4_1')
    args=parser.parse_args()
    geometry=json.loads(args.config.read_text())
    sys.path.append('/usr/lib/freecad/lib')
    import FreeCAD as App
    import Part
    import MeshPart
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    width,height,thickness=geometry['board_mm']
    pitch=geometry['led_pitch_mm'];depth=geometry['grid_depth_mm']
    face_thickness=geometry['face_thickness_mm'];grid_height=8*pitch+pitch/2
    beam_back=geometry['carrier_back_mm'];beam_front=geometry['carrier_beam_front_mm']
    bottom=geometry['carrier_bottom_mm'];holes=geometry['mounting_holes_mm']
    total_width=args.tiles*width
    def box(x,y,z,dx,dy,dz):return Part.makeBox(dx,dy,dz,App.Vector(x,y,z))
    def bore(x,y,z,r,h):return Part.makeCylinder(r,h,App.Vector(x,y,z))
    def fuse(shapes):
        result=shapes[0]
        for s in shapes[1:]:result=result.fuse(s)
        return result.removeSplitter()
    grid,face=optical_shapes(App,Part,pitch,geometry['grid_wall_mm'],depth,face_thickness)
    grid_parts=[grid]
    for x,y in holes:
        # Ears support the bezel at the same height as the translucent plate.
        grid_parts.append(box(x-2.5,grid_height-.1,0,5,height-grid_height+.1,depth))
        grid_parts.append(box(x-2.5,grid_height,depth,5,height-grid_height,face_thickness))
    grid=fuse(grid_parts)
    for x,y in holes:grid=grid.cut(bore(x,y,-1,1.2,depth+face_thickness+2))
    wire=geometry.get('edge_wire')
    edge_points=wire['left_holes_mm']+wire['right_holes_mm'] if wire else []
    grid=solder_hoods(grid,geometry,App,Part)
    bezel_z=depth+face_thickness;bezel_thickness=.8
    bezel=box(0,0,bezel_z,width,height,bezel_thickness)
    bezel=bezel.cut(box(.8,pitch/2+geometry['grid_wall_mm']/2,bezel_z-1,
                         width-1.6,8*pitch-geometry['grid_wall_mm'],bezel_thickness+2))
    bezel_parts=[bezel]
    slot_back=-(thickness+.25)
    for x,_ in holes:
        # Hooks sit outside the top edge. Their rear lips avoid carrier rests.
        bezel_parts.extend([
            box(x-1.6,-1.2,slot_back-.8,3.2,1.1,bezel_z+bezel_thickness-slot_back+.8),
            box(x-1.6,-1.2,bezel_z,3.2,1.7,bezel_thickness),
            box(x-1.6,-1.2,slot_back-.8,3.2,2.5,.8)])
    bezel=fuse(bezel_parts)
    for x,y in holes:bezel=bezel.cut(bore(x,y,bezel_z-1,1.2,bezel_thickness+2))
    bezel=bezel.removeSplitter()

    # Rear frame is open over the matrix and edge contacts. Crossmembers stay
    # 4.2 mm behind the PCB rear; the SWIO/USB area has a full cable opening.
    base_parts=[box(0,-2,beam_back,total_width,5,beam_front-beam_back),
                box(0,41,beam_back,total_width,bottom-41,beam_front-beam_back)]
    for tile in range(args.tiles):
        offset=tile*width
        base_parts.append(box(offset+width/2-1.5,0,beam_back,3,43.5,beam_front-beam_back))
    carrier=fuse(base_parts)
    for tile in range(args.tiles):
        offset=tile*width
        carrier=carrier.cut(box(offset+5.6,43.5,beam_back-1,21.4,bottom-43.5+1,beam_front-beam_back+2))
    carrier_parts=[carrier]
    for tile in range(args.tiles):
        offset=tile*width
        for x,y in holes:
            carrier_parts.append(bore(offset+x,y,beam_front,2.3,-thickness-beam_front))
        for x in (10.16,30.48):
            carrier_parts.append(box(offset+x-1.6,.2,beam_front,3.2,1.4,-thickness-beam_front))
    carrier=fuse(carrier_parts)
    for tile in range(args.tiles):
        for x,y in holes:
            carrier=carrier.cut(bore(tile*width+x,y,beam_back+1.2,.85,-thickness-beam_back))
    # Printed splice plates join sections without inserting a gap between PCBs.
    # Use two plates and four M2 x 6 screws at each section joint.
    for x in (2.5,total_width-2.5):
        for y in (.5,52.1):carrier=carrier.cut(bore(x,y,beam_back-1,.85,beam_front-beam_back+2))
    carrier=carrier.removeSplitter()
    splice=box(-5,-2.5,beam_back-2,10,5,2)
    for x in (-2.5,2.5):splice=splice.cut(bore(x,0,beam_back-3,1.15,4))
    splice=splice.removeSplitter()

    pcb=box(0,0,-thickness,width,height,thickness)
    for x,y in holes:pcb=pcb.cut(bore(x,y,-thickness-1,1.1,thickness+2))
    for index in range(3):pcb=pcb.cut(bore(7.62+index*1.25,46.75,-thickness-1,.3,thickness+2))
    for x,y in edge_points:pcb=pcb.cut(bore(x,y,-thickness-1,wire['hole_mm']/2,thickness+2))
    pcb=pcb.removeSplitter()
    # Manufacturer body envelopes, independent of the footprint courtyard.
    # These are clearance aids, not complete electronic or cable models.
    swio_envelope=box(6.12,45.6,-thickness-4.2,5.5,3.2,4.2)
    usb_envelope=box(14.3,41.8,-thickness-3.3,12.04,8,3.3)
    doc=App.newDocument('LetkiV4MechanicalPrototype')
    notes=doc.addObject('App::FeaturePython','Dimensions')
    notes.addProperty('App::PropertyString','Qualification')
    notes.Qualification='UNPRINTED PROTOTYPE: nominal CAD fit only; qualify actual PCB, printing, screws, optics and cables'
    notes.addProperty('App::PropertyString','CoordinateSystem')
    notes.CoordinateSystem='PCB front view: origin top-left, x right, y down, z positive in front; PCB front z=0'
    notes.addProperty('App::PropertyInteger','Tiles');notes.Tiles=args.tiles
    for name,value in [('BoardWidth',width),('BoardHeight',height),('BoardThickness',thickness),
                       ('GridDepth',depth),('FaceThickness',face_thickness),('TopSlotHeight',-slot_back)]:
        notes.addProperty('App::PropertyLength',name);setattr(notes,name,value)
    for name,value in [('BoardScrews',geometry['board_screws']),('CarrierJointScrews',geometry['carrier_join_screws'])]:
        notes.addProperty('App::PropertyString',name);setattr(notes,name,value)

    def add(name,shape,material,colour):
        assert shape.isValid() and len(shape.Solids)==1,(name,'invalid or disconnected solid')
        obj=doc.addObject('PartDesign::Feature',name);obj.Shape=shape
        obj.addProperty('App::PropertyString','Material');obj.Material=material
        if obj.ViewObject:obj.ViewObject.ShapeColor=colour
        return obj
    shapes={'OpaqueGrid':grid,'TranslucentFace':face,'FrontBezel':bezel,
            f'Carrier{args.tiles}Tiles':carrier,'CarrierSplice':splice}
    print_report={}
    for name,shape in shapes.items():
        printable=shape.copy()
        # Print grid and bezel front down; carrier rear down. Normalize STL
        # coordinates so slicers receive a part resting on the build plate.
        if name in ('OpaqueGrid','FrontBezel'):printable.rotate(App.Vector(),App.Vector(1,0,0),180)
        bb=printable.BoundBox;printable.translate(App.Vector(-bb.XMin,-bb.YMin,-bb.ZMin))
        bb=printable.BoundBox
        assert max(bb.XLength,bb.YLength,bb.ZLength)<=180,'Part does not fit the A1 mini bed envelope'
        mesh=MeshPart.meshFromShape(Shape=printable,LinearDeflection=.05,AngularDeflection=.1,Relative=False)
        assert mesh.isSolid(),(name,'STL is not closed')
        mesh.write(str(output/(name+'.stl')))
        Part.export([printable],str(output/(name+'.step')))
        print_report[name]={'print_dimensions_mm':[round(v,3) for v in (bb.XLength,bb.YLength,bb.ZLength)],
                            'solid_volume_mm3':round(shape.Volume,3),'closed_stl':True}
    add('Carrier',carrier,'Opaque PETG/PLA; retention and temperature require qualification',(.16,.18,.2))
    for tile in range(args.tiles):
        offset=App.Vector(tile*width,0,0)
        placed={}
        for name,shape,material,colour in [
            ('PCB',pcb,'Nominal PCB outline/hole gauge; components omitted',(.12,.42,.18)),
            ('OpaqueGrid',grid,'Opaque PLA/PETG',(.12,.13,.15)),
            ('TranslucentFace',face,'Translucent white; qualify transmission',(.95,.92,.85)),
            ('FrontBezel',bezel,'Opaque PLA/PETG',(.12,.13,.15))]:
            copy=shape.copy();copy.translate(offset);placed[name]=copy
            add(name+str(tile+1),copy,material,colour)
        for tp in geometry.get('testpoints',[]):
            x,y=tp['xy_mm']
            copper=bore(tile*width+x,y,-thickness-.035,.5,.035)
            add(f'{tp["ref"]}_Tile{tile+1}',copper,'Illustrative rear testpoint copper',(.8,.6,.18))
        for name in ('OpaqueGrid','FrontBezel','TranslucentFace'):
            assert placed[name].common(placed['PCB']).Volume<1e-5,(name,'intersects nominal PCB')
            assert placed[name].common(carrier).Volume<1e-5,(name,'intersects carrier')
        assert placed['OpaqueGrid'].common(placed['TranslucentFace']).Volume<1e-5,'Face overlaps grid'
        assert placed['FrontBezel'].common(placed['TranslucentFace']).Volume<1e-5,'Face overlaps bezel'
        assert placed['FrontBezel'].common(placed['OpaqueGrid']).Volume<1e-5,'Grid overlaps bezel'
        for name,envelope in [('SWIO',swio_envelope),('USB',usb_envelope)]:
            shape=envelope.copy();shape.translate(offset)
            assert shape.common(carrier).Volume<1e-5,(name,'carrier blocks connector envelope')
        assert carrier.common(placed['PCB']).Volume<1e-5,'Carrier intersects nominal PCB'
        for x,y in edge_points:
            front_solder=bore(tile*width+x,y,0,wire['front_solder_radius_mm'],wire['front_solder_height_mm'])
            assert front_solder.common(placed['OpaqueGrid']).Volume<1e-5,'Front wire solder blocks the grid'
        for tp in geometry.get('testpoints',[]):
            x,y=tp['xy_mm']
            probe=bore(tile*width+x,y,beam_back-1,.65,-thickness-beam_back+1)
            assert probe.common(carrier).Volume<1e-5,(tp['ref'],'carrier blocks probe access')
    for suffix,y in [('Top',.5),('Bottom',52.1)]:
        shape=splice.copy();shape.translate(App.Vector(total_width,y,0))
        add('Splice'+suffix,shape,'Opaque PLA/PETG; two plates per carrier joint',(.4,.42,.45))
    bridge_count=0
    if wire:
        for tile in range(args.tiles-1):
            z=-thickness-wire['rear_bridge_standoff_mm'];r=wire['wire_mm']/2
            for index,(left_point,right_point) in enumerate(zip(wire['left_holes_mm'],wire['right_holes_mm'])):
                assert abs(left_point[1]-right_point[1])<1e-5,'Facing staple holes differ in height'
                left=tile*width+right_point[0];right=(tile+1)*width+left_point[0];y=left_point[1]
                bridge=Part.makeCylinder(r,right-left,App.Vector(left,y,z),App.Vector(1,0,0))
                for x in (left,right):
                    leg=bore(x,y,z,r,wire['front_protrusion_mm']-z)
                    bridge=bridge.fuse(leg)
                bridge=bridge.removeSplitter()
                assert bridge.common(carrier).Volume<1e-5,'Carrier blocks wire bridge'
                for near_tile in (tile,tile+1):
                    local_grid=grid.copy();local_grid.translate(App.Vector(near_tile*width,0,0))
                    local_pcb=pcb.copy();local_pcb.translate(App.Vector(near_tile*width,0,0))
                    assert bridge.common(local_grid).Volume<1e-5,'Wire bridge blocks grid'
                    assert bridge.common(local_pcb).Volume<1e-5,'Wire bridge misses a PCB hole'
                add(f'WireBridge{tile+1}_{index+1}',bridge,'0.5 mm tinned copper; conservative straight bend envelope',(.7,.7,.75))
                bridge_count+=1
    populated_report=None
    if args.pcb_step:
        populated=Part.Shape();populated.read(str(args.pcb_step))
        assert populated.isValid() and populated.Solids,'Invalid populated STEP'
        # KiCad STEP uses +y upwards and PCB rear z=0. Mirror y, then move
        # its front surface to our optical datum. Body envelopes are labelled
        # in the source library; solder and cable bends are not modelled.
        transform=App.Matrix();transform.A22=-1;transform.A34=-thickness
        populated=populated.transformGeometry(transform)
        assert populated.isValid()
        overlaps={name:round(populated.common(shape).Volume,8)
                  for name,shape in [('OpaqueGrid',grid),('TranslucentFace',face),
                                     ('FrontBezel',bezel),('Carrier',carrier)]}
        assert all(v<1e-5 for v in overlaps.values()),('Populated STEP intersects printed parts',overlaps)
        populated_report={'source':str(args.pcb_step),'intersection_volumes_mm3':overlaps,
                          'scope':'KiCad package models and conservative connector body envelopes; solder, contact details and cable bends omitted'}
    # All 64 light-cell separators reach z=0; no shared under-grid air gap.
    assert abs(grid.BoundBox.ZMin)<1e-6
    doc.recompute()
    doc.saveAs(str(output/f'{args.name}-mechanics-{args.tiles}-tiles.FCStd'))
    report={'status':'NOMINAL_CAD_PASS_PHYSICAL_QUALIFICATION_PENDING','tiles':args.tiles,
            'grid_floor_z_mm':0,'pcb_front_z_mm':0,
            'pcb_holes_mm':holes,'edge_wire_holes_mm':edge_points,'wire_bridge_count':bridge_count,'solder_hoods':{'enclosed':True,'count':len(edge_points),'wall_mm':wire['grid_hood_wall_mm'],'roof_mm':wire['grid_hood_roof_mm']},'probe_points_checked':len(geometry.get('testpoints',[])),'frame_pitch_mm':width,
            'nominal_pcb_connector_and_optical_intersections':0,
            'parts':print_report,'board_screws_per_tile':2,'splice_plates_per_joint':2,
            'splice_screws_per_joint':4,
            'populated_step_check':populated_report,
            'remaining':['print tolerances/warp','PCB thickness and header pin protrusion/hole fill',
                         'screw retention and insertion loads','actual cable overmould/bend clearance',
                         'face transmission, light leakage and legibility']}
    (output/f'mechanics-{args.tiles}-tiles.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
