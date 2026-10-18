"""Read-only independent audit of exact MPN pins and rectangular seams."""
from pathlib import Path
import sys,json,hashlib,math,pcbnew
sys.path.insert(0,str(Path(__file__).resolve().parent))
from kicad_sexpr import *
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'hw/ledkiv3.2';ART=ROOT/'build/hardware/v3_2-study';ART.mkdir(parents=True,exist_ok=True);b=pcbnew.LoadBoard(str(P/'ledkiv3_2.kicad_pcb'));f={fp.GetReference():fp for fp in b.GetFootprints()}
expected={1:'/SWDIO',2:'/ROW7_CTRL',3:'/SDA',4:'/SCL',5:'GND',6:'VCC',7:'/RESET_N',8:'/LED_BLANK',9:'/ADDR1',10:'/ROW6_CTRL',11:'/ROW5_CTRL',12:'/UTX',13:'/URX',14:'/ROW8_CTRL',15:'/VTX',16:'/VRX',17:'/ROW2_CTRL',18:'/ROW1_CTRL',19:'/ROW3_CTRL',20:'/ADDR0',21:'/ROW4_CTRL',22:'/ADDR2',23:'/GPIO_SPARE',24:'/SWCLK'}
actual={int(p.GetNumber()):str(p.GetNetname()) for p in f['U1'].Pads()};assert actual==expected,(actual,expected)
assert len(list(f['U1'].Pads()))==24
assert len(list(b.GetTracks()))==len(list(b.Zones()))==0
assert b.GetCopperLayerCount()==4
# Exact netlist parity of every physical numbered terminal, plus none missing.
nl=read(ART/'v32.net');nodes={}
for n in children(child(nl,'nets'),'net'):
 for nd in children(n,'node'):nodes[(str(child(nd,'ref')[1]),str(child(nd,'pin')[1]))]=str(child(n,'name')[1])
actualnodes={(r,str(p.GetNumber())):str(p.GetNetname()) for r,fp in f.items() for p in fp.Pads() if p.GetNumber()}
assert actualnodes==nodes
# Seams have the same longitudinal positions/pad numbers and 2.54mm wire span.
pads={r:{int(p.GetNumber()):(tuple(pcbnew.ToMM(p.GetPosition())),str(p.GetNetname())) for p in f[r].Pads()} for r in ['J1','J3','J4','J5']}
for i in range(1,8):
 for r in ['J1','J3']:assert abs(pads[r][i][0][1]-6.2*i)<1e-6
 for r in ['J4','J5']:assert abs(pads[r][i][0][0]-6.2*i)<1e-6
 assert abs((49.6+pads['J3'][i][0][0])-pads['J1'][i][0][0]-2.54)<1e-6
 assert abs((49.6+pads['J4'][i][0][1])-pads['J5'][i][0][1]-2.54)<1e-6
 if i!=5:assert len({pads[r][i][1] for r in pads})==1
assert pads['J1'][5][1]=='/UTX_EDGE' and pads['J3'][5][1]=='/URX_EDGE'
assert pads['J4'][5][1]=='/VTX_EDGE' and pads['J5'][5][1]=='/VRX_EDGE'
# Check retained native layer-specific lands and new mechanical holes.
for r in ['J1','J3','J4','J5']:
 for p in f[r].Pads():
  assert tuple(pcbnew.ToMM(p.GetDrillSize()))==(.8,.8)
  for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu]:
   assert tuple(pcbnew.ToMM(p.GetSize(layer)))==(1.4,1.4)
   assert p.GetShape(layer)==pcbnew.PAD_SHAPE_CIRCLE
  assert tuple(pcbnew.ToMM(p.GetSize(pcbnew.B_Cu)))==(2.04,1.6)
  assert p.GetShape(pcbnew.B_Cu)==pcbnew.PAD_SHAPE_OVAL
for r,pos in {'H1':(6.2,6.2),'H2':(43.4,6.2),'H3':(6.2,43.4),'H4':(43.4,43.4)}.items():
 assert tuple(pcbnew.ToMM(f[r].GetPosition()))==pos
 ps=list(f[r].Pads());assert len(ps)==1 and ps[0].GetAttribute()==pcbnew.PAD_ATTRIB_NPTH
 assert tuple(pcbnew.ToMM(ps[0].GetDrillSize()))==(2.2,2.2)
# Distinct physical pixels stay on one 6.2mm lattice across tile boundaries.
pts=set()
for ty in range(3):
 for tx in range(4):
  for i in range(1,65):
   x,y=pcbnew.ToMM(f['D'+str(i)].GetPosition());assert f['D'+str(i)].GetLayer()==pcbnew.F_Cu
   pts.add((round(x+49.6*tx,4),round(y+49.6*ty,4)))
assert len(pts)==4*3*64
xs=sorted({x for x,y in pts});ys=sorted({y for x,y in pts});assert all(abs(q-p-6.2)<1e-6 for seq in [xs,ys] for p,q in zip(seq,seq[1:]))
# Source predecessor and authored rule floors remain unchanged.
manifest=json.loads((ROOT/'config/v3_2-study.json').read_text())['predecessor_hashes'];src=ROOT/'hw/ledkiv3.1'
assert all(hashlib.sha256((src/r).read_bytes()).hexdigest()==h for r,h in manifest.items())
base=json.loads((src/'ledkiv3_1.kicad_pro').read_text());new=json.loads((P/'ledkiv3_2.kicad_pro').read_text());assert base['board']['design_settings']==new['board']['design_settings'];assert base['erc']==new['erc']
summary={'status':'PASS_STATIC_UNROUTED','footprints':len(f),'unique_reference_pin_pairs':len(actualnodes),'physical_numbered_pads':sum(bool(p.GetNumber()) for fp in f.values() for p in fp.Pads()),'mcu_pins_checked':24,'tracks_and_vias':0,'zones':0,'copper_layers':4,'pixel_pitch_mm':6.2,'tile_mm':[49.6,49.6],'seam_span_mm':2.54,'rectangular_lattice_checked':[4,3],'baseline_files_unchanged':len(manifest),'authored_board_and_erc_rules_preserved':True,'qualifications':'No connectivity/routing, firmware, physical, fabrication or bootloader qualification.'}
(ART/'independent-audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
