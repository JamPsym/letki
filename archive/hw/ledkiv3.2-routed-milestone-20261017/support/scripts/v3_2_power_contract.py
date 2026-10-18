"""Read native power-copper identity; supports the reviewed v3.2 contract."""
import pcbnew
mm=lambda p:[round(x,6) for x in pcbnew.ToMM(p)]
def snapshot(b):
 tracks=[];zones=[]
 for t in b.GetTracks():
  if t.GetNetname() not in ['VCC','GND']:continue
  r={'uuid':t.m_Uuid.AsString(),'net':str(t.GetNetname())}
  if isinstance(t,pcbnew.PCB_VIA):r.update(type='via',xy_mm=mm(t.GetPosition()),diameter_mm=round(pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)),6),drill_mm=round(pcbnew.ToMM(t.GetDrillValue()),6))
  else:r.update(type='track',layer=b.GetLayerName(t.GetLayer()),start_mm=mm(t.GetStart()),end_mm=mm(t.GetEnd()),width_mm=round(pcbnew.ToMM(t.GetWidth()),6))
  tracks.append(r)
 for z in b.Zones():
  if z.GetIsRuleArea() or z.GetNetname() not in ['VCC','GND']:continue
  poly=z.Outline();contours=[]
  for i in range(poly.OutlineCount()):
   c=poly.COutline(i);contours.append([[round(c.CPoint(j).x/1e6,6),round(c.CPoint(j).y/1e6,6)] for j in range(c.PointCount())])
  zones.append({'uuid':z.m_Uuid.AsString(),'net':str(z.GetNetname()),'layers':[b.GetLayerName(l) for l in b.GetEnabledLayers().CuStack() if z.IsOnLayer(l)],'outline_mm':contours})
 return {'tracks_and_vias':sorted(tracks,key=lambda x:x['uuid']),'zones':sorted(zones,key=lambda x:x['uuid'])}
