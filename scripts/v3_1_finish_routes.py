#!/usr/bin/env python3
"""Finish explicitly named residual nets with native-copper terminal escapes.

Experiments only: preserve the full context, ordinary vias and GND layer.
"""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import time
import pcbnew
import v4_finish_routes as local

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--drc',type=Path,required=True)
p.add_argument('--work',type=Path,required=True)
p.add_argument('--nets',nargs='+',required=True)
p.add_argument('--step',type=float,default=.1,choices=[.05,.1,.2])
p.add_argument('--row-width',type=float,default=.3,choices=[.15,.2,.3])
p.add_argument('--max-anchor-pairs',type=int,default=8)
args=p.parse_args();assert not args.work.exists()
assert all(name not in ['GND','VCC'] and not any(c in name for c in '*?![') for name in args.nets)
shutil.copytree(args.source.parent,args.work/'context')
path=args.work/'context'/args.source.name
authored=path.with_suffix('.kicad_pro').read_bytes()
b=pcbnew.LoadBoard(str(path));local.STEP=args.step
ALL=(pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)
LAYERS=(pcbnew.B_Cu,pcbnew.F_Cu,pcbnew.In2_Cu)
local.LAYERS=LAYERS


def inside_fastener(a,z,width):
    dx,dy=z[0]-a[0],z[1]-a[1];den=dx*dx+dy*dy
    for x,y in [(2.54,46.75),(38.1,46.75)]:
        t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/den)) if den else 0
        if math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)<2.455+width/2:return True
    return False


class Router(local.Router):
    def free(self,n):
        x,y,_=n;x*=local.STEP;y*=local.STEP
        if not(.2+self.width/2<x<40.44-self.width/2 and .2+self.width/2<y<49.07-self.width/2):return False
        if inside_fastener((x,y),(x,y),self.width):return False
        return super().free(n)
    def segment(self,a,z,layer):
        return not inside_fastener(a,z,self.width) and super().segment(a,z,layer)
    def via(self,x,y):
        point=(x*local.STEP,y*local.STEP)
        return not inside_fastener(point,point,.6) and super().via(x,y)


def seed(item):
    uid=item['uuid']
    for t in b.GetTracks():
        if t.m_Uuid.AsString()==uid:return t
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.m_Uuid.AsString()==uid:return pad
    return None


def component(item,goal):
    first=seed(item)
    if first is None:return set(),[]
    cn=b.GetConnectivity();todo=[first];seen=set();points=[]
    while todo:
        node=todo.pop();key=node.m_Uuid.AsString()
        if key in seen or node.Type()==pcbnew.PCB_ZONE_T:continue
        seen.add(key)
        if node.Type()==pcbnew.PCB_VIA_T:
            via=pcbnew.Cast_to_PCB_VIA(node)
            points.append((tuple(pcbnew.ToMM(via.GetPosition())),LAYERS))
        todo.extend(cn.GetConnectedItems(node))
    return seen,sorted(points,key=lambda p:math.dist(p[0],goal))[:8]


def layers(item):
    obj=seed(item)
    if obj is None:raise ValueError('Missing native endpoint '+item['uuid'])
    if obj.Type()==pcbnew.PCB_VIA_T:return LAYERS
    if obj.Type()==pcbnew.PCB_PAD_T:
        pad=pcbnew.Cast_to_PAD(obj)
        return tuple(layer for layer in LAYERS if pad.IsOnLayer(layer))
    return (obj.GetLayer(),)


report=[];started=time.monotonic()
for finding in json.loads(args.drc.read_text())['unconnected_items']:
    a,z=finding['items'];name=re.search(r'\[([^]]+)\]',a['description']).group(1)
    if name not in args.nets:continue
    b.BuildConnectivity()
    start=(a['pos']['x'],a['pos']['y']);end=(z['pos']['x'],z['pos']['y'])
    ai,ap=component(a,end);zi,zp=component(z,start)
    if ai & zi:continue
    width=args.row_width if re.fullmatch('/[KL][1-8]',name) else .15
    r=Router(b,b.FindNet(name),width)
    pairs=sorted(((s,t) for s in [(start,layers(a))]+ap for t in [(end,layers(z))]+zp),key=lambda pair:math.dist(pair[0][0],pair[1][0]))
    route=None;count=0
    for (sp,sl),(ep,el) in pairs[:args.max_anchor_pairs]:
        route,n,se,ee=r.find(sp,sl,ep,el);count+=n
        if route:
            r.publish(sp,ep,route,se,ee);break
    report.append({'net':name,'connected':bool(route),'visited':count,'width_mm':width})
    (args.work/'terminal-routes.json').write_text(json.dumps({'status':'RUNNING','duration_seconds':round(time.monotonic()-started,3),'connections':report},indent=2)+'\n')
    print(name,'connected' if route else 'unresolved',count,flush=True)
pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(path),b)
path.with_suffix('.kicad_pro').write_bytes(authored)
(args.work/'terminal-routes.json').write_text(json.dumps({'duration_seconds':round(time.monotonic()-started,3),'connections':report},indent=2)+'\n')
print(path)
