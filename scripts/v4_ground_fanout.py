#!/usr/bin/env python3
"""Add short local plane fanouts to unfinished development routing.

Uses KiCad's actual copper shapes for collision checks. The subsequent official
DRC is authoritative; this is a routing helper, not a replacement rule checker.
"""
import argparse
import math
from pathlib import Path
import shutil
import pcbnew

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'build/hardware/v4'
LAYERS=(pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)


def vector(x,y):return pcbnew.VECTOR2I(round(x*1e6),round(y*1e6))
def collide(a,b,clearance):return pcbnew.SHAPE.Collide(a,b,pcbnew.FromMM(clearance))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcb',type=Path)
    parser.add_argument('--output',type=Path,default=ART/'ground-fanout.kicad_pcb')
    parser.add_argument('--net',choices=('GND','VCC'),default='GND')
    parser.add_argument('--plane-layer',choices=('In1.Cu','In2.Cu'),default='In1.Cu')
    args=parser.parse_args();b=pcbnew.LoadBoard(str(args.pcb));ground=b.FindNet(args.net);code=ground.GetNetCode()
    plane_layer=pcbnew.In1_Cu if args.plane_layer=='In1.Cu' else pcbnew.In2_Cu
    pads=[(f.GetReference(),p) for f in b.GetFootprints() for p in f.Pads()]
    copper={layer:[] for layer in LAYERS};holes=[];surface_pads=[]
    for ref,p in pads:
        for layer in LAYERS:
            if p.IsOnLayer(layer):copper[layer].append((p.GetNetCode(),p.GetEffectiveShape(layer),ref))
        if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD:
            surface_pads.extend(p.GetEffectiveShape(layer) for layer in (pcbnew.F_Cu,pcbnew.B_Cu) if p.IsOnLayer(layer))
        if p.GetDrillSize().x:holes.append(p.GetEffectiveHoleShape())
    for t in b.GetTracks():
        for layer in LAYERS:
            if t.IsOnLayer(layer):copper[layer].append((t.GetNetCode(),t.GetEffectiveShape(layer),'track/via'))
        if isinstance(t,pcbnew.PCB_VIA):holes.append(t.GetEffectiveHoleShape())
    gzone=next(z for z in b.Zones() if z.GetNetCode()==code and z.GetLayer()==plane_layer)
    fill=gzone.GetFilledPolysList(plane_layer)
    assert fill.OutlineCount()==1, 'Plane has several islands; resolve their connectivity before automatic fanout'
    b.BuildConnectivity()
    cn=b.GetConnectivity()
    def component(p):
        queue=[p];seen=set()
        while queue:
            i=queue.pop();key=i.m_Uuid.AsString()
            if key in seen:continue
            seen.add(key)
            if i.Type()==pcbnew.PCB_ZONE_T:return True,seen
            queue.extend(cn.GetConnectedItems(i))
        return False,seen
    missing=[];added=0;skipped=0
    # Fan out individual ground pads. Prefer the side facing away from an IC.
    for ref,p in pads:
        if p.GetNetCode()!=code or p.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD:continue
        is_connected,component_ids=component(p)
        if is_connected:skipped+=1;continue
        layer=pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
        px,py=pcbnew.ToMM(p.GetPosition());fp=p.GetParentFootprint();fx,fy=pcbnew.ToMM(fp.GetPosition())
        angle=math.atan2(py-fy,px-fx)
        angles=[angle+i*math.pi/4 for i in (0,1,-1,2,-2,3,-3,4)]+[i*math.pi/16 for i in range(32)]
        anchors=[(p.GetPosition(),layer)]
        # A ground cluster may already have a useful escape trace. Place a
        # plane via on its free end/centre instead of forcing another escape
        # from a densely surrounded IC pad.
        for t in b.GetTracks():
            if isinstance(t,pcbnew.PCB_VIA) or t.GetNetCode()!=code or t.m_Uuid.AsString() not in component_ids:continue
            anchors.extend([(t.GetStart(),t.GetLayer()),(t.GetEnd(),t.GetLayer()),
                            (pcbnew.VECTOR2I((t.GetStart().x+t.GetEnd().x)//2,(t.GetStart().y+t.GetEnd().y)//2),t.GetLayer())])
        candidates=[]
        for origin,route_layer in anchors:
            ax,ay=pcbnew.ToMM(origin)
            candidates.append((ax,ay,origin,route_layer))
            candidates.extend((round(ax+r*math.cos(a),4),round(ay+r*math.sin(a),4),origin,route_layer) for r in (1.2,1.5,1.8,2.2,2.6,3.0) for a in angles)
        selected=None
        for x,y,origin,route_layer in candidates:
            if not(.56<x<40.08 and .56<y<49.17):continue
            vpos=vector(x,y)
            if not fill.Contains(vpos):continue
            circle=pcbnew.SHAPE_CIRCLE(vpos,pcbnew.FromMM(.35))
            drill=pcbnew.SHAPE_CIRCLE(vpos,pcbnew.FromMM(.15))
            if any(collide(shape,circle,.205) for layer in LAYERS for net,shape,_ in copper[layer] if net!=code):continue
            # Keep all drills outside SMT copper/mask even on the same net.
            if any(collide(shape,drill,.21) for shape in surface_pads):continue
            if any(collide(shape,drill,.255) for shape in holes):continue
            shape=pcbnew.SHAPE_SEGMENT(origin,vpos,pcbnew.FromMM(.2))
            if any(collide(obstacle,shape,.205) for net,obstacle,_ in copper[route_layer] if net!=code):continue
            selected=(vpos,shape,circle,drill,origin,route_layer);break
        if selected is None:missing.append((ref,p.GetNumber(),(px,py)));continue
        vpos,shape,circle,drill,origin,route_layer=selected
        if origin!=vpos:
            t=pcbnew.PCB_TRACK(b);t.SetNet(ground);t.SetLayer(route_layer);t.SetWidth(pcbnew.FromMM(.2));t.SetStart(origin);t.SetEnd(vpos);b.Add(t)
        v=pcbnew.PCB_VIA(b);v.SetNet(ground);v.SetPosition(vpos);v.SetWidth(pcbnew.FromMM(.7));v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
        v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED);v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED);b.Add(v)
        copper[route_layer].append((code,shape,'added ground track'))
        for layer in LAYERS:copper[layer].append((code,circle,'added ground via'))
        holes.append(drill);added+=1
    pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(args.output),b)
    shutil.copy2(args.pcb.with_suffix('.kicad_pro'),args.output.with_suffix('.kicad_pro'))
    print('Added',args.net,'fanouts:',added,'already connected:',skipped,'needs manual routing:',missing)


if __name__=='__main__':main()
