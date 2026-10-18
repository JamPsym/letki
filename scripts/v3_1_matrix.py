#!/usr/bin/env python3
"""Seed matrix and deliberate power in a new complete working context.

Not a final router or exporter. Native DRC and plane continuity must follow.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import pcbnew

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'hw/ledkiv3.1'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,default=ROOT/'build/hardware/v3_1-integration/matrix-1')
args=parser.parse_args()
assert not args.out.exists(), 'Use a new experiment directory.'
shutil.copytree(SOURCE,args.out/'context')
project=args.out/'context/ledkiv3_1.kicad_pcb'
authored=project.with_suffix('.kicad_pro').read_bytes()
board=pcbnew.LoadBoard(str(project))
assert not list(board.GetTracks()), 'Source contains routing; do not replay matrix creation.'
fps={f.GetReference():f for f in board.GetFootprints()}
ALL=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]
def vector(x,y):return pcbnew.VECTOR2I(round(x*1e6),round(y*1e6))
def position(p):return tuple(pcbnew.ToMM(p.GetPosition()))
def pad(ref,n):return next(p for p in fps[ref].Pads() if p.GetNumber()==str(n))
def track(net,layer,a,b,width):
    if math.dist(a,b)<1e-6:return
    t=pcbnew.PCB_TRACK(board);t.SetNetCode(net);t.SetLayer(layer);t.SetWidth(pcbnew.FromMM(width))
    t.SetStart(vector(*a));t.SetEnd(vector(*b));board.Add(t)
def via(net,x,y):
    v=pcbnew.PCB_VIA(board);v.SetPosition(vector(x,y));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
    v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net)
    v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED);v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
def segment_free(net,layer,a,b,width):
    shape=pcbnew.SHAPE_SEGMENT(vector(*a),vector(*b),pcbnew.FromMM(width))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode()!=net and p.IsOnLayer(layer) and pcbnew.SHAPE.Collide(shape,p.GetEffectiveShape(layer),pcbnew.FromMM(.205)):
                return False
    for t in board.GetTracks():
        if t.GetNetCode()!=net and t.IsOnLayer(layer) and pcbnew.SHAPE.Collide(shape,t.GetEffectiveShape(layer),pcbnew.FromMM(.205)):
            return False
    return True
def via_free(net,x,y):
    if not (.51<x<40.13 and .51<y<48.76):return False
    if any(math.hypot(x-hx,y-46.75)<2.95 for hx in [2.54,38.1]):return False
    pt=vector(x,y)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            for layer in ALL:
                if not p.IsOnLayer(layer):continue
                radius=.505 if p.GetNetCode()!=net else .40
                if pcbnew.SHAPE.Collide(p.GetEffectiveShape(layer),pt,pcbnew.FromMM(radius)):
                    return False
            if p.GetDrillSize().x and pcbnew.SHAPE.Collide(p.GetEffectiveHoleShape(),pt,pcbnew.FromMM(.405)):return False
    for t in board.GetTracks():
        if isinstance(t,pcbnew.PCB_VIA) and math.dist(position(t),(x,y))<.555:return False
        if t.GetNetCode()==net:continue
        for layer in ALL:
            if t.IsOnLayer(layer) and pcbnew.SHAPE.Collide(t.GetEffectiveShape(layer),pt,pcbnew.FromMM(.505)):return False
    return True


report={'matrix':[],'power_vias':[],'unresolved_power':[]}
try:
    # Carry chain power independently of ordinary signal routes. The PTH edge
    # contacts themselves reach both planes. Wide rear legs avoid front LEDs.
    vcc=board.FindNet('VCC').GetNetCode()
    for ref in ['J3','J1']:
        px=position(pad(ref,1))[0]
        x=1.9 if ref=='J3' else 38.74
        for number in [1,2]:
            y=position(pad(ref,number))[1]
            track(vcc,pcbnew.B_Cu,(px,y),(x,y),1.2)
        track(vcc,pcbnew.B_Cu,(x,1.5),(x,12.7),1.2)
        assert via_free(vcc,x,1.5),(ref,'power-bus via')
        via(vcc,x,1.5)
    track(vcc,pcbnew.F_Cu,(1.9,1.5),(38.74,1.5),2.0)
    for row in range(8):
        cathodes=[pad(f'D{row*8+c+1}',1) for c in range(8)]
        # Mid-cell buses leave usable via corridors on BOTH sides of each
        # LED row. Inset the right branch around the symmetric PTH contact.
        net=cathodes[0].GetNetCode();y=40.64-5.08*row;by=round(y+2.54,6)
        assert all(p.GetNetCode()==net for p in cathodes)
        xs=[position(p)[0] for p in cathodes[:-1]]+[37.4]
        # Find a rear-accessible ordinary via without moving any LED.
        buses=[2.54]+[round(2.54+5.08*c-1.9,6) for c in range(1,8)]
        vx=next((x*.25 for x in range(14,150) if all(abs(x*.25-bus)>=.755 for bus in buses)
                 and via_free(net,x*.25,by)),None)
        assert vx is not None,('row via',row)
        via(net,vx,by);xs=sorted(set(xs+[vx]))
        for a,b in zip(xs,xs[1:]):track(net,pcbnew.F_Cu,(a,by),(b,by),.3)
        for index,p in enumerate(cathodes):
            bx=37.4 if index==7 else position(p)[0]
            track(net,pcbnew.F_Cu,position(p),(bx,by),.3)
        report['matrix'].append({'row':row+1,'via':[vx,by]})
    for col in range(8):
        # First column is inset around the all-layer edge contacts. Its front
        # leads turn between LED pads instead of crossing the cathode pad.
        bx=2.54 if col==0 else round(2.54+5.08*col-1.9,6)
        ys=[];net=None
        for row in range(8):
            p=pad(f'D{row*8+col+1}',2);px,py=position(p);net=p.GetNetCode()
            offsets=([0,1.6,1.2,2.0,.8,2.4,2.2,1.8,1.4,1.0,2.8,-.6,-1.0,-1.8,-2.2]
                     if col==0 else [0,.6,1.2,1.6,2.0,2.4,-.6,-1.0,-1.8,-2.2])
            shifts=[0,-.2,.2,-.4,.4,-.6,.6,.8,1.0,1.2,-1.2,1.6,-1.6,2.0,-2.0,2.4,-2.4,2.8,-2.8,3.2,-3.2]
            xs=([.64] if col==0 else [])+[bx+d for d in shifts]
            target=None;lead=None
            for d in offsets:
                for vx in xs:
                    vx,vy=round(vx,6),round(py+d,6)
                    if not via_free(net,vx,vy):continue
                    if not segment_free(net,pcbnew.In2_Cu,(vx,vy),(bx,vy),.3):continue
                    for points in [[(px,py),(vx,vy)],[(px,py),(px,vy),(vx,vy)],[(px,py),(vx,py),(vx,vy)]]:
                        if all(segment_free(net,pcbnew.F_Cu,a,z,.3) for a,z in zip(points,points[1:])):
                            target=(vx,vy);lead=points;break
                    if target:break
                if target:break
            assert target is not None,('column LED via',col,row,px,py)
            vx,vy=target
            via(net,vx,vy);ys.append(vy)
            for a,z in zip(lead,lead[1:]):track(net,pcbnew.F_Cu,a,z,.3)
            track(net,pcbnew.In2_Cu,(vx,vy),(bx,vy),.3)
        ys=sorted(ys)
        for a,b in zip(ys,ys[1:]):track(net,pcbnew.In2_Cu,(bx,a),(bx,b),.5)
        report['matrix'].append({'column':col+1,'bus_x':bx,'via_y':ys})
        print('Matrix column',col+1,'complete',flush=True)
    # Decoupling supply leads are fixed short routes, not arbitrary autoroutes.
    for ref,pin,cap in [('U1',9,'C3'),('U2',16,'C1')]:
        a,c=pad(ref,pin),pad(cap,2)
        assert a.GetNetCode()==c.GetNetCode() and abs(position(a)[1]-position(c)[1])<2e-6
        assert segment_free(a.GetNetCode(),pcbnew.B_Cu,position(a),position(c),.3)
        track(a.GetNetCode(),pcbnew.B_Cu,position(a),position(c),.3)
    # Give supply/return pins their own nearby ordinary via and short branch.
    # Keep every through via clear of SMD lands, including its own net.
    power_pads=[p for f in board.GetFootprints() for p in f.Pads()
                if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD and p.GetNetname() in ['VCC','GND']]
    power_pads.sort(key=lambda p:(not p.GetParentFootprint().GetReference().startswith(('U','C','Q')),p.GetParentFootprint().GetReference(),p.GetNumber()))
    for p in power_pads:
        ref=p.GetParentFootprint().GetReference();net=p.GetNetCode();x,y=position(p)
        width=.5 if ref.startswith('Q') and p.GetNetname()=='VCC' else .3
        # Skip a chip's VDD if its directly connected bypass pad gets the via.
        if (ref,p.GetNumber()) in [('U1','9'),('U2','16')]:continue
        offsets=sorted([(dx*.2,dy*.2) for dx in range(-12,13) for dy in range(-12,13)
                        if .8<=math.hypot(dx*.2,dy*.2)<=2.5],key=lambda q:(q[0]*q[0]+q[1]*q[1],abs(q[1]),abs(q[0])))
        offsets=([(0,3.015-y),(-.2,3.015-y),(.2,3.015-y)]+offsets) if ref=='C4' and p.GetNumber()=='2' else offsets
        target=next(((round(x+dx,6),round(y+dy,6)) for dx,dy in offsets
                     if via_free(net,x+dx,y+dy) and segment_free(net,pcbnew.B_Cu,(x,y),(x+dx,y+dy),width)),None)
        if target is None:
            report['unresolved_power'].append([ref,p.GetNumber(),p.GetNetname(),x,y]);continue
        via(net,*target);track(net,pcbnew.B_Cu,(x,y),target,width)
        report['power_vias'].append([ref,p.GetNumber(),p.GetNetname(),*target])
    for name,layer in [('GND',pcbnew.In1_Cu),('VCC',pcbnew.In2_Cu)]:
        zone=pcbnew.ZONE(board);zone.SetNet(board.FindNet(name));zone.SetLayer(layer)
        zone.SetLocalClearance(pcbnew.FromMM(.2));zone.SetMinThickness(pcbnew.FromMM(.15))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetThermalReliefGap(pcbnew.FromMM(.3));zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(.3))
        outline=zone.Outline();outline.NewOutline()
        for x,y in [(.25,.25),(40.39,.25),(40.39,49.02),(.25,49.02)]:outline.Append(pcbnew.FromMM(x),pcbnew.FromMM(y))
        board.Add(zone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    report['status']='seed complete; official DRC/open nets/plane qualification pending'
finally:
    pcbnew.SaveBoard(str(project),board);project.with_suffix('.kicad_pro').write_bytes(authored)
    (args.out/'matrix-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(project)
print('Power vias:',len(report['power_vias']),'Unresolved power:',report['unresolved_power'])
