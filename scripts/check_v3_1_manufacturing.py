#!/usr/bin/env python3
"""Read-only v3.1 manufacturing, assembly and reviewed power-geometry checks.

Current 146-part revision. Native ERC/DRC/parity, independent multilayer
power connectivity and physical qualification remain separate gates.
"""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew

ROOT=Path(__file__).resolve().parents[1]
mm=lambda p:tuple(pcbnew.ToMM(p))
def near(a,b):return len(a)==len(b) and all(abs(x-y)<2e-6 for x,y in zip(a,b))

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--board',type=Path,default=ROOT/'hw/ledkiv3.1/ledkiv3_1.kicad_pcb')
 ap.add_argument('--output',type=Path,default=ROOT/'build/hardware/v3_1-integration/manufacturing.json')
 ap.add_argument('--labels',type=Path,default=ROOT/'config/v3_1-labels.json')
 ap.add_argument('--power-layout',type=Path,default=ROOT/'config/v3_1-power-layout.json')
 a=ap.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text('{"status":"NOT_PASSED"}\n')
 b=pcbnew.LoadBoard(str(a.board));fps={f.GetReference():f for f in b.GetFootprints()}
 assert len(fps)==len(list(b.GetFootprints()))==146
 assert b.GetCopperLayerCount()==4
 outline=pcbnew.SHAPE_POLY_SET();assert b.GetBoardPolygonOutlines(outline,False) and outline.OutlineCount()==1
 bb=outline.BBox();assert near((*mm(bb.GetOrigin()),*mm(bb.GetEnd())),(0,0,40.64,49.27))
 smd=[(f.GetReference(),p.GetNumber(),p.GetEffectiveShape(l)) for f in b.GetFootprints() for p in f.Pads() if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD for l in [pcbnew.F_Cu,pcbnew.B_Cu] if p.IsOnLayer(l)]
 tracks=list(b.GetTracks());vias=[t for t in tracks if isinstance(t,pcbnew.PCB_VIA)];hits=[]
 for v in vias:
  assert v.GetViaType()==pcbnew.VIATYPE_THROUGH and near((pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)),pcbnew.ToMM(v.GetDrillValue())),(.6,.3))
  assert v.IsTented(pcbnew.F_Cu) and v.IsTented(pcbnew.B_Cu),'Untented via'
  for ref,pad,shape in smd:
   if pcbnew.SHAPE.Collide(shape,v.GetPosition(),pcbnew.FromMM(.36)):hits.append([v.m_Uuid.AsString(),ref,pad])
 assert not hits,('Conservative via/SMT guard',hits)
 for fp in b.GetFootprints():
  for p in fp.Pads():
   bb=p.GetBoundingBox();lo=mm(bb.GetOrigin());hi=mm(bb.GetEnd())
   assert lo[0]>=0 and lo[1]>=0 and hi[0]<=40.64 and hi[1]<=49.27,(fp.GetReference(),'pad outside outline')
 pcbnew.ZONE_FILLER(b).Fill(b.Zones())
 for ref in ['H1','H2']:
  pos=fps[ref].GetPosition();radius=pcbnew.FromMM(2.45)
  for fp in b.GetFootprints():
   if fp.GetReference() in ['H1','H2']:continue
   for p in fp.Pads():
    for l in b.GetEnabledLayers().CuStack():
     if p.IsOnLayer(l):assert not pcbnew.SHAPE.Collide(p.GetEffectiveShape(l),pos,radius),(ref,fp.GetReference(),p.GetNumber())
  for t in tracks:assert not pcbnew.SHAPE.Collide(t.GetEffectiveShape(),pos,radius),(ref,t.m_Uuid.AsString())
  for z in b.Zones():
   if z.GetIsRuleArea():continue
   for l in z.GetLayerSet().Seq():assert not pcbnew.SHAPE.Collide(z.GetFilledPolysList(l),pos,radius),(ref,'zone',l)
 fixed={f'D{i}' for i in range(1,65)}|{'J1','J2','J3','H1','H2'}
 movable=set(fps)-fixed;labels=json.loads(a.labels.read_text());assert {r['reference'] for r in labels['labels']}==movable
 for row in labels['labels']:
  f=fps[row['reference']];assert f.GetLayer()==pcbnew.B_Cu
  field=next(x for x in f.GetFields() if x.m_Uuid.AsString()==row['field_uuid'])
  assert field.IsVisible() and field.GetText()==row['silk']
  assert field.GetLayer()==pcbnew.B_SilkS and b.GetLayerName(field.GetLayer())==row['layer']
  assert near(mm(field.GetPosition()),row['position_mm']) and near(mm(field.GetTextSize()),(1.,1.))
  assert abs(pcbnew.ToMM(field.GetTextThickness())-.15)<1e-6 and field.IsMirrored()
  assert abs(field.GetTextAngle().AsDegrees()-row['angle_degrees'])<1e-6
 graphics={g.m_Uuid.AsString():g for g in b.GetDrawings()}
 for row in labels['leaders']:
  g=graphics[row['uuid']];assert g.GetLayer()==pcbnew.B_SilkS and near(mm(g.GetStart()),row['start_mm']) and near(mm(g.GetEnd()),row['end_mm'])
 for row in labels.get('edge_legends',[]):
  g=graphics[row['uuid']];assert g.GetLayer()==pcbnew.B_SilkS and g.GetText()==row['text']
  assert near(mm(g.GetPosition()),row['position_mm']) and abs(g.GetTextAngle().AsDegrees()-row['angle_degrees'])<1e-6
  bb=g.GetBoundingBox();lo=mm(bb.GetOrigin());hi=mm(bb.GetEnd())
  assert lo[0]>=0 and lo[1]>=0 and hi[0]<=40.64 and hi[1]<=49.27,'Edge legend clipped by board outline'
 contract=json.loads(a.power_layout.read_text());required=contract['required_tracks'];assert required,'Power layout must have explicit reviewed feeds'
 assert contract['physical_qualification']=='PENDING'
 copper={t.m_Uuid.AsString():t for t in tracks if not isinstance(t,pcbnew.PCB_VIA)}
 for item in required:
  t=copper[item['uuid']];assert t.GetNetname()==item['net'] and t.GetNetname() in ['GND','VCC',*(f'/S{i}' for i in range(1,9))]
  assert t.GetLayerName()==item['layer'] and pcbnew.ToMM(t.GetWidth())>=item['minimum_width_mm']-1e-6
  assert near(mm(t.GetStart()),item['start_mm']) and near(mm(t.GetEnd()),item['end_mm'])
 assert any(item['net']=='VCC' and item['minimum_width_mm']>=2 for item in required),'Missing reviewed wide VCC distribution'
 report={'status':'PASS','board_sha256':hashlib.sha256(a.board.read_bytes()).hexdigest(),'footprints':146,'ordinary_tented_vias':len(vias),'via_pad_collisions':hits,'all_via_SMT_guard_radius_mm':.36,'M2_all_layer_copper_keepout_radius_mm':2.45,'rear_assembly_labels_checked':len(labels['labels']),'leader_segments_checked':len(labels['leaders']),'reviewed_power_tracks_checked':len(required),'power_layout_sha256':hashlib.sha256(a.power_layout.read_bytes()).hexdigest(),'scope':'Manufacturing/assembly and exact reviewed power geometry; DRC/parity/multilayer connectivity/IR-drop/thermal and physical validation separate'}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
