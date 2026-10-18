#!/usr/bin/env python3
"""Audit the schematic-only PMOS study against exact pins and retained v3 I/O."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--netlist', type=Path, default=ROOT/'build/hardware/v3_1-transistor-study/netlist.xml')
parser.add_argument('--output', type=Path, default=ROOT/'build/hardware/v3_1-transistor-study/circuit-check.json')
args = parser.parse_args()
root = ET.parse(args.netlist).getroot()
parts = {c.attrib['ref']: c for c in root.findall('components/comp')}
nets = {n.attrib['name']: {(p.attrib['ref'], p.attrib['pin']) for p in n.findall('node')}
        for n in root.findall('nets/net')}


def net(ref, pin):
    hits = [items for items in nets.values() if (ref, pin) in items]
    assert len(hits) == 1, (ref, pin, hits)
    return hits[0]


def same(*pins):
    items = net(*pins[0])
    assert all(pin in items for pin in pins), pins
    return items


def fields(ref):
    return {f.attrib['name']: f.text for f in parts[ref].findall('fields/field')}


assert {r for r in parts if r.startswith('U')} == {'U1', 'U2'}, 'Exactly the two v3 ICs'
assert parts['U1'].findtext('value') == 'CH32V003F4P6'
assert parts['U2'].findtext('value') == 'SN74HC138PWR'
assert len([r for r in parts if r.startswith('D')]) == 64
assert len([r for r in parts if r.startswith('Q')]) == 8
row_pins = ['19', '5', '13', '14', '1', '20', '10', '4']  # R1 bottom .. R8 top
col_pins = ['15', '14', '13', '12', '11', '10', '9', '7']
for i in range(1, 9):
    # CJ2305 manufacturer drawing: G1/S2/D3; source on the common supply.
    assert parts[f'Q{i}'].findtext('value') == 'CJ2305'
    assert parts[f'Q{i}'].findtext('footprint') == 'Package_TO_SOT_SMD:SOT-23'
    same((f'Q{i}', '2'), ('U1', '9'), ('U2', '16'))
    gate = same((f'Q{i}', '1'), (f'R{22+i}', '2'))
    assert len(gate) == 3 and sum(r == f'R{14+i}' for r, p in gate) == 1
    logic = net('U2', col_pins[i-1])
    assert len(logic) == 2 and sum(r == f'R{14+i}' for r, p in logic) == 1
    assert not any(r.startswith('D') or r.startswith('Q') for r, p in logic)
    anodes = net(f'Q{i}', '3')
    assert anodes == {(f'Q{i}', '3')} | {(f'D{row*8+i}', '2') for row in range(8)}
    cathodes = net(f'R{i}', '1')
    assert cathodes == {(f'R{i}', '1')} | {(f'D{(i-1)*8+c}', '1') for c in range(1, 9)}
    sink = same(('U1', row_pins[i-1]), (f'R{i}', '2'), (f'R{30+i}', '2'))
    assert len(sink) == 3
    same((f'R{30+i}', '1'), (f'R{22+i}', '1'), ('U1', '9'))
    assert parts[f'R{i}'].findtext('value') == '680 1%'
    assert parts[f'R{14+i}'].findtext('value') == '1k 1%'
    assert parts[f'R{22+i}'].findtext('value') == parts[f'R{30+i}'].findtext('value') == '10k'
for i, mcu_pin in enumerate(['17', '16', '15'], 1):
    same(('U1', mcu_pin), ('U2', str(i)), (f'R{38+i}', '2'))
    same((f'R{38+i}', '1'), ('U1', '9'))
    assert parts[f'R{38+i}'].findtext('value') == '4.7k'
for n in range(1, 65):
    assert parts[f'D{n}'].findtext('value') == 'XL-2012UOC'
same(('U1', '18'), ('J2', '2'))
same(('U1', '9'), ('J2', '1'), ('J1', '1'), ('J1', '2'), ('J3', '1'), ('J3', '2'))
same(('U1', '7'), ('J2', '3'), ('J1', '6'), ('J1', '7'), ('J3', '6'), ('J3', '7'),
     ('U2', '4'), ('U2', '5'), ('U2', '8'))
same(('U1', '9'), ('U2', '6'), ('C1', '2'), ('C3', '2'), ('C4', '1'))
same(('U1', '7'), ('C1', '1'), ('C3', '1'), ('C4', '2'))
same(('U1', '2'), ('J1', '5'))
same(('U1', '3'), ('J3', '5'))
same(('U1', '11'), ('J1', '3'), ('J3', '3'), ('R12', '2'))
same(('U1', '12'), ('J1', '4'), ('J3', '4'), ('R11', '2'))
same(('U1', '8'), ('C2', '1'), ('R10', '1'))
same(('U1', '6'), ('C5', '1'), ('R13', '1'))

vmin, vmax = 3.3*.95, 3.3*1.05
resistance_allowance = .03  # Engineering allowance: initial tolerance, TCR and drift.
row_min = 680*(1-resistance_allowance)
row_fault = vmax/row_min
pull_fault = vmax/(10000*(1-resistance_allowance))
gate_peak = vmax/(1000*(1-resistance_allowance))
gate_dc = vmax/((1000+10000)*(1-resistance_allowance))
gate_fraction = 10000*(1-resistance_allowance)/(10000*(1-resistance_allowance)+1000*(1+resistance_allowance))
vgs_assuming_vol04 = (vmin-.4)*gate_fraction
core_allowance, other_io_allowance = .020, .005
vss_subtotal = 8*(row_fault+pull_fault)+core_allowance+other_io_allowance
assert row_fault+pull_fault < .008  # Within the WCH characterised sink test current.
assert vss_subtotal < .080  # Absolute maximum is a ceiling, not a validated operating target.
assert vgs_assuming_vol04 > 1.8
report = {
    'status': 'INDEPENDENT CONNECTIVITY CHECK PASSED; schematic study, physical qualification pending',
    'ic_count': 2, 'transistor_count': 8, 'led_count': 64,
    'supply_V': {'nominal': 3.3, 'minimum': vmin, 'maximum': vmax},
    'row_resistance_ohm': 680, 'engineering_resistance_allowance': resistance_allowance,
    'per_row_zero_LED_drop_bound_mA': row_fault*1000,
    'per_pad_with_10k_pull_bound_mA': (row_fault+pull_fault)*1000,
    'eight_rows_LED_current_bound_mA': 8*row_fault*1000,
    'MCU_core_engineering_allowance_mA': core_allowance*1000,
    'other_IO_engineering_allowance_mA': other_io_allowance*1000,
    'MCU_VSS_engineering_subtotal_mA': vss_subtotal*1000,
    'MCU_VSS_absolute_max_mA': 80,
    'row_resistor_fault_power_mW': vmax*vmax/row_min*1000,
    'gate_series_initial_peak_bound_mA': gate_peak*1000,
    'selected_gate_DC_pull_current_bound_mA': gate_dc*1000,
    'minimum_abs_VGS_assuming_decoder_VOL_0p4V': vgs_assuming_vol04,
    'CJ2305_Rds_max_at_1p8V_25C_ohm': .090,
    'MOSFET_fault_drop_at_25C_V': 8*row_fault*.090,
    'MOSFET_fault_power_at_25C_mW': (8*row_fault)**2*.090*1000,
    'brightness_illustration': {'assumed_LED_Vf_V': 2.1, 'assumed_GPIO_VOL_V': .1,
                               'nominal_selected_pixel_current_mA': (3.3-2.1-.1)/680*1000,
                               'nominal_pixel_duty': .1},
    'limits': [
        'HC138 3.3V loaded VOL is not guaranteed by its 2/4.5/6V table; VOL=0.4V is an engineering condition to verify.',
        'Open-drain address rise time/loading must satisfy HC138 transition limits; exact 3.3V timing requires qualification.',
        '20mA core and 5mA other-I/O allowances are engineering budgets, not datasheet maximum guarantees.',
        'Gate charge/settling and 100us blanking require scope verification, including decoder transition glitches.',
        'Rds number is specified at 25C; temperature behavior and actual footprints require first-article review.',
        'LED low-current Vf/brightness and idle-column ghosting remain unmeasured.',
        'No onboard regulation or new port protection; common powered 3.3V chain only.',
        'Existing I2C pulls and edge-contact/mechanical ECOs are retained for this electrical study and need later review.',
        'No PCB exists for this study; original seed DRC/parity findings remain unchanged.'
    ]
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(f"PMOS study: 2 ICs, 8 transistors, reversed 64 LEDs; pad bound {(row_fault+pull_fault)*1000:.2f}mA; "
      f"VSS engineering subtotal {vss_subtotal*1000:.2f}mA; see limits.")
