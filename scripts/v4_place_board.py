#!/usr/bin/env python3
"""Place the unrouted v4 tile and establish its regular LED pitch and edge pads."""
import json
from pathlib import Path
import subprocess
import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
ROOT=Path(__file__).resolve().parents[1];PROJ=ROOT/'hw/ledkiv4';ART=ROOT/'build/hardware/v4'

def pads_footprint(name,count,edge=False):
 n=['footprint',Q(name),['version','20241229'],['generator','pcbnew'],['layer',Q('F.Cu')],['descr',Q('PCB-only solder connection; no purchased connector')],['attr','smd','exclude_from_bom','exclude_from_pos_files','board_only'],
 ['property',Q('Reference'),Q('REF**'),['at','0','-2','0'],['layer',Q('F.Fab')],['effects',['font',['size','0.8','0.8']]]],
 ['property',Q('Value'),Q(name),['at','0','0','0'],['layer',Q('F.Fab')],['effects',['font',['size','0.8','0.8']],['hide','yes']]]]
 for index in range(count):
  # Back-side placement at angle zero mirrors local Y. Define the edge
  # contact numbers upward in the library so the assembled board runs down.
  pos=(0,-index*2.54) if edge else (index*2.54,0)
  n.append(['pad',Q(str(index+1)),'smd','rect' if edge else 'circle',['at',str(pos[0]),str(pos[1])],['size','1.6','1.4' if edge else '1.6'],['layers',Q('F.Cu'),Q('F.Mask')]])
 start_y=-2.54*(count-1)-.95 if edge else -1.05
 end=(1.05,.95) if edge else (2.54*(count-1)+1.05,1.05)
 n.append(['fp_rect',['start','-1.05',str(start_y)],['end',str(end[0]),str(end[1])],
           ['stroke',['width','0.05'],['type','default']],['fill','no'],['layer',Q('F.CrtYd')]])
 write(PROJ/'Letki.pretty'/(name+'.kicad_mod'),n)

def main():
 board=pcbnew.LoadBoard(str(PROJ/'ledkiv4.kicad_pcb'))
 assert not list(board.GetTracks()),'Refusing to reposition a routed board'
 pads_footprint('EdgeBridge_1x07_P2.54mm',7,True);pads_footprint('SWIO_Pads_1x03_P2.54mm',3)
 # Retain the standard HRO copper/drills, but place its opening-edge outline
 # on Fab: the socket sits flush with the PCB edge, where silk cannot print.
 usb=read('/usr/share/kicad/footprints/Connector_USB.pretty/USB_C_Receptacle_HRO_TYPE-C-31-M-12.kicad_mod')
 usb[1]=Q('USB_C_Receptacle_HRO_TYPE-C-31-M-12_Head')
 for item in children(usb,'fp_line'):
  if child(item,'layer')[1]=='F.SilkS' and max(float(child(item,t)[2]) for t in ('start','end'))>3.45:
   child(item,'layer')[1]=Q('F.Fab')
 write(PROJ/'Letki.pretty/USB_C_Receptacle_HRO_TYPE-C-31-M-12_Head.kicad_mod',usb)
 s=read(PROJ/'ledkiv4.kicad_sch')
 for inst in children(s,'symbol'):
  ref=prop(inst,'Reference')[2]
  if ref in ('J1','J3','J2'):
   prop(inst,'Footprint')[2]=Q('Letki:'+('SWIO_Pads_1x03_P2.54mm' if ref=='J2' else 'EdgeBridge_1x07_P2.54mm'))
   child(inst,'in_bom')[1]='no'
  elif ref=='J4':prop(inst,'Footprint')[2]=Q('Letki:USB_C_Receptacle_HRO_TYPE-C-31-M-12_Head')
 write(PROJ/'ledkiv4.kicad_sch',s)
 subprocess.run(['python3',str(ROOT/'scripts/v4_sync_pcb.py')],check=True,stdout=subprocess.DEVNULL)
 board=pcbnew.LoadBoard(str(PROJ/'ledkiv4.kicad_pcb'))
 # Adjust only the new candidate outline; old CAD remains untouched.
 for d in board.GetDrawings():
  if d.GetLayer()==pcbnew.Edge_Cuts:
   assert d.GetShape()==pcbnew.SHAPE_T_RECT
   d.SetStart(pcbnew.VECTOR2I(0,0));d.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(40.64),pcbnew.FromMM(49.27)))
 poses={'U1':(20.32,20.32,0),'U2':(20.32,28.8,0),'U3':(20.32,10.16,0),
 'C1':(25.75,31.3,180),'C3':(14.6,18.045,0),'C6':(26.0,13.085,0),
 'R9':(12.7,13.97,0),'R14':(12.7,23.5,0),
 'SW1':(10.16,4.7,0),'SW2':(10.16,40.64,0),
 'R11':(32.5,4.0,0),'R12':(32.5,6.54,0),'JP1':(36.2,4.0,0),'JP2':(36.2,6.54,0),
 'J1':(39.59,13.97,0),'J3':(1.05,13.97,0),'J2':(5.08,44.45,0),
 'U4':(28.2,17.5,0),'C7':(29.7,20.6,0),'R26':(29.7,15.0,0),
 'R27':(28.2,11.0,0),'R28':(28.2,9.4,0),'R29':(28.2,6.9,0),
 'U6':(28.5,28.5,0),'C8':(31.5,30.0,270),'C9':(26.2,24.8,180),
 'J4':(20.32,46.08,180),'U5':(32.5,43.0,0),'C10':(37.0,43.0,0),
 'R30':(16.0,38.2,0),'R31':(24.64,38.2,0),'R32':(32.5,46.4,0)}
 for f in board.GetFootprints():
  ref=f.GetReference()
  if ref.startswith('D') and ref[1:].isdigit():
   index=int(ref[1:])-1;row,col=divmod(index,8)
   x,y,angle=2.54+5.08*col,40.64-5.08*row,0
  elif ref.startswith('Q'):
   x,y,angle=2.54+5.08*(int(ref[1:])-1),35.56,0
  elif ref.startswith('R') and 1<=int(ref[1:])<=8:
   x,y,angle=7.95,28.0-2.54*(int(ref[1:])-1),0
  elif ref.startswith('R') and 15<=int(ref[1:])<=22:
   x,y,angle=33.02,8.89+2.54*(int(ref[1:])-15),0
  elif ref.startswith('R') and 23<=int(ref[1:])<=25:
   x,y,angle=12.7,25.4+2.54*(int(ref[1:])-23),0
  else:x,y,angle=poses[ref]
  f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
  if not ref.startswith('D') and f.GetLayer()!=pcbnew.B_Cu:f.Flip(f.GetPosition(),False)
  f.SetOrientationDegrees(angle)
  # The VSSOP has 0.175 mm pad spacing. JLCPCB specifies 0.15 mm
  # different-net SMD pad clearance; retain 0.2 mm elsewhere.
  if ref=='U4':f.SetLocalClearance(pcbnew.FromMM(.15))
  for field in f.GetFields():
   field.SetLayer(pcbnew.F_Fab if ref.startswith('D') else pcbnew.B_Fab)
   field.SetMirrored(not ref.startswith('D'))
 pcbnew.SaveBoard(str(PROJ/'ledkiv4.kicad_pcb'),board)
 # Set manufacturing rules deliberately instead of inheriting v3 defaults.
 path=PROJ/'ledkiv4.kicad_pro';project=json.loads(path.read_text());settings=project['board']['design_settings']
 rules=settings['rules'];rules['min_clearance']=.15;rules['min_track_width']=.15;rules['min_via_diameter']=.6;rules['min_through_hole_diameter']=.3;rules['min_copper_edge_clearance']=.2
 path.write_text(json.dumps(project,indent=2)+'\n')
 print('Placed 40.64 x 49.27 mm four-layer tile; uniform 5.08 mm LED pitch continues across horizontal seams.')
 print('PCB-only edge bridges replace the purchased-header footprints; nominal copper setback is 0.25 mm.')
if __name__=='__main__':main()
