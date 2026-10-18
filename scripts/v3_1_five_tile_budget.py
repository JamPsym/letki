#!/usr/bin/env python3
"""Evaluate brightness options, five-tile power and proposed rail drop limits."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT/'config/v3_1-system.json').read_text())
out = ROOT/'build/hardware/v3_1-five-tiles'
out.mkdir(parents=True, exist_ok=True)
n = cfg['tile_count']
assert n == 5
rail = cfg['tile_supply_V']
led = cfg['LED_model']
scan = cfg['scan']
b = cfg['budget_assumptions']
active = 1-scan['blank_us']/scan['column_slot_us']
duty = active/scan['columns']
assert scan['frame_Hz'] == 1e6/(scan['column_slot_us']*scan['columns'])
rows = []
for ohm, label, extra_parts in [(220, 'Initial continuous-current reference', 0),
                                (100, 'Higher continuous-current reference', 0),
                                (102, 'Continuous: two stocked 51R in series', 40),
                                (34, 'PULSE ONLY: two stocked 68R in parallel', 40),
                                (33, 'PULSE ONLY: one new 33R', 0),
                                (51, 'PULSE ONLY: one stocked 51R', 0),
                                (82, 'Continuous screen fails at nominal datasheet Vf floor', 0)]:
    rmin = ohm*(1-cfg['resistance_engineering_allowance'])
    nominal = (rail['nominal']-led['nominal_Vf_V'])/ohm
    pulsed_option = ohm in [34,33,51]
    option_duty = duty if pulsed_option else .1
    limit = led['pulse_current_ceiling_A_at_25C'] if pulsed_option else led['continuous_current_ceiling_A_at_25C']
    # A positive voltage margin at 20mA rules out an operating point above
    # 20mA IF Vf at that current stays above the assumed floor and IV is monotone.
    # It is not a rigorous current bound obtained by treating Vf as constant.
    margin = led['assumed_Vf_floor_at_20mA_V']+limit*rmin-rail['maximum']
    margin25 = led['datasheet_Vf_min_at_20mA_25C_V']+led['continuous_current_ceiling_A_at_25C']*rmin-rail['maximum']
    rows.append({'row_ohm':ohm, 'profile':'pulse' if pulsed_option else 'continuous',
                 'nominal_pixel_pulse_mA':nominal*1000,
                 'nominal_pixel_average_mA':nominal*option_duty*1000,
                 'conditional_current_ceiling_margin_V':margin, '25C_table_20mA_margin_V':margin25,
                 'zero_LED_drop_fault_mA':rail['maximum']/rmin*1000,
                 'row_resistor_zero_drop_fault_mW':rail['maximum']**2/rmin*1000,
                 'additional_placements_for_five_tiles':extra_parts, 'description':label})
chosen = next(r for r in rows if r['row_ohm'] == cfg['row_resistor_ohm'])
assert chosen['conditional_current_ceiling_margin_V'] > 0
assert next(r for r in rows if r['row_ohm']==82)['25C_table_20mA_margin_V'] < 0

vmax = rail['maximum']
gate_peak = vmax/970
gate_dc = vmax/(11000*.97)
bias = 8*vmax/9700
address = 3*vmax/(4700*.93)
tile_base = b['tile_core_A']+b['tile_other_IO_A']+b['tile_decoder_A']+bias+9*gate_dc+address
tile_mean_base = tile_base+b['tile_average_gate_charge_allowance_A']
tile_LED_mean = 64*chosen['nominal_pixel_average_mA']/1000
tile_LED_peak = 8*chosen['nominal_pixel_pulse_mA']/1000
mean_nominal = n*(tile_LED_mean+tile_mean_base)+b['ESP_nominal_A']+b['head_other_A']
op_pulse = led['operating_pulse_budget_A']
mean_limit_budget = n*(8*op_pulse*active+tile_mean_base)+b['ESP_supply_capacity_allowance_A']+b['head_other_A']
peak_limit_budget = n*(8*op_pulse+tile_base+16*gate_peak)+b['ESP_supply_capacity_allowance_A']+b['head_other_A']
usb_sustained = mean_limit_budget*vmax/(b['buck_efficiency_for_budget']*b['USB_min_at_converter_V'])
assert mean_limit_budget < cfg['head_power']['output_capacity_target_A']
assert peak_limit_budget < cfg['head_power']['transient_peak_target_A']
assert usb_sustained < 3

p = cfg['power_layout_targets']
width, thickness = p['VCC_rail_width_mm'], p['outer_copper_thickness_um']/1000
rloop = 2*p['copper_resistivity_ohm_mm2_per_m_at_20C']*(p['per_tile_path_mm']/1000)/(width*thickness)
single_end_drop = p['tile_peak_budget_A']*rloop*(n*(n+1)/2)*p['hot_resistance_factor']
# Equal-potential feeds at both ends; symmetric equal loads, one segment
# before each node and after the last node. Vj=I*R*j*(n+1-j)/2.
drop = p['tile_peak_budget_A']*rloop*max(j*(n+1-j)/2 for j in range(1,n+1))*p['hot_resistance_factor']
last_v = p['head_minimum_output_V_at_load']-drop-p['extra_contact_and_wire_drop_budget_V']
assert last_v >= rail['minimum']
result = {
    'status':'Engineering planning model; conditional LED floor and budgets need physical qualification',
    'tile_count':n, 'pixel_duty':duty, 'active_supply_duty':active,
    'selected_row_ohm':cfg['row_resistor_ohm'], 'selected_nominal_pixel_pulse_mA':chosen['nominal_pixel_pulse_mA'],
    'selected_nominal_pixel_average_mA':chosen['nominal_pixel_average_mA'],
    'average_current_ratio_vs_220R_continuous_profile':220/cfg['row_resistor_ohm']*duty/.1,
    'five_tile_LED_only_nominal_average_A':n*tile_LED_mean,
    'full_matrix_plus_logic_ESP_nominal_engineering_average_A':mean_nominal,
    'full_matrix_operating_pulse_budget_plus_ESP_capacity_average_A':mean_limit_budget,
    'coincident_gate_transient_plus_operating_pulse_budget_A':peak_limit_budget,
    'USB_input_sustained_budget_A_at_4p5V_eta_0p85':usb_sustained,
    'head_output_capacity_target_A':cfg['head_power']['output_capacity_target_A'],
    'LDO_heat_at_nominal_engineering_load_W':(5-3.3)*mean_nominal,
    'buck_loss_at_nominal_engineering_load_eta_0p85_W':3.3*mean_nominal*(1/.85-1),
    'rail_drop':{'geometry_status':'Unrouted target, 2mm-equivalent VCC/GND, 35um copper, 30% hot R allowance',
                 'two_end_feed_copper_loop_drop_V':drop, 'single_end_feed_drop_V':single_end_drop,
                 'additional_contacts_wire_budget_V':p['extra_contact_and_wire_drop_budget_V'],
                 'last_tile_minimum_V':last_v, 'full_chain_head_LED_feed_design_current_A':n*p['tile_peak_budget_A']},
    'assumptions':cfg, 'resistor_comparison':rows,
    'limits':[
        'Vf=2.1V is an illustration, not a measured LED bin or guaranteed current/brightness.',
        'The 1.6V floor at 20mA is conditional; actual lot/hot measurements and current/temperature derating determine release population.',
        'Current ratios are calculated, not measured luminous output.',
        'Pulse absolute ceiling is 80mA at 25C for <=100us and <=10% duty; continuous ceiling is 20mA.',
        '34R is for dedicated hardware-one-pulse firmware ONLY; never use the repetitive/continuous driver.',
        'ESP 500mA is a supply-capacity allowance, not constant current; logic budgets are engineering estimates.',
        'Zero-LED-drop multi-fault current is excluded from normal head sizing; protection behavior requires separate checks.',
        'Rail drop calculation is not routed copper or an IPC thermal/current-rating certification.',
        'USB-C needs actual source-current handling. Rd alone does not grant 1.5A/3A.',
        'Five-tile/ESP/new MOSFET optics and power not tested; existing two-v3 UART/I2C transport is confirmed.'
    ]}
(out/'power-brightness.json').write_text(json.dumps(result,indent=2)+'\n')
with (out/'resistor-comparison.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
print(f"5 tiles, {cfg['row_resistor_ohm']}R: {chosen['nominal_pixel_pulse_mA']:.2f}mA pulse / {chosen['nominal_pixel_average_mA']:.2f}mA mean pixel; {mean_nominal:.3f}A nominal engineering total.")
print(f"60mA pulse budget + ESP allowance: {mean_limit_budget:.3f}A mean, {peak_limit_budget:.3f}A coincident gate model; target 3.3V/3A with 3.5A transient envelope.")
print(f"Copper target drop {drop*1000:.1f}mV + contacts/wire budget; last tile minimum {last_v:.3f}V.")
