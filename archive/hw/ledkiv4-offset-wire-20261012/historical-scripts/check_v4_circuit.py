#!/usr/bin/env python3
"""Check v4 electrical connectivity against explicit datasheet pin mappings.

This is a circuit check, not a routing/manufacturing/physical-qualification gate.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'build/hardware/v4'
r=E.parse(ART/'netlist.xml').getroot()
components={c.attrib['ref']:c for c in r.find('components')}
nets={n.attrib['name']:{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node')} for n in r.find('nets')}
def net_of(ref,pin):
 matches=[(name,items) for name,items in nets.items() if (ref,pin) in items]
 assert len(matches)==1,(ref,pin,matches)
 return matches[0]
def same(*endpoints):
 name,items=net_of(*endpoints[0]);assert all(p in items for p in endpoints),(name,endpoints)
 return name,items
assert sum(ref.startswith('D') and ref[1:].isdigit() for ref in components)==64
assert components['U2'].findtext('value')=='74HCT238PW,118'
assert components['U3'].findtext('value')=='SN74HCT244PWR'
outputs=['15','14','13','12','11','10','9','7']
rows=['19','5','13','14','1','20','10','4']
buf_in=['2','4','6','8','17','15','13','11'];buf_out=['18','16','14','12','3','5','7','9']
for n in range(1,9):
 _,gate=same(('U2',outputs[n-1]),('Q'+str(n),'1'));assert not any(ref.startswith('D') for ref,pin in gate)
 _,column=net_of('Q'+str(n),'3')
 assert {(ref,pin) for ref,pin in column if ref.startswith('D')}=={('D'+str(row*8+n),'1') for row in range(8)}
 same(('Q'+str(n),'2'),('U1','7'))
 same(('U1',rows[n-1]),('U3',buf_in[n-1]),('R'+str(14+n),'1'))
 _,row=same(('U3',buf_out[n-1]),('R'+str(n),'2'));assert not any(ref=='U1' for ref,pin in row)
 _,anodes=net_of('R'+str(n),'1')
 assert {(ref,pin) for ref,pin in anodes if ref.startswith('D')}=={('D'+str((n-1)*8+col+1),'2') for col in range(8)}
 assert components['R'+str(n)].findtext('value')=='1.2k 1%'
for ref,c in components.items():
 if ref.startswith('D') and ref[1:].isdigit():
  assert c.findtext('value')=='XL-2012UOC'
  fields={f.attrib['name']:f.text for f in c.findall('fields/field')}
  assert fields.get('LCSC')=='C965813'
for ref in ('R11','R12'):
 _,items=net_of(ref,'1');assert ('U1','9') not in items, 'I2C pull-up bypasses head-only jumper'
 assert components[ref].findtext('value')=='2.2k'
same(('U1','11'),('J1','3'),('J3','3'),('R12','2'))
same(('U1','12'),('J1','4'),('J3','4'),('R11','2'))
same(('U1','2'),('U4','2'),('R28','2'))
same(('U1','3'),('U4','3'))
same(('U4','6'),('R26','1'));same(('R26','2'),('J1','5'))
same(('U4','5'),('R27','2'),('R29','2'));same(('R27','1'),('J3','5'))
assert net_of('U1','2')[0] != net_of('J1','5')[0]
assert net_of('U1','3')[0] != net_of('J3','5')[0]
for pin in ('1','4','7'):same(('U4',pin),('U1','7'))
same(('U1','9'),('U6','2'),('U4','8'),('C3','2'),('C7','1'),
     ('C9','1'),('JP1','1'),('JP2','1'),('SW1','1'),('SW2','1'),
     ('J2','1'),('R28','1'),('R29','1'))
same(('U6','1'),('U1','7'),('C8','2'),('C9','2'))
same(('U1','18'),('J2','2'))
same(('U1','7'),('J2','3'))
same(('U1','7'),('C1','1'),('C3','1'),('C6','2'),('C7','2'))
for n,pin in enumerate(('1','2','3'),23):same(('U2',pin),('R'+str(n),'1'))
for pin in ('1','10','19'):same(('U3',pin),('U1','7'))
same(('U3','20'),('U2','16'),('U2','6'),('U6','3'),('C6','1'),
     ('C8','1'),('J1','1'),('J1','2'),('J3','1'),('J3','2'))
assert net_of('U1','9')[0] != net_of('U3','20')[0], 'Logic rail shorted to LED rail'
for pin in ('4','5'):same(('U2',pin),('U1','7'))
assert components['U4'].findtext('value')=='SN74LVC2G125DCUR'
assert components['U6'].findtext('value')=='ME6206A33M3G'
for ref in ('R26','R27'):assert components[ref].findtext('value')=='2.2k'
for ref in ('R9','R14','R28','R29'):assert components[ref].findtext('value')=='100k'
same(('U5','1'),('U5','3'),('C10','1'),('J4','A4'),('J4','A9'),('J4','B4'),('J4','B9'))
same(('U5','6'),('U3','20'))
same(('U5','2'),('U1','7'),('C10','2'),('R30','2'),('R31','2'),('R32','2'),
     ('J4','A1'),('J4','A12'),('J4','B1'),('J4','B12'),('J4','SH'))
same(('U5','5'),('R32','1'))
same(('J4','A5'),('R30','1'));same(('J4','B5'),('R31','1'))
assert net_of('J4','A5')[0] != net_of('J4','B5')[0], 'USB CC pins must have individual pulls'
assert net_of('U5','1')[0] != net_of('U5','6')[0], 'Current limiting bypassed'
for ref in ('R30','R31'):assert components[ref].findtext('value')=='5.1k 1%'
assert components['R32'].findtext('value')=='33k 1%'
assert components['U5'].findtext('value')=='TPS2553DBVR'
for ref in ('U5','J4','R30','R31','R32','C10'):
 fields={f.attrib['name']:f.text for f in components[ref].findall('fields/field')}
 assert fields.get('Population')=='HEAD_ONLY',(ref,fields)
# Bare probe pads are electrical nodes, with no purchased component.
for ref,endpoint in [('TP1',('U5','1')),('TP2',('U1','9')),('TP3',('U1','2')),
                     ('TP4',('U1','3')),('TP5',('U2','1')),('TP6',('U2','2')),
                     ('TP7',('U2','3')),('TP8',('U2','15')),('TP9',('Q1','3')),
                     ('TP10',('U1','7'))]:
 same((ref,'1'),endpoint)
 fields={f.attrib['name']:f.text for f in components[ref].findall('fields/field')}
 assert fields.get('Population')=='PCB_ONLY' and not fields.get('LCSC'),(ref,fields)
resistance=1200
limit_resistance_kohm=33.0
current=5.25/(resistance*.99)
conservative_current=5.25/(resistance*.97)
report={'status':'circuit connectivity checks passed; production completion NOT established',
 'led':'XINGLIGHT XL-2012UOC, orange, LCSC C965813',
 'row_resistance_ohm':resistance,'row_initial_tolerance':.01,
 'row_total_resistance_allowance':.03,
 'supplies':'3.3 V MCU/UART/I2C; 5 V HCT LED drivers',
 'uart':'SN74LVC2G125DCUR buffered TX/RX, 2.2k series, 100k idle pulls',
 'swio':'J2 pin 1 = 3.3 V reference, pin 2 = U1 PD1/SWIO, pin 3 = GND; optional PicoBlade or bare pads',
 'usb_head':'USB-C 5 V sink, TPS2553DBVR, 33k 1% current limit; regulated 5 V 1 A charger',
 'usb_current_limit_min_mA_R_initial_tolerance':25230/(limit_resistance_kohm*1.01)**1.016,
 'usb_current_limit_max_mA_R_initial_tolerance':22980/(limit_resistance_kohm*.99)**.94,
 'usb_current_limit_min_mA_R_total_3percent_allowance':25230/(limit_resistance_kohm*1.03)**1.016,
 'usb_current_limit_max_mA_R_total_3percent_allowance':22980/(limit_resistance_kohm*.97)**.94,
 'row_fault_current_max_mA':current*1000,'eight_row_fault_current_max_mA':8*current*1000,
 'row_resistor_fault_power_max_mW':5.25**2/(resistance*.99)*1000,
 'eight_row_fault_current_mA_total_3percent_allowance':8*conservative_current*1000,
 'row_buffer_delta_ICC_mA_engineering_allowance':8*3,
 'row_buffer_static_VCC_mA_with_fault_and_3percent_resistance_allowance':8*conservative_current*1000+24+.160,
 'row_buffer_VCC_absolute_max_mA':70,
 'row_buffer_budget_caveat':'3 mA/input is specified at 0.5/2.4 V; exact MCU VOH/current and transition effects require qualification',
 'i2c_head_pullups_ohm':2200,
 'i2c_rise_time_ns_at_400pF_with_3percent_R_allowance':.8473*2200*1.03*400e-12*1e9,
 'i2c_pullup_low_current_mA_at_Vlogic3p366_VOL0p4_Rminus3percent':(3.366-.4)/(2200*.97)*1000,
 'sink_Rds_conservative_ohm_at_25C':4.5,
 'sink_drop_at_fault_bound_V':8*current*4.5,
 'sink_power_at_fault_bound_mW':(8*current)**2*4.5*1000,
 'remaining_gates':['physical USB supply/protection envelope','procurement stock and fabricator review','UART/full-chain electrical qualification','LED revision/bin and brightness qualification','physical first article and mechanical tests']}
(ART/'circuit-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
