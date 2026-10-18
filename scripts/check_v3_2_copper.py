#!/usr/bin/env python3
"""Independent multilayer power connectivity from freshly filled native copper.

Each zone polygon is a separate node; only PTH pads/vias intrinsically join
layers. Near-touch tolerance is explicit and native DRC remains authoritative.
No source is written. The erosion gauge is not an electrical/thermal solver.
"""
import argparse,hashlib,json,time
from pathlib import Path
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--board',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--all-nets',action='store_true')
a=ap.parse_args();start=time.perf_counter()
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text('{"status":"NOT_PASSED"}\n')
import pcbnew
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from shapely import make_valid,STRtree
b=pcbnew.LoadBoard(str(a.board))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
layers=list(b.GetEnabledLayers().CuStack());tolerance_mm=.000005

def geometry(poly):
 def points(c):return [(c.CPoint(j).x/1e6,c.CPoint(j).y/1e6) for j in range(c.PointCount())]
 return [make_valid(Polygon(points(poly.COutline(i)),[points(poly.CHole(i,h)) for h in range(poly.HoleCount(i))])) for i in range(poly.OutlineCount())]

def native_copper(item,layer):
 p=pcbnew.SHAPE_POLY_SET();item.TransformShapeToPolygon(p,layer,0,100,pcbnew.ERROR_INSIDE)
 return unary_union(geometry(p))

results={}
for net in (sorted({str(p.GetNetname()) for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname()}) if a.all_nets else ['GND','VCC']):
 nodes=[];geoms={l:[] for l in layers};indices={l:[] for l in layers}
 def add(label,parts):
  idx=len(nodes);nodes.append(label)
  for layer,g in parts.items():
   if g.is_empty:continue
   geoms[layer].append(g);indices[layer].append(idx)
 for fp in b.GetFootprints():
  for p in fp.Pads():
   if p.GetNetname()==net:add(fp.GetReference()+'.'+p.GetNumber(),{l:native_copper(p,l) for l in layers if p.IsOnLayer(l)})
 for t in b.GetTracks():
  if t.GetNetname()!=net:continue
  label=('via' if isinstance(t,pcbnew.PCB_VIA) else 'track')+':'+t.m_Uuid.AsString()
  add(label,{l:native_copper(t,l) for l in layers if t.IsOnLayer(l)})
 zones=[]
 for z in b.Zones():
  if z.GetIsRuleArea() or z.GetNetname()!=net:continue
  for l in layers:
   if not z.IsOnLayer(l):continue
   polygons=geometry(z.GetFilledPolysList(l))
   for i,g in enumerate(polygons):add('zone:'+pcbnew.LayerName(l)+':'+str(i),{l:g})
   cores=unary_union(polygons).buffer(-.25);cores=list(cores.geoms) if hasattr(cores,'geoms') else [cores];cores=sorted(cores,key=lambda g:-g.area)
   gateways=[]
   for t in b.GetTracks():
    if not isinstance(t,pcbnew.PCB_VIA) or t.GetNetname()!=net:continue
    xy=tuple(pcbnew.ToMM(t.GetPosition()));pt=Point(xy)
    gateways.append({'xy_mm':xy,'filled_polygon':[i for i,g in enumerate(polygons) if g.covers(pt)],'half_mm_core':[i for i,g in enumerate(cores) if g.covers(pt)]})
   zones.append({'layer':pcbnew.LayerName(l),'polygons':len(polygons),'area_mm2':sum(g.area for g in polygons),'eroded_half_mm_regions':len(cores),'via_gateways':gateways})
 parent=list(range(len(nodes)))
 def find(x):
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 def join(x,y):parent[find(x)]=find(y)
 for l in layers:
  tree=STRtree(geoms[l])
  for i,g in enumerate(geoms[l]):
   for j in tree.query(g,predicate='dwithin',distance=tolerance_mm):
    if j>i:join(indices[l][i],indices[l][j])
 clusters={}
 for i,label in enumerate(nodes):clusters.setdefault(find(i),[]).append(label)
 results[net]={'connected_components':len(clusters),'components':sorted(clusters.values(),key=lambda items:-len(items)),'zones':zones}
report={'status':'PASS' if all(r['connected_components']==1 for r in results.values()) else 'FAIL','board_sha256':hashlib.sha256(a.board.read_bytes()).hexdigest(),'scope':'Native polygons independently joined across copper layers; DRC/IR-drop/thermal and physical qualification separate','fresh_refill':True,'near_touch_tolerance_mm':tolerance_mm,'polygon_max_error_mm':.0001,'nets':results,'whole_script_seconds':time.perf_counter()-start}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'nets':{n:r['connected_components'] for n,r in results.items()},'seconds':report['whole_script_seconds']}))
raise SystemExit(0 if report['status']=='PASS' else 1)
