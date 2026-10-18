#!/usr/bin/env python3
"""Remove obsolete disconnected wire fragments and improve v4 annotation spacing."""
from collections import defaultdict
from copy import deepcopy
import math
from pathlib import Path
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
ROOT=Path(__file__).resolve().parents[1];PATH=ROOT/'hw/ledkiv4/ledkiv4.kicad_sch'
s=read(PATH);libs={n[1]:n for n in children(child(s,'lib_symbols'),'symbol')}
def point(node):return tuple(round(float(v),6) for v in child(node,'at')[1:3])
def positioned(inst,pin):
 origin=child(inst,'at');theta=math.radians(float(origin[3]));at=child(pin,'at');x,y=map(float,at[1:3])
 return round(float(origin[1])+math.cos(theta)*x+math.sin(theta)*y,6),round(float(origin[2])+math.sin(theta)*x-math.cos(theta)*y,6)
pin_points={};all_pins=set()
for inst in children(s,'symbol'):
 lib=libs[child(inst,'lib_id')[1]]
 for unit in children(lib,'symbol'):
  for pin in children(unit,'pin'):
   p=positioned(inst,pin);all_pins.add(p)
   pin_points.setdefault(p,(inst,pin))
# Wire fragments detached by the driver changes have no electrical pins.
graph=defaultdict(set);wire_ends={}
for wire in children(s,'wire'):
 a,b=[tuple(round(float(v),6) for v in n[1:]) for n in children(child(wire,'pts'),'xy')]
 graph[a].add(b);graph[b].add(a);wire_ends[id(wire)]=(a,b)
orphans=set();seen=set()
for start in graph:
 if start in seen:continue
 pending=[start];cluster=set()
 while pending:
  p=pending.pop()
  if p in cluster:continue
  cluster.add(p);pending.extend(graph[p]-cluster)
 seen|=cluster
 if not(cluster&all_pins):orphans|=cluster
for wire in list(children(s,'wire')):
 if wire_ends[id(wire)][0] in orphans:s.remove(wire)
for name in ('label','junction'):
 for node in list(children(s,name)):
  p=point(node)
  on_wire=False
  for a,b in wire_ends.values():
   cross=(p[0]-a[0])*(b[1]-a[1])-(p[1]-a[1])*(b[0]-a[0])
   if abs(cross)<.00001 and min(a[0],b[0])<=p[0]<=max(a[0],b[0]) and min(a[1],b[1])<=p[1]<=max(a[1],b[1]):
    on_wire=True;break
  if p in orphans or (name=='label' and not on_wire and p not in all_pins):s.remove(node)
# Respect the symbol library's field placements. Long BOM values are hidden.
for inst in children(s,'symbol'):
 definition=libs[child(inst,'lib_id')[1]];origin=child(inst,'at');angle=float(origin[3])
 if angle==0:
  for name in ('Reference','Value'):
   template=prop(definition,name);target=prop(inst,name)
   if not template or not target:continue
   at=child(template,'at');child(target,'at')[1:]=[str(float(origin[1])+float(at[1])),str(float(origin[2])-float(at[2])),at[3]]
   effect=child(target,'effects');target.remove(effect);target.append(deepcopy(child(template,'effects')))
 ref=prop(inst,'Reference')[2]
 if ref.startswith(('D','U','Q')):
  effect=child(prop(inst,'Value'),'effects')
  if not child(effect,'hide'):effect.append(['hide','yes'])
# Move solder jumpers out of the title block along with all their annotations.
for index in (1,2):
 inst=next(n for n in children(s,'symbol') if prop(n,'Reference')[2]=='JP'+str(index))
 old=point(inst);new=(345.44,175.26+25.4*(index-1));dx,dy=new[0]-old[0],new[1]-old[1]
 endpoints={positioned(inst,p) for unit in children(libs[child(inst,'lib_id')[1]],'symbol') for p in children(unit,'pin')}
 for tag in ('label','global_label'):
  for node in children(s,tag):
   if point(node) in endpoints:
    at=child(node,'at');at[1]=str(float(at[1])+dx);at[2]=str(float(at[2])+dy)
 at=child(inst,'at');at[1:3]=list(map(str,new))
 for field in children(inst,'property'):
  at=child(field,'at');at[1]=str(float(at[1])+dx);at[2]=str(float(at[2])+dy)
# Recompute pin points after the moves, then give signal labels short wire stubs.
pin_points={}
for inst in children(s,'symbol'):
 for unit in children(libs[child(inst,'lib_id')[1]],'symbol'):
  for pin in children(unit,'pin'):pin_points.setdefault(positioned(inst,pin),(inst,pin))
import uuid
for tag in ('label','global_label'):
 for node in list(children(s,tag)):
  p=point(node)
  if p not in pin_points:continue
  inst,pin=pin_points[p]
  theta=math.radians(float(child(inst,'at')[3]));pa=math.radians(float(child(pin,'at')[3]))
  lx,ly=-math.cos(pa),-math.sin(pa)
  dx=math.cos(theta)*lx+math.sin(theta)*ly;dy=math.sin(theta)*lx-math.cos(theta)*ly
  end=(round(p[0]+5.08*dx,6),round(p[1]+5.08*dy,6))
  s.append(['wire',['pts',['xy',str(p[0]),str(p[1])],['xy',str(end[0]),str(end[1])]],['stroke',['width','0'],['type','default']],['uuid',Q(str(uuid.uuid4()))]])
  at=child(node,'at');at[1:3]=list(map(str,end))
  effects=child(node,'effects');effects[:]=[v for v in effects if not(isinstance(v,list) and v[0]=='justify')]
  effects.append(['justify','right' if dx<-.1 else 'left','bottom'])
  if len(node[1])>7:child(child(effects,'font'),'size')[1:]=['0.9','0.9']
write(PATH,s)
print('Removed orphaned fragments, spaced pin labels, hid long BOM values and moved jumpers clear of title block.')
