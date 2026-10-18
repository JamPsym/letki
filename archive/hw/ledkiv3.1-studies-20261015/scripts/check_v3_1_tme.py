#!/usr/bin/env python3
"""Independently audit Study B's exported pins, exact parts and current paths."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--netlist', type=Path)
parser.add_argument('--output', type=Path)
parser.add_argument('--profile', choices=['continuous','pulse'], default='continuous')
args = parser.parse_args()
prefix = 'pulse-' if args.profile == 'pulse' else ''
evidence = ROOT/'build/hardware/v3_1-five-tiles'
args.netlist = args.netlist or evidence/(prefix+'netlist.xml')
args.output = args.output or evidence/(prefix+'circuit-check.json')
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


def value(ref):
    return parts[ref].findtext('value')


def fields(ref):
    return {f.attrib['name']: f.text for f in parts[ref].findall('fields/field')}


assert {r for r in parts if r.startswith('U')} == {'U1', 'U2'}, 'Exactly the two v3 ICs'
assert value('U1') == 'CH32V003F4P6'
assert value('U2') == 'SN74HC138PWR'
assert {r for r in parts if r.startswith('D')} == {f'D{i}' for i in range(1, 65)}
assert {r for r in parts if r.startswith('Q')} == {f'Q{i}' for i in range(1, 17)}
pulsed = args.profile == 'pulse'
assert {r for r in parts if r.startswith('R')} == {f'R{i}' for i in range(1, 66 if pulsed else 58)}
row_pins = ['19', '5', '13', '14', '1', '20', '10', '4']  # R1 bottom .. R8 top
col_pins = ['15', '14', '13', '12', '11', '10', '9', '7']
for i in range(1, 9):
    pmos, nmos = f'Q{i}', f'Q{8+i}'
    assert value(pmos) == fields(pmos)['MPN'] == 'AO3415A'
    assert value(nmos) == fields(nmos)['MPN'] == 'DMN2056U-7'
    for q in [pmos, nmos]:
        assert parts[q].findtext('footprint') == 'Package_TO_SOT_SMD:SOT-23'
        assert fields(q)['Supplier'] == 'TME'
    # Manufacturer G1/S2/D3 maps, independent of generic drawing placement.
    same((pmos, '2'), ('U1', '9'), ('U2', '16'))
    assert net(pmos, '1') == {(pmos, '1'), (f'R{14+i}', '2'), (f'R{22+i}', '2')}
    assert net('U2', col_pins[i-1]) == {('U2', col_pins[i-1]), (f'R{14+i}', '1')}
    same((f'R{22+i}', '1'), ('U1', '9'))
    assert net(pmos, '3') == {(pmos, '3')} | {(f'D{row*8+i}', '2') for row in range(8)}
    assert net(f'R{i}', '1') == {(f'R{i}', '1')} | {(f'D{(i-1)*8+c}', '1') for c in range(1, 9)} | ({(f'R{57+i}','1')} if pulsed else set())
    assert net(nmos, '3') == {(nmos, '3'), (f'R{i}', '2'), (f'R{49+i}', '2')} | ({(f'R{57+i}','2')} if pulsed else set())
    assert net(nmos, '1') == {(nmos, '1'), (f'R{41+i}', '2'), (f'R{30+i}', '1')}
    same((nmos, '2'), (f'R{30+i}', '2'), ('U1', '7'))
    assert net('U1', row_pins[i-1]) == {('U1', row_pins[i-1]), (f'R{41+i}', '1')}
    same((f'R{49+i}', '1'), ('U1', '9'))
    assert value(f'R{i}') == ('68 1%' if pulsed else '100 1%')
    assert fields(f'R{i}')['MPN'] == ('0805W8F680JT5E' if pulsed else '0805S8F1000T5E')
    if pulsed:
        assert value(f'R{57+i}') == '68 1%'
        assert fields(f'R{57+i}')['MPN'] == '0805W8F680JT5E'
    assert value(f'R{14+i}') == value(f'R{41+i}') == '1k 1%'
    assert value(f'R{22+i}') == value(f'R{30+i}') == value(f'R{49+i}') == '10k'
for i, mcu_pin in enumerate(['17', '16', '15'], 1):
    assert same(('U1', mcu_pin), ('U2', str(i)), (f'R{38+i}', '2')) == {
        ('U1', mcu_pin), ('U2', str(i)), (f'R{38+i}', '2')}
    same((f'R{38+i}', '1'), ('U1', '9'))
    assert value(f'R{38+i}') == '4.7k'
for n in range(1, 65):
    assert value(f'D{n}') == 'XL-2012UOC'
# Retained interfaces, decoupling, enables and explicit C1/C3 ground repair.
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
allowance = .03  # Initial tolerance + engineering allowance for TCR/drift.
row_ohm = 34 if pulsed else 100
pixel_duty = .08 if pulsed else .1
row_active_duty = .64 if pulsed else 1
row_min, gate_min, pull_min = row_ohm*(1-allowance), 1000*(1-allowance), 10000*(1-allowance)
led_bound = vmax/row_min  # Zero LED and MOSFET drops; not the normal current.
led_limit = .080 if pulsed else .020  # 25C stress ceiling, with pulse conditions if selected.
vf_at_limit_floor = 1.6  # Engineering floor, NOT a manufacturer hot-temperature guarantee.
loadline_margin = vf_at_limit_floor+led_limit*row_min-vmax
drain_bias = vmax/pull_min
gate_peak = vmax/gate_min
gate_dc = vmax/((1000+10000)*(1-allowance))
address_allowance = .07  # Existing 4.7k parts are 5%, plus 2% engineering allowance.
address_sink = 3*vmax/(4700*(1-address_allowance))
gate_fraction = pull_min/(pull_min+1000*(1+allowance))
gate_thevenin = 10000*(1+allowance)*1000*(1+allowance)/(11000*(1+allowance))
n_vgs = 2.3*gate_fraction - 100e-9*gate_thevenin
p_vgs_conditional = (vmin-.4)*gate_fraction - 10e-6*gate_thevenin
core_allowance, other_io_allowance, decoder_allowance = .020, .005, .001
mcu_peak_budget = core_allowance+other_io_allowance+8*gate_peak+address_sink
decoder_peak_budget = decoder_allowance+8*gate_peak+gate_dc
rail_peak_budget = (8*(led_bound+drain_bias+gate_dc)+gate_dc+address_sink+
                    core_allowance+other_io_allowance+decoder_allowance+16*gate_peak)
assert loadline_margin > 0  # Conditional monotone LED load-line crossing before 20mA.
resistor_fault_mean = vmax*vmax/row_min*row_active_duty/(2 if pulsed else 1)
assert resistor_fault_mean < .125  # Parallel parts split power; <=70C and pulse-overload review required.
assert vmax*vmax/(4*row_min)*pixel_duty < .050  # Mean LED power ceiling at 25C, not a pulse qualification.
assert n_vgs > 1.5 and p_vgs_conditional > 1.8
assert gate_peak < .008 and mcu_peak_budget < .080
assert decoder_peak_budget < .050 and gate_peak < .025
assert rail_peak_budget < (1 if pulsed else .4)  # Includes zero-drop faults; head normal load modeled separately.
report = {
    'status': 'INDEPENDENT CONNECTIVITY CHECK PASSED; schematic study, physical qualification pending',
    'ic_count': 2, 'transistor_count': 16, 'led_count': 64, 'resistor_count': 65 if pulsed else 57,
    'profile': args.profile,
    'pulse_conditions': {'gate_pulse_us':80,'pixel_period_us':1000,'duty':.08,'LED_absolute_pulse_ceiling_mA_at_25C':80,'requires':'v3_1-pulse hardware OPM/PWM2; gate/drain waveform verification'} if pulsed else None,
    'supply_V': {'nominal': 3.3, 'minimum': vmin, 'maximum': vmax},
    'row_resistance_ohm': row_ohm, 'engineering_resistance_allowance': allowance,
    'address_pull_engineering_resistance_allowance': address_allowance,
    'per_LED_zero_drop_bound_mA': led_bound*1000,
    'LED_current_limit_loadline_check': {'assumed_Vf_at_20mA_floor_V': vf_at_limit_floor,
        'current_ceiling_mA':led_limit*1000,
        'margin_V': loadline_margin,
        'condition': 'Monotone IV curve and Vf(20mA)>=1.6V; temperature/lot measurements required. Pulse ceiling additionally requires timing conditions.'},
    'per_NMOS_with_drain_bias_bound_mA': (led_bound+drain_bias)*1000,
    'selected_PMOS_column_bound_mA': 8*led_bound*1000,
    'row_resistor_zero_drop_power_mW': vmax*vmax/row_min*1000,
    'individual_row_resistor_mean_zero_drop_fault_mW':resistor_fault_mean*1000,
    'LED_electrical_power_bound_25C_mW': vmax*vmax/(4*row_min)*1000,
    'gate_series_initial_peak_bound_mA': gate_peak*1000,
    'gate_divider_DC_bound_mA': gate_dc*1000,
    'minimum_NMOS_VGS_with_GPIO_VOH_2p3V': n_vgs,
    'minimum_abs_PMOS_VGS_conditional_on_decoder_VOL_0p4V': p_vgs_conditional,
    'MCU_core_engineering_allowance_mA': core_allowance*1000,
    'other_IO_engineering_allowance_mA': other_io_allowance*1000,
    'MCU_supply_transient_engineering_subtotal_mA': mcu_peak_budget*1000,
    'MCU_absolute_max_mA': {'VDD': 100, 'VSS': 80},
    'HC138_supply_transient_engineering_subtotal_mA': decoder_peak_budget*1000,
    'HC138_supply_absolute_max_mA': 50,
    'rail_coincident_engineering_sum_mA': rail_peak_budget*1000,
    'initial_test_supply_capacity_A_per_tile': .75 if pulsed else .4,
    'Rds_max_at_low_gate_voltage_25C_ohm': {'AO3415A_at_minus_1p8V': .065, 'DMN2056U_at_plus_1p5V': .085},
    'MOSFET_conduction_power_bound_25C_mW': {
        'selected_PMOS': (8*led_bound)**2*.065*1000,
        'one_NMOS_including_bias': (led_bound+drain_bias)**2*.085*1000},
    'brightness_illustration': {'assumed_LED_Vf_V': 2.1, 'ignored_switch_drop': True,
        'selected_pixel_current_mA': (3.3-2.1)/row_ohm*1000, 'nominal_pixel_duty': pixel_duty,
        'average_pixel_current_mA': (3.3-2.1)/row_ohm*1000*pixel_duty,
        'full_matrix_average_LED_current_mA': 64*(3.3-2.1)/row_ohm*1000*pixel_duty},
    'limits': [
        'HC138 has no loaded 3.3V VOL guarantee in its 2/4.5/6V table; VOL<=0.4V is conditional and needs measurement.',
        'Address open-drain rise times and decoder input-transition limits require trace/capacitance review and bench checks.',
        'Core/other-I/O/decoder allowances and coincident transient sums are engineering budgets, not guaranteed supply maxima.',
        'Gate charge, row release, column turn-off, reset and address glitches require scope checks through the 100us blank.',
        'One timer tick is 83ns: the existing gamma PWM low end may not pass the 1k gate network optically.',
        'DMN2056U Ciss/Qg are typical, not maximum; AO3415A has maxima at the documented test conditions.',
        'Rds maxima are at 25C; LED/resistor temperature derating and actual brightness remain to be qualified.',
        '100R replaces the initial 220R for brightness. The zero-drop bound is now >20mA; LED limiting relies on a conditional Vf load line.',
        '1.6V at 20mA is an engineering floor beyond the 25C datasheet table, not a certified temperature guarantee.',
        'Zero-LED-drop resistor dissipation is about 124mW, close to 125mW at <=70C; normal LED dissipation is lower. Fault/temperature qualification remains.',
        'V3 PWM ghosting was fixed and user-confirmed using GPIO-LOW blanking and selective PWM return; Study B retains that sequence.',
        'Cathode bias resistors bias new MOSFET-side nodes; checking their settling does not reopen the resolved v3 firmware issue.',
        'Only a common regulated 3.3V +/-5% supply; no direct 5V, USB power, onboard regulator or port buffering.',
        'Original contact/mechanical arrangements and per-tile I2C pulls remain for later integration.',
        'No study PCB exists. Original seed DRC/parity violations remain unchanged; no physical testing or fabrication release.'
    ],
    'datasheet_archive': 'build/hardware/v3_1-tme-study/references/manifest.json',
}
if pulsed:
    report['limits'] = [x for x in report['limits'] if not any(y in x for y in ['100R replaces','about 124mW','existing gamma PWM','through the 100us blank','LED limiting relies'])]
    report['limits'] += [
        'Pulse profile ONLY: never use continuous/repetitive full-duty row firmware with 34R.',
        '80mA is an absolute pulse ceiling at 25C for <=100us and <=10% duty; it is not the selected operating current.',
        '80us hardware gate pulses leave allowance below 100us; gate tails, clock/timing, temperature and exact LED lot require physical validation.',
        'Mean zero-drop power calculation does not establish a resistor repetitive-pulse overload rating; check exact stock part and temperature.',
        'Skipped scan interrupts stop in modeled PWM2/OPM hardware; silicon waveform and restart behavior still need verification.'
    ]
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(f'TME study: two retained ICs, 16 exact MOSFETs, 64 reversed LEDs; '
      f'zero-drop LED bound {led_bound*1000:.2f}mA, nominal illustration '
      f'{(3.3-2.1)/row_ohm*1000:.2f}mA pulse at {pixel_duty:.0%} pixel duty. Conditional limit margin {loadline_margin:.3f}V; physical checks pending.')
