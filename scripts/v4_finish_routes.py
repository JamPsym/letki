#!/usr/bin/env python3
"""Finish residual development-PCB connections with a local clearance-aware grid.

Uses real KiCad copper shapes and through-via constraints. Always run official
DRC after this helper; it does not establish fabrication readiness.
"""
import argparse
import heapq
import json
import math
from pathlib import Path
import re
import shutil
import pcbnew

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'build/hardware/v4'
LAYERS=(pcbnew.B_Cu,pcbnew.F_Cu,pcbnew.In2_Cu)
ALL=(pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu)
STEP=.2


def vector(x,y):return pcbnew.VECTOR2I(round(x*1e6),round(y*1e6))
def collide(a,b,c):return pcbnew.SHAPE.Collide(a,b,pcbnew.FromMM(c))


class Router:
    def __init__(self,board,net,width):
        self.board=board;self.net=net;self.width=width
        self.buckets={l:{} for l in ALL};self.pads=[];self.holes=[]
        self.free_cache={};self.via_cache={};self.edge_cache={}
        def add(layer,shape):
            box=shape.BBox();a=pcbnew.ToMM(box.GetOrigin());z=pcbnew.ToMM(box.GetEnd())
            for x in range(math.floor((a[0]-.8)/2),math.floor((z[0]+.8)/2)+1):
                for y in range(math.floor((a[1]-.8)/2),math.floor((z[1]+.8)/2)+1):
                    self.buckets[layer].setdefault((x,y),[]).append(shape)
        for f in board.GetFootprints():
            for p in f.Pads():
                for l in ALL:
                    if p.IsOnLayer(l) and p.GetNetCode()!=net.GetNetCode():add(l,p.GetEffectiveShape(l))
                if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD:
                    self.pads.extend(p.GetEffectiveShape(l) for l in (pcbnew.B_Cu,pcbnew.F_Cu) if p.IsOnLayer(l))
                if p.GetDrillSize().x:self.holes.append(p.GetEffectiveHoleShape())
        for t in board.GetTracks():
            for l in ALL:
                if t.IsOnLayer(l) and t.GetNetCode()!=net.GetNetCode():add(l,t.GetEffectiveShape(l))
            if isinstance(t,pcbnew.PCB_VIA):self.holes.append(t.GetEffectiveHoleShape())
    def nearby(self,layer,x,y):return self.buckets[layer].get((math.floor(x/2),math.floor(y/2)),())
    def free(self,n):
        if n in self.free_cache:return self.free_cache[n]
        x,y,l=n;x*=STEP;y*=STEP
        p=vector(x,y)
        ok=.2+self.width/2<x<40.44-self.width/2 and .2+self.width/2<y<49.53-self.width/2
        if ok:ok=not any(pcbnew.SHAPE.Collide(s,p,pcbnew.FromMM(self.width/2+.205)) for s in self.nearby(l,x,y))
        self.free_cache[n]=ok;return ok
    def segment(self,a,b,layer):
        shape=pcbnew.SHAPE_SEGMENT(vector(*a),vector(*b),pcbnew.FromMM(self.width))
        seen=set()
        for x in range(math.floor((min(a[0],b[0])-.4)/2),math.floor((max(a[0],b[0])+.4)/2)+1):
            for y in range(math.floor((min(a[1],b[1])-.4)/2),math.floor((max(a[1],b[1])+.4)/2)+1):
              for s in self.buckets[layer].get((x,y),()):
                key=id(s)
                if key in seen:continue
                seen.add(key)
                if collide(s,shape,.205):return False
        return True
    def via(self,x,y):
        key=x,y
        if key in self.via_cache:return self.via_cache[key]
        px,py=x*STEP,y*STEP;p=vector(px,py)
        ok=.505<px<40.135 and .505<py<49.225
        if ok:ok=not any(pcbnew.SHAPE.Collide(s,p,pcbnew.FromMM(.505)) for l in ALL for s in self.nearby(l,px,py))
        if ok:ok=not any(pcbnew.SHAPE.Collide(s,p,pcbnew.FromMM(.36)) for s in self.pads)
        if ok:ok=not any(pcbnew.SHAPE.Collide(s,p,pcbnew.FromMM(.405)) for s in self.holes)
        self.via_cache[key]=ok;return ok
    def anchors(self,point,layers):
        x,y=point;cx,cy=round(x/STEP),round(y/STEP);result=[]
        for l in layers:
            for dx in range(-12,13):
                for dy in range(-12,13):
                    n=cx+dx,cy+dy,l;target=n[0]*STEP,n[1]*STEP
                    if self.free(n) and self.segment(point,target,l):result.append((math.dist(point,target),n,None))
            # Fine-pitch pads need a straight escape before the path can
            # turn onto the coarser grid without brushing adjacent pads.
            for distance in (.8,1.2,1.6,2.0):
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    elbow=x+dx*distance,y+dy*distance
                    if not self.segment(point,elbow,l):continue
                    ex,ey=round(elbow[0]/STEP),round(elbow[1]/STEP)
                    for gx in range(-2,3):
                        for gy in range(-2,3):
                            n=ex+gx,ey+gy,l;target=n[0]*STEP,n[1]*STEP
                            if self.free(n) and self.segment(elbow,target,l):result.append((distance+math.dist(elbow,target),n,elbow))
        return result
    def find(self,start,start_layers,end,end_layers):
        starts=self.anchors(start,start_layers);ends=self.anchors(end,end_layers)
        if not starts or not ends:return None,0,None,None
        targets={}
        for d,n,elbow in sorted(ends,reverse=True,key=lambda a:a[0]):targets[n]=(d,elbow)
        queue=[];g={};prev={};origin={};counter=0
        def h(n):return math.hypot(n[0]*STEP-end[0],n[1]*STEP-end[1])
        for d,n,elbow in starts:
            if d>=g.get(n,float('inf')):continue
            g[n]=d;prev[n]=None;origin[n]=elbow;heapq.heappush(queue,(d+h(n),counter,n));counter+=1
        closed=set()
        while queue and len(closed)<250000:
            _,_,n=heapq.heappop(queue)
            if n in closed:continue
            closed.add(n)
            if n in targets:
                route=[];p=n
                while p is not None:route.append(p);p=prev[p]
                route.reverse();return route,len(closed),origin[route[0]],targets[n][1]
            x,y,l=n;neighbors=[]
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                m=x+dx,y+dy,l
                if not self.free(m):continue
                key=n,m
                if key not in self.edge_cache:self.edge_cache[key]=self.segment((x*STEP,y*STEP),(m[0]*STEP,m[1]*STEP),l)
                if self.edge_cache[key]:neighbors.append((m,STEP*math.hypot(dx,dy)))
            if self.via(x,y):
                neighbors.extend(((x,y,ll),2.5) for ll in LAYERS if ll!=l and self.free((x,y,ll)))
            for m,d in neighbors:
                ng=g[n]+d
                if ng>=g.get(m,float('inf')):continue
                g[m]=ng;prev[m]=n;heapq.heappush(queue,(ng+h(m),counter,m));counter+=1
        return None,len(closed),None,None
    def publish(self,start,end,route,start_elbow=None,end_elbow=None):
        def track(a,b,l):
            if math.dist(a,b)<.00001:return
            t=pcbnew.PCB_TRACK(self.board);t.SetNet(self.net);t.SetLayer(l);t.SetWidth(pcbnew.FromMM(self.width));t.SetStart(vector(*a));t.SetEnd(vector(*b));self.board.Add(t)
        points=[(n[0]*STEP,n[1]*STEP,n[2]) for n in route]
        if start_elbow is not None:track(start,start_elbow,points[0][2]);start=start_elbow
        if end_elbow is not None:track(end_elbow,end,points[-1][2]);end=end_elbow
        track(start,points[0][:2],points[0][2]);track(points[-1][:2],end,points[-1][2])
        # Coalesce straight grid runs before adding copper.
        begin=points[0];last=points[0];direction=None
        for p in points[1:]:
            if p[2]!=last[2]:
                track(begin[:2],last[:2],last[2])
                v=pcbnew.PCB_VIA(self.board);v.SetNet(self.net);v.SetPosition(vector(*p[:2]));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
                v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED);v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED);self.board.Add(v)
                begin=p;last=p;direction=None;continue
            d=round(p[0]-last[0],6),round(p[1]-last[1],6)
            if direction is not None and d!=direction:track(begin[:2],last[:2],last[2]);begin=last
            direction=d;last=p
        track(begin[:2],last[:2],last[2])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcb',type=Path);parser.add_argument('drc',type=Path)
    parser.add_argument('--output',type=Path,default=ART/'finished-development.kicad_pcb')
    parser.add_argument('--limit',type=int,default=100)
    parser.add_argument('--allow-ground-layer',action='store_true',help='Development only: check plane continuity after using In1.Cu')
    parser.add_argument('--prioritize',default='',help='Comma-separated net names to route first')
    parser.add_argument('--step',type=float,default=.2,choices=(.2,.1,.05),help='Routing grid in mm')
    args=parser.parse_args()
    global LAYERS,STEP
    STEP=args.step
    if args.allow_ground_layer:LAYERS=(*LAYERS,pcbnew.In1_Cu)
    b=pcbnew.LoadBoard(str(args.pcb));report=json.loads(args.drc.read_text())
    count=0
    b.BuildConnectivity();cn=b.GetConnectivity()
    def component_points(item,netname,goal):
        objects={t.m_Uuid.AsString():t for t in b.GetTracks()}
        seed=objects.get(item['uuid'])
        if seed is None:
            match=re.search(r'Pad (\S+) .* of (\S+) on',item['description'])
            if match:
                seed=next(p for f in b.GetFootprints() if f.GetReference()==match[2] for p in f.Pads() if p.GetNumber()==match[1])
        if seed is None:return []
        todo=[seed];seen=set();points=[]
        while todo:
            node=todo.pop();key=node.m_Uuid.AsString()
            if key in seen or node.Type()==pcbnew.PCB_ZONE_T:continue
            seen.add(key)
            if node.Type()==pcbnew.PCB_VIA_T:
                p=pcbnew.ToMM(pcbnew.Cast_to_PCB_VIA(node).GetPosition());points.append((p,LAYERS))
            todo.extend(cn.GetConnectedItems(node))
        return sorted(points,key=lambda p:math.dist(p[0],goal))[:8]
    priority=args.prioritize.split(',') if args.prioritize else []
    opens=sorted(report['unconnected_items'],key=lambda v:next((i for i,name in enumerate(priority) if '['+name+']' in v['items'][0]['description']),len(priority)))
    for open_ in opens[:args.limit]:
        a,z=open_['items']
        name=re.search(r'\[([^]]+)\]',a['description']).group(1)
        info=b.FindNet(name);assert info,name
        def layers(item):
            if 'Via ' in item['description']:return LAYERS
            for text,l in [('B.Cu',pcbnew.B_Cu),('F.Cu',pcbnew.F_Cu),('In2.Cu',pcbnew.In2_Cu),('In1.Cu',pcbnew.In1_Cu)]:
                if 'on '+text in item['description']:return (l,)
            raise ValueError('Endpoint layer unsupported: '+item['description'])
        start=a['pos']['x'],a['pos']['y'];end=z['pos']['x'],z['pos']['y']
        width=.5 if name=='/USB_VBUS' else (.3 if name=='VCC' else .2)
        r=Router(b,info,width)
        starts=[(start,layers(a))]+component_points(a,name,end)
        ends=[(end,layers(z))]+component_points(z,name,start)
        attempts=sorted(((aa,zz) for aa in starts for zz in ends),key=lambda pair:math.dist(pair[0][0],pair[1][0]))
        route=None;visited=0
        for (sp,sl),(ep,el) in attempts:
            route,v,start_elbow,end_elbow=r.find(sp,sl,ep,el);visited+=v
            if route:start,end=sp,ep;break
        print(name,'routed' if route else 'unresolved','visited',visited,flush=True)
        if route:r.publish(start,end,route,start_elbow,end_elbow);count+=1
    pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(args.output),b)
    shutil.copy2(args.pcb.with_suffix('.kicad_pro'),args.output.with_suffix('.kicad_pro'))
    rules=args.pcb.with_suffix('.kicad_dru')
    if rules.exists():shutil.copy2(rules,args.output.with_suffix('.kicad_dru'))
    print('Connections added:',count,'output:',args.output)


if __name__=='__main__':main()
