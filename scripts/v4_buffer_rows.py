#!/usr/bin/env python3
"""Add the reviewed low-cost HCT row buffering and chain pull-up selection."""
from copy import deepcopy
from pathlib import Path
import uuid
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'hw/ledkiv4/ledkiv4.kicad_sch'
def uid():return Q(str(uuid.uuid4()))
def effects(hidden=False):return ['effects',['font',['size','1.27','1.27']]]+([['hide','yes']] if hidden else [])
def field(name,value,x=0,y=0,hidden=True):return ['property',Q(name),Q(value),['at',str(x),str(y),'0'],effects(hidden)]
def label(name,x,y):
 n=['label',Q(name),['at',str(round(x,6)),str(round(y,6)),'0'],effects(),['uuid',uid()]]
 if name in ('GND','VCC'):n[0]='global_label';n.insert(2,['shape','input'])
 return n
def lib(path,name):
 root=read(path);own=deepcopy(next(x for x in children(root,'symbol') if x[1]==name))
 parent=child(own,'extends')
 if not parent:return own
 inherited=lib(path,str(parent[1]));old=str(inherited[1]);inherited[1]=Q(name)
 for unit in children(inherited,'symbol'):unit[1]=Q(str(unit[1]).replace(old,name))
 for node in own[2:]:
  if not isinstance(node,list) or node[0]=='extends':continue
  if node[0]=='property':inherited[:]=[v for v in inherited if not(isinstance(v,list) and v[0]=='property' and v[1]==node[1])]
  else:inherited[:]=[v for v in inherited if not(isinstance(v,list) and v[0]==node[0])]
  inherited.append(node)
 return inherited
def pins(symbol):
 return {child(p,'number')[1]:p for unit in children(symbol,'symbol') for p in children(unit,'pin')}
def endpoint(inst,pin):
 at=child(inst,'at');assert at[3]=='0'
 p=child(pin,'at');return round(float(at[1])+float(p[1]),6),round(float(at[2])-float(p[2]),6)
def instance(root,libid,definition,ref,value,footprint,x,y,bom=True):
 n=['symbol',['lib_id',Q(libid)],['at',str(x),str(y),'0'],['unit','1'],['in_bom','yes' if bom else 'no'],['on_board','yes'],['dnp','no'],['uuid',uid()],
 field('Reference',ref,x+5.08,y-3.81,False),field('Value',value,x+5.08,y,False),field('Footprint',footprint),field('Datasheet','')]
 for number in pins(definition):n.append(['pin',Q(number),['uuid',uid()]])
 n.append(['instances',['project',Q('ledkiv4'),['path',Q('/'+child(root,'uuid')[1]),['reference',Q(ref)],['unit','1']]]])
 root.append(n);return n

def main():
 s=read(PATH);libroot=child(s,'lib_symbols');insts=children(s,'symbol')
 assert not any(prop(i,'Reference')[2]=='U3' for i in insts),'Row buffer already exists'
 # Flatten standard inherited HCT symbols while retaining standard pin geometry.
 logicpath='/usr/share/kicad/symbols/74xx.kicad_sym'
 for old,new in [('74HC238','74HCT238'),('74HC244','74HCT244')]:
  definition=lib(logicpath,new);definition[1]=Q('74xx:'+new)
  if old=='74HC238':libroot[:]=[n for n in libroot if not(isinstance(n,list) and n[0]=='symbol' and n[1]=='74xx:74HC238')]
  libroot.append(definition)
 u2=next(i for i in insts if prop(i,'Reference')[2]=='U2')
 child(u2,'lib_id')[1]=Q('74xx:74HCT238')
 prop(u2,'Value')[2]=Q('CD74HCT238PWR');prop(u2,'Manufacturer')[2]=Q('TI');prop(u2,'LCSC')[2]=Q('C2653311')
 prop(u2,'Datasheet')[2]=Q('https://www.ti.com/lit/ds/symlink/cd74hc238.pdf')
 buf=next(n for n in children(libroot,'symbol') if n[1]=='74xx:74HCT244')
 u3=instance(s,'74xx:74HCT244',buf,'U3','SN74HCT244PWR','Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm',260.35,181.61)
 prop(u3,'Datasheet')[2]=Q('https://www.ti.com/lit/ds/symlink/sn74hct244.pdf')
 u3.extend([field('Manufacturer','TI'),field('LCSC','C6778')])
 bp=pins(buf)
 u1=next(i for i in insts if prop(i,'Reference')[2]=='U1')
 mcu=next(n for n in children(libroot,'symbol') if n[1]=='Letki:CH32V003F4P6');mp=pins(mcu)
 rows=['19','5','13','14','1','20','10','4']
 inputs=['2','4','6','8','17','15','13','11'];outputs=['18','16','14','12','3','5','7','9']
 for row,num in enumerate(rows,1):
  point=endpoint(u1,mp[num]);attached=[]
  for wire in children(s,'wire'):
   pts=[tuple(round(float(v),6) for v in p[1:]) for p in children(child(wire,'pts'),'xy')]
   if point in pts:attached.append((wire,pts))
  assert len(attached)==1,(num,attached)
  wire,pts=attached[0];s.remove(wire);other=pts[1] if pts[0]==point else pts[0]
  s.extend([label('D'+str(row),*other),label('ROW_GPIO'+str(row),*point),
            label('ROW_GPIO'+str(row),*endpoint(u3,bp[inputs[row-1]])),label('D'+str(row),*endpoint(u3,bp[outputs[row-1]]))])
 for num in ('1','19','10'):s.append(label('GND',*endpoint(u3,bp[num])))
 s.append(label('VCC',*endpoint(u3,bp['20'])))
 # Defined input pulls, including decoder addresses during reset.
 resistor=next(n for n in children(libroot,'symbol') if n[1]=='Device:R');rp=pins(resistor)
 decoder=next(n for n in children(libroot,'symbol') if n[1]=='74xx:74HCT238');dp=pins(decoder)
 for index,num in enumerate(('1','2','3')):s.append(label('COL_ADDR'+str(index),*endpoint(u2,dp[num])))
 names=[f'ROW_GPIO{i}' for i in range(1,9)]+[f'COL_ADDR{i}' for i in range(3)]
 for index,name in enumerate(names):
  x=195.58+15.24*(index%6);y=243.84+22.86*(index//6)
  r=instance(s,'Device:R',resistor,'R'+str(15+index),'100k','Resistor_SMD:R_0603_1608Metric',x,y)
  s.extend([label(name,*endpoint(r,rp['1'])),label('GND',*endpoint(r,rp['2']))])
 cap=next(n for n in children(libroot,'symbol') if n[1]=='Device:C');cp=pins(cap)
 c=instance(s,'Device:C',cap,'C6','100n','Capacitor_SMD:C_0603_1608Metric',299.72,181.61)
 s.extend([label('VCC',*endpoint(c,cp['1'])),label('GND',*endpoint(c,cp['2']))])
 # Free solder jumpers select a single pair of I2C pull-ups per chain.
 jumper=lib('/usr/share/kicad/symbols/Jumper.kicad_sym','SolderJumper_2_Open')
 jumper[1]=Q('Jumper:SolderJumper_2_Open');libroot.append(jumper);jp=pins(jumper)
 for index,ref in enumerate(('R11','R12'),1):
  r=next(i for i in insts if prop(i,'Reference')[2]==ref)
  point=endpoint(r,rp['1']);wires=[]
  for wire in children(s,'wire'):
   pts=[tuple(round(float(v),6) for v in p[1:]) for p in children(child(wire,'pts'),'xy')]
   if point in pts:wires.append((wire,pts))
  if wires:
   assert len(wires)==1,(ref,wires)
   wire,pts=wires[0];s.remove(wire);other=pts[1] if pts[0]==point else pts[0]
   s.append(label('VCC',*other))
  else:
   attached=[n for n in children(s,'symbol') if child(n,'lib_id')[1]=='power:VCC' and tuple(map(float,child(n,'at')[1:3]))==point]
   assert len(attached)==1,(ref,point)
   s.remove(attached[0])
  s.append(label('PULLUP_VCC'+str(index),*point))
  j=instance(s,'Jumper:SolderJumper_2_Open',jumper,'JP'+str(index),'HEAD ONLY','Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm',322.58,243.84+12.7*index,bom=False)
  s.extend([label('VCC',*endpoint(j,jp['1'])),label('PULLUP_VCC'+str(index),*endpoint(j,jp['2']))])
 write(PATH,s)
 print('Added HCT244 row buffer, HCT238 decoder, 11 startup pulls, decoupling and I2C head-only solder jumpers.')
if __name__=='__main__':main()
