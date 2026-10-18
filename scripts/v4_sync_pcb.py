#!/usr/bin/env python3
"""Synchronize the unrouted v4 candidate from its schematic using real libraries.

Refuses to discard any routing. Retains placement/orientation of existing parts.
"""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as E
import pcbnew
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
ROOT=Path(__file__).resolve().parents[1];PROJ=ROOT/'hw/ledkiv4';ART=ROOT/'build/hardware/v4'

def main():
 path=PROJ/'ledkiv4.kicad_pcb';ast=read(path)
 assert not any(children(ast,k) for k in ('segment','arc','via')), 'PCB has routing; refusing to replace footprints'
 schema=read(PROJ/'ledkiv4.kicad_sch');instances={prop(n,'Reference')[2]:n for n in children(schema,'symbol')}
 previous=pcbnew.LoadBoard(str(path))
 old={f.GetReference():f for f in previous.GetFootprints() if f.GetReference()}
 poses={ref:(f.GetPosition(),f.GetOrientationDegrees(),f.GetLayer()) for ref,f in old.items()}
 mechanics=[]
 for f in previous.GetFootprints():
  if not f.GetReference():mechanics.append(pcbnew.Cast_to_FOOTPRINT(f.Duplicate(False)))
 ast[:]=[v for v in ast if not(isinstance(v,list) and v[0]=='footprint')]
 write(ART/'pcb-without-footprints.kicad_pcb',ast)
 board=pcbnew.LoadBoard(str(ART/'pcb-without-footprints.kicad_pcb'))
 subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(ART/'netlist.xml'),str(PROJ/'ledkiv4.kicad_sch')],check=True,stdout=subprocess.DEVNULL)
 netlist=E.parse(ART/'netlist.xml').getroot();fps={}
 for c in netlist.find('components'):
  ref=c.attrib['ref'];libname,name=c.findtext('footprint').split(':')
  directory=PROJ/'Letki.pretty' if libname=='Letki' else Path('/usr/share/kicad/footprints')/(libname+'.pretty')
  fp=pcbnew.FootprintLoad(str(directory),name);assert fp,ref
  board.Add(fp);fp.SetFPID(pcbnew.LIB_ID(libname,name))
  fp.SetReference(ref);fp.SetValue(c.findtext('value'))
  if ref in poses:pos,angle,layer=poses[ref]
  else:
   index=len(fps)-len(poses)
   pos=pcbnew.VECTOR2I(pcbnew.FromMM(35+5*(index%7)),pcbnew.FromMM(90+3*(index//7)))
   angle,layer=0,pcbnew.B_Cu
  fp.SetPosition(pos)
  if layer==pcbnew.B_Cu:fp.Flip(pos,False)
  fp.SetOrientationDegrees(angle)
  inst=instances[ref]
  for field in children(inst,'property'):
   if field[1] not in ('Reference','Value','Footprint'):
    fp.SetField(str(field[1]),str(field[2]));fp.GetField(str(field[1])).SetVisible(False)
  for field in fp.GetFields():
   field.SetMirrored(layer==pcbnew.B_Cu)
   field.SetLayer(pcbnew.B_Fab if layer==pcbnew.B_Cu else pcbnew.F_Fab)
  fp.Value().SetVisible(False)
  fp.SetSheetfile('ledkiv4.kicad_sch');fp.SetSheetname('')
  attributes=fp.GetAttributes()
  if child(inst,'in_bom')[1]=='no':attributes|=pcbnew.FP_EXCLUDE_FROM_BOM
  fp.SetAttributes(attributes)
  key=pcbnew.KIID_PATH();key.push_back(pcbnew.KIID(str(child(schema,'uuid')[1])));key.push_back(pcbnew.KIID(str(child(inst,'uuid')[1])));fp.SetPath(key)
  fps[ref]=fp
 for n,f in enumerate(mechanics,1):
  board.Add(f);f.SetReference('H'+str(n));f.SetAttributes(f.GetAttributes()|pcbnew.FP_BOARD_ONLY|pcbnew.FP_EXCLUDE_FROM_BOM|pcbnew.FP_EXCLUDE_FROM_POS_FILES)
 for n in netlist.find('nets'):
  name=n.attrib['name'];net=board.FindNet(name)
  if not net:net=pcbnew.NETINFO_ITEM(board,name);board.Add(net)
  for node in n.findall('node'):
   pads=[p for p in fps[node.attrib['ref']].Pads() if p.GetNumber()==node.attrib['pin']]
   assert pads,node.attrib
   for p in pads:
    p.SetNet(net);p.SetPinFunction(node.attrib.get('pinfunction',''));p.SetPinType(node.attrib.get('pintype',''))
 pcbnew.SaveBoard(str(path),board)
 print(f'Synchronized {len(fps)} electrical footprints; retained four layers and mechanical holes. Routing remains pending.')
if __name__=='__main__':main()
