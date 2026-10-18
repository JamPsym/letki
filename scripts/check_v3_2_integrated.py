"""Independent v3.2 routing geometry, invariant and manufacturing gate."""
from pathlib import Path
import argparse,json,hashlib,math,collections,sys
import pcbnew
ap=argparse.ArgumentParser();ap.add_argument('--power-manifest',type=Path,required=True);ap.add_argument('--netlist',type=Path,required=True);ap.add_argument('--labels',type=Path,required=True);ap.add_argument('--in1-manifest',type=Path);ap.add_argument('--board',type=Path,required=True);ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--allow-open',action='store_true');a=ap.parse_args()
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text('{"status":"NOT_PASSED"}\n')
b=pcbnew.LoadBoard(str(a.board));base=pcbnew.LoadBoard(str(a.baseline));mm=lambda v:tuple(round(x,6) for x in pcbnew.ToMM(v));layers=[pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]
def pose(f):return (mm(f.GetPosition()),round(f.GetOrientationDegrees(),6),f.GetLayer(),f.GetValue(),str(f.GetFPID().GetLibNickname()),str(f.GetFPID().GetLibItemName()))
def pads(f):return collections.Counter((p.GetNumber(),mm(p.GetPosition()),round(p.GetOrientationDegrees(),6),p.GetAttribute(),str(p.GetNetname()),mm(p.GetDrillSize()),tuple((l,p.IsOnLayer(l),mm(p.GetSize(l)),int(p.GetShape(l))) for l in layers)) for p in f.Pads())
f={p.GetReference():p for p in b.GetFootprints()};old={p.GetReference():p for p in base.GetFootprints()};assert len(f)==len(list(b.GetFootprints()))==159 and f.keys()==old.keys()
assert b.GetCopperLayerCount()==4
for ref in f:assert pose(f[ref])==pose(old[ref]) and pads(f[ref])==pads(old[ref]),('Changed placement/identity/pad geometry',ref)
pro=json.loads(a.board.with_suffix('.kicad_pro').read_text());bp=json.loads(a.baseline.with_suffix('.kicad_pro').read_text());assert pro['board']['design_settings']==bp['board']['design_settings'];assert pro['erc']==bp['erc']
assert not pro['board']['design_settings'].get('drc_exclusions');assert not any(v=='ignore' for v in pro['board']['design_settings']['rule_severities'].values())
assert a.board.with_suffix('.kicad_dru').read_bytes()==a.baseline.with_suffix('.kicad_dru').read_bytes()
outline=pcbnew.SHAPE_POLY_SET();assert b.GetBoardPolygonOutlines(outline,False) and outline.OutlineCount()==1;bb=outline.BBox();assert mm(bb.GetOrigin())==(0,0) and mm(bb.GetEnd())==(49.6,49.6)
smts=[(fp.GetReference(),p.GetNumber(),p.GetEffectiveShape(l)) for fp in b.GetFootprints() for p in fp.Pads() if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD for l in [pcbnew.F_Cu,pcbnew.B_Cu] if p.IsOnLayer(l)]
tracks=list(b.GetTracks());vias=[t for t in tracks if isinstance(t,pcbnew.PCB_VIA)];hits=[]
for v in vias:
 assert v.GetViaType()==pcbnew.VIATYPE_THROUGH and abs(pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu))-.6)<1e-6 and abs(pcbnew.ToMM(v.GetDrillValue())-.3)<1e-6
 assert v.IsTented(pcbnew.F_Cu) and v.IsTented(pcbnew.B_Cu),'Untented via'
 for ref,pin,shape in smts:
  if pcbnew.SHAPE.Collide(shape,v.GetPosition(),pcbnew.FromMM(.36)):hits.append([v.m_Uuid.AsString(),mm(v.GetPosition()),ref,pin])
# Never turn failed guards into implicit waivers.
assert not hits,('Via/SMT guard',hits)
for t in tracks:
 if not isinstance(t,pcbnew.PCB_VIA):assert pcbnew.ToMM(t.GetWidth())>=.15-1e-6
# No physical duplicate primitives, including duplicated UUIDs or reverse tracks.
ids=[t.m_Uuid.AsString() for t in tracks];assert len(ids)==len(set(ids)),'Duplicate copper UUIDs'
geom=[]
for t in tracks:
 if isinstance(t,pcbnew.PCB_VIA):g=('via',t.GetNetname(),mm(t.GetPosition()),round(pcbnew.ToMM(t.GetDrillValue()),6),round(pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)),6))
 else:g=('track',t.GetNetname(),t.GetLayer(),tuple(sorted([mm(t.GetStart()),mm(t.GetEnd())])),round(pcbnew.ToMM(t.GetWidth()),6))
 geom.append(g)
assert len(geom)==len(set(geom)),'Duplicate physical copper'
pcbnew.ZONE_FILLER(b).Fill(b.Zones());holes=[]
for ref in ['H1','H2','H3','H4']:
 pos=f[ref].GetPosition();r=pcbnew.FromMM(2.45)
 for other,fp in f.items():
  if other.startswith('H'):continue
  for p in fp.Pads():
   for l in layers:
    if p.IsOnLayer(l):assert not pcbnew.SHAPE.Collide(p.GetEffectiveShape(l),pos,r),(ref,other,p.GetNumber())
 for t in tracks:assert not pcbnew.SHAPE.Collide(t.GetEffectiveShape(),pos,r),(ref,t.m_Uuid.AsString())
 for z in b.Zones():
  if z.GetIsRuleArea():continue
  for l in layers:
   if z.IsOnLayer(l):assert not pcbnew.SHAPE.Collide(z.GetFilledPolysList(l),pos,r),(ref,'zone',l)
 holes.append([ref,mm(pos)])
# In1 must remain a return plane unless an exact reviewed exception is added.
in1=[t for t in tracks if not isinstance(t,pcbnew.PCB_VIA) and t.GetLayer()==pcbnew.In1_Cu]
def identity(t):return {'uuid':t.m_Uuid.AsString(),'net':str(t.GetNetname()),'start_mm':list(mm(t.GetStart())),'end_mm':list(mm(t.GetEnd())),'width_mm':round(pcbnew.ToMM(t.GetWidth()),6)}
review=json.loads(a.in1_manifest.read_text()) if a.in1_manifest else {'tracks':[],'review_status':'REVIEWED_CAD_RETURN_PATHS'}
assert review['review_status']=='REVIEWED_CAD_RETURN_PATHS','Plane exceptions lack completed CAD return review'
allowed=review['tracks']
assert sorted([identity(t) for t in in1],key=lambda x:x['uuid'])==sorted(allowed,key=lambda x:x['uuid']),'Unreviewed GND-plane traces'

summary={'status':'PASS_GEOMETRY','source_sha256':hashlib.sha256(a.board.read_bytes()).hexdigest(),'unchanged_footprints':159,'numbered_physical_pads':sum(bool(p.GetNumber()) for fp in f.values() for p in fp.Pads()),'tracks':len(tracks)-len(vias),'ordinary_tented_vias':len(vias),'zones':len(list(b.Zones())),'M2_copper_exclusion_mm':2.45,'via_SMT_guard_mm':.36,'in1_traces':len(in1),'authored_rules_unchanged':True,'scope':'Geometry/identity/manufacturing gate only; native ERC/DRC/opens/parity and physical copper continuity separately required.'}

# Exported schematic terminal identity is independently compared, including
# every physical pad that intentionally shares a reference/pin pair.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from kicad_sexpr import read,child,children
from v3_2_power_contract import snapshot
power=json.loads(a.power_manifest.read_text())
assert power['review_status']=='REVIEWED_CAD_POWER_PATHS'
assert snapshot(b)==power['native_geometry'],'Reviewed power copper changed'
nl=read(a.netlist);nodes={}
for net in children(child(nl,'nets'),'net'):
 for nd in children(net,'node'):nodes[(str(child(nd,'ref')[1]),str(child(nd,'pin')[1]))]=str(child(net,'name')[1])
actual={(r,p.GetNumber()):str(p.GetNetname()) for r,fp in f.items() for p in fp.Pads() if p.GetNumber()}
assert actual==nodes,'Exported schematic terminal mismatch'
expected={1:'/SWDIO',2:'/ROW7_CTRL',3:'/SDA',4:'/SCL',5:'GND',6:'VCC',7:'/RESET_N',8:'/LED_BLANK',9:'/ADDR1',10:'/ROW6_CTRL',11:'/ROW5_CTRL',12:'/UTX',13:'/URX',14:'/ROW8_CTRL',15:'/VTX',16:'/VRX',17:'/ROW2_CTRL',18:'/ROW1_CTRL',19:'/ROW3_CTRL',20:'/ADDR0',21:'/ROW4_CTRL',22:'/ADDR2',23:'/GPIO_SPARE',24:'/SWCLK'}
assert {int(p.GetNumber()):str(p.GetNetname()) for p in f['U1'].Pads()}==expected
pads={r:{int(p.GetNumber()):(mm(p.GetPosition()),str(p.GetNetname())) for p in f[r].Pads()} for r in ['J1','J3','J4','J5']}
for i in range(1,8):
 for r in ['J1','J3']:assert abs(pads[r][i][0][1]-6.2*i)<1e-6
 for r in ['J4','J5']:assert abs(pads[r][i][0][0]-6.2*i)<1e-6
 assert abs(49.6+pads['J3'][i][0][0]-pads['J1'][i][0][0]-2.54)<1e-6
 assert abs(49.6+pads['J4'][i][0][1]-pads['J5'][i][0][1]-2.54)<1e-6
 if i!=5:assert len({pads[r][i][1] for r in pads})==1
assert [pads[r][5][1] for r in ['J1','J3','J4','J5']]==['/UTX_EDGE','/URX_EDGE','/VTX_EDGE','/VRX_EDGE']
# A frozen native label manifest supplements native silk DRC (custom fields
# have historically not always appeared in its item diagnostics).
labels=json.loads(a.labels.read_text())['labels'];objects={x.m_Uuid.AsString():x for x in b.GetDrawings()}
for fp in f.values():objects.update({x.m_Uuid.AsString():x for x in fp.GetFields()})
assert len({x['uuid'] for x in labels})==len(labels)
shapes=[]
for rec in labels:
 t=objects[rec['uuid']];assert t.GetText()==rec['text'] and mm(t.GetPosition())==tuple(rec['xy']) and t.GetTextAngle().AsDegrees()==rec['angle']
 assert t.IsVisible() and t.GetLayer()==pcbnew.B_SilkS and t.IsMirrored()
 assert min(mm(t.GetTextSize()))>=1 and pcbnew.ToMM(t.GetTextThickness())>=.15
 if rec['ref'] in f and rec['ref'].startswith(('R','C','Q','U')):assert rec['text']==(rec['ref'][1:] if rec['ref'].startswith('R') else rec['ref'])
 s=t.GetEffectiveTextShape()
 for prev in shapes:assert not pcbnew.SHAPE.Collide(s,prev,pcbnew.FromMM(.17)),('Silk-label collision',rec['ref'])
 for fp in f.values():
  for pad in fp.Pads():
   if pad.IsOnLayer(pcbnew.B_Cu):assert not pcbnew.SHAPE.Collide(s,pad.GetEffectiveShape(pcbnew.B_Cu),pcbnew.FromMM(.17)),('Silk/pad collision',rec['ref'],fp.GetReference(),pad.GetNumber())
 shapes.append(s)
summary.update(status='PASS_INDEPENDENT_CIRCUIT_GEOMETRY_LABELS',mcu_pins_checked=24,unique_ref_pin_pairs=len(nodes),rear_labels=len(labels),bridge_span_mm=2.54,power_contract_preserved=True)
a.output.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

