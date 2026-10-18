#!/usr/bin/env python3
"""Create a separate, schematic-only v3.1 PMOS study; never overwrite CAD.

The routed/ground-repaired seed stays untouched. This is not a PCB updater.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import uuid

from kicad_sexpr import Quoted as Q, child, children, prop, read, write

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'hw/ledkiv3.1'
DEST = SOURCE / 'transistor-study'
PROJECT = 'ledkiv3_1_pmos'


def uid():
    return Q(str(uuid.uuid4()))


def effects(hidden=False):
    return ['effects', ['font', ['size', '1', '1']]] + ([['hide', 'yes']] if hidden else [])


def field(name, value, x=0, y=0, hidden=True):
    return ['property', Q(name), Q(value), ['at', str(x), str(y), '0'], effects(hidden)]


def label(name, x, y):
    if name == 'VCC':
        return ['global_label', Q(name), ['shape', 'input'], ['at', str(x), str(y), '0'],
                effects(), ['uuid', uid()]]
    return ['label', Q(name), ['at', str(x), str(y), '0'], effects(), ['uuid', uid()]]


def pin_point(inst, pin):
    at = child(inst, 'at')
    angle = math.radians(float(at[3]))
    p = child(pin, 'at')
    x, y = map(float, p[1:3])
    return (round(float(at[1])+math.cos(angle)*x-math.sin(angle)*y, 6),
            round(float(at[2])-math.sin(angle)*x-math.cos(angle)*y, 6))


def tidy_pmos_schema(schema):
    """Give the added circuitry visible wire stubs and readable fields."""
    definitions = {str(s[1]): s for s in children(child(schema, 'lib_symbols'), 'symbol')}
    instances = {str(prop(s, 'Reference')[2]): s for s in children(schema, 'symbol')}

    def at(node):
        return tuple(round(float(v), 6) for v in child(node, 'at')[1:3])

    def wire(a, b):
        schema.append(['wire', ['pts', ['xy', *map(str, a)], ['xy', *map(str, b)]],
                       ['stroke', ['width', '0'], ['type', 'default']], ['uuid', uid()]])

    def attached_labels(point):
        return [n for tag in ('label', 'global_label') for n in children(schema, tag) if at(n) == point]

    for ref, inst in instances.items():
        if ref.startswith('D') and ref[1:].isdigit():
            effect = child(prop(inst, 'Value'), 'effects')
            if not child(effect, 'hide'):
                effect.append(['hide', 'yes'])
        new = ref.startswith('Q') or (ref.startswith('R') and int(ref[1:]) >= 15)
        if not new:
            continue
        x, y = at(inst)
        number = int(ref[1:])
        horizontal = ref.startswith('R') and 15 <= number <= 22
        for fname, offset in [('Reference', -5.08), ('Value', -2.54)]:
            f = prop(inst, fname)
            f_at = child(f, 'at')
            if horizontal:
                f_at[1:4] = [str(x), str(y+offset), '0']
                effect = child(f, 'effects')
                effect[:] = [n for n in effect if not (isinstance(n, list) and n[0] == 'justify')]
            else:
                f_at[1:4] = [str(x+6.35 if ref.startswith('Q') else x+3.81),
                            str(y+(-1.27 if fname == 'Reference' else 1.27)), '0']
                child(f, 'effects').append(['justify', 'left'])
        if ref.startswith('Q'):
            child(prop(inst, 'Value'), 'effects').append(['hide', 'yes'])
        for unit in children(definitions[str(child(inst, 'lib_id')[1])], 'symbol'):
            for pin in children(unit, 'pin'):
                num = str(child(pin, 'number')[1])
                point = pin_point(inst, pin)
                labels = attached_labels(point)
                if (ref.startswith('Q') and num == '1') or (horizontal and num == '2'):
                    for l in labels:
                        schema.remove(l)
                    continue
                dx, dy = point[0]-x, point[1]-y
                sx, sy = ((1 if dx > 0 else -1), 0) if abs(dx) > abs(dy) else (0, (1 if dy > 0 else -1))
                end = (round(point[0]+5.08*sx, 6), round(point[1]+5.08*sy, 6))
                wire(point, end)
                for l in labels:
                    child(l, 'at')[1:3] = list(map(str, end))
                    child(l, 'effects').append(['justify', 'right' if sx < 0 else 'left', 'bottom'])
    for n in range(1, 9):
        q, r = instances[f'Q{n}'], instances[f'R{14+n}']
        qpin = next(p for u in children(definitions[str(child(q, 'lib_id')[1])], 'symbol') for p in children(u, 'pin')
                    if child(p, 'number')[1] == '1')
        rpin = next(p for u in children(definitions['Device:R'], 'symbol') for p in children(u, 'pin')
                    if child(p, 'number')[1] == '2')
        a, b = pin_point(r, rpin), pin_point(q, qpin)
        wire(a, b)
        l = label(f'G{n}', round((a[0]+b[0])/2, 6), a[1])
        child(l, 'effects').append(['justify', 'left', 'bottom'])
        schema.append(l)
    for l in list(children(schema, 'label')):
        if str(l[1]).startswith('SEL') and at(l)[0] == 127.0:
            a = at(l)
            b = (132.08, a[1])
            wire(a, b)
            child(l, 'at')[1:3] = list(map(str, b))
            child(l, 'effects').append(['justify', 'left', 'bottom'])
    schema.append(['title_block', ['title', Q('Letki v3.1 — PMOS electrical study')],
                   ['date', Q('2026-10-14')], ['rev', Q('Study A')],
                   ['comment', '1', Q('Eight CJ2305; two retained v3 ICs; schematic only')]])


def main():
    if DEST.exists():
        raise SystemExit('Study already exists: edit reviewed study; do not replay this seed helper.')
    DEST.mkdir()
    schema = read(SOURCE / 'ledkiv3_1.kicad_sch')
    child(schema, 'paper')[1] = Q('A3')
    root_id = child(schema, 'uuid')[1]
    lib_root = child(schema, 'lib_symbols')
    libs = {str(s[1]): s for s in children(lib_root, 'symbol')}
    symbols = {str(prop(s, 'Reference')[2]): s for s in children(schema, 'symbol')}
    local = []
    for ref, name in [('U1', 'CH32V003F4P6'), ('U2', 'SN74HC138PWR')]:
        inst = symbols[ref]
        old_id = str(child(inst, 'lib_id')[1])
        definition = libs[old_id]
        old_name = old_id.split(':')[-1]
        definition[1] = Q('LetkiStudy:'+name)
        for unit in children(definition, 'symbol'):
            unit[1] = Q(str(unit[1]).replace(old_name, name))
        prop(definition, 'Value')[2] = Q(name)
        filters = prop(definition, 'ki_fp_filters')
        if filters:
            filters[2] = Q('TSSOP*')
        else:
            definition.append(field('ki_fp_filters', 'TSSOP*'))
        child(inst, 'lib_id')[1] = Q('LetkiStudy:'+name)
        prop(inst, 'Value')[2] = Q(name)
        entry = deepcopy(definition)
        entry[1] = Q(name)
        local.append(entry)
    ti_url = 'https://www.ti.com/lit/ds/symlink/sn74hc138.pdf'
    prop(symbols['U2'], 'Datasheet')[2] = Q(ti_url)
    prop(libs['74xx:74HC138'], 'Datasheet')[2] = Q(ti_url)
    prop(local[1], 'Datasheet')[2] = Q(ti_url)
    write(DEST/'LetkiStudy.kicad_sym', ['kicad_symbol_lib', ['version', '20241209'],
                                      ['generator', 'kicad_symbol_editor'], *local])
    write(DEST/'sym-lib-table', ['sym_lib_table', ['lib', ['name', Q('LetkiStudy')],
        ['type', Q('KiCad')], ['uri', Q('${KIPRJMOD}/LetkiStudy.kicad_sym')],
        ['options', Q('')], ['descr', Q('Exact retained v3 ICs; inherited pin geometry')]]])

    # Make the inherited switch available without touching the original library.
    pcb = read(SOURCE/'ledkiv3_1.kicad_pcb')
    switch = deepcopy(next(f for f in children(pcb, 'footprint') if prop(f, 'Reference')[2] == 'SW1'))
    switch[1] = Q('SW_tactile_TS-1089S')
    switch[:] = [n for n in switch if not (isinstance(n, list) and n[0] in
                 ('at', 'uuid', 'path', 'sheetfile', 'sheetname'))]
    switch.insert(2, ['version', '20241229'])
    switch.insert(3, ['generator', 'pcbnew'])
    prop(switch, 'Reference')[2] = Q('REF**')
    for pad in children(switch, 'pad'):
        pad[:] = [n for n in pad if not (isinstance(n, list) and n[0] in
                  ('net', 'pinfunction', 'pintype', 'uuid'))]
    (DEST/'LetkiStudy.pretty').mkdir()
    write(DEST/'LetkiStudy.pretty/SW_tactile_TS-1089S.kicad_mod', switch)
    write(DEST/'fp-lib-table', ['fp_lib_table', ['lib', ['name', Q('LetkiStudy')],
        ['type', Q('KiCad')], ['uri', Q('${KIPRJMOD}/LetkiStudy.pretty')],
        ['options', Q('')], ['descr', Q('Inherited switch lands; physical suffix audit pending')]]])

    for ref, inst in symbols.items():
        if ref.startswith('D') and ref[1:].isdigit():
            # Swap anode/cathode positions without changing the matrix wiring.
            at = child(inst, 'at')
            at[3] = str((int(at[3])+180) % 360)
            prop(inst, 'Value')[2] = Q('XL-2012UOC')
            inst.append(field('MPN', 'XL-2012UOC'))
            inst.append(field('Sourcing', 'USER_STOCK; rotated polarity for PMOS columns'))
        if ref in {f'R{i}' for i in range(1, 9)}:
            prop(inst, 'Value')[2] = Q('680 1%')
            inst.append(field('MPN', 'RC0805FR-07680RL'))
            inst.append(field('Sourcing', 'UNCONFIRMED; discuss user resistors before purchase'))
        if ref in ('SW1', 'SW2'):
            prop(inst, 'Footprint')[2] = Q('LetkiStudy:SW_tactile_TS-1089S')
        for instances in children(inst, 'instances'):
            for project in children(instances, 'project'):
                project[1] = Q(PROJECT)

    decoder = libs['74xx:74HC138']
    outputs = ['15', '14', '13', '12', '11', '10', '9', '7']
    for unit in children(decoder, 'symbol'):
        for pin in children(unit, 'pin'):
            number = str(child(pin, 'number')[1])
            if number not in outputs:
                continue
            index = outputs.index(number)+1
            endpoint = pin_point(symbols['U2'], pin)
            attached = []
            for wire in children(schema, 'wire'):
                ends = [tuple(round(float(v), 6) for v in xy[1:])
                        for xy in children(child(wire, 'pts'), 'xy')]
                if endpoint in ends:
                    attached.append((wire, ends))
            assert len(attached) == 1, (number, attached)
            wire, ends = attached[0]
            schema.remove(wire)
            other = ends[1] if ends[0] == endpoint else ends[0]
            schema.extend([label(f'S{index}', *other), label(f'SEL{index}', *endpoint)])

    mos = deepcopy(next(s for s in children(read('/usr/share/kicad/symbols/Transistor_FET.kicad_sym'), 'symbol')
                        if s[1] == 'Q_PMOS_GSD'))
    mos[1] = Q('Transistor_FET:Q_PMOS_GSD')
    lib_root.append(mos)
    libs[str(mos[1])] = mos
    resistor = libs['Device:R']

    def place(ref, value, lib_id, x, y, angle, footprint, nets, metadata=()):
        definition = libs[lib_id]
        instance = ['symbol', ['lib_id', Q(lib_id)], ['at', str(x), str(y), str(angle)], ['unit', '1'],
                    ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'], ['uuid', uid()],
                    field('Reference', ref, x+3.81, y-2.54, False),
                    field('Value', value, x+3.81, y, False), field('Footprint', footprint),
                    *[field(k, v) for k, v in metadata],
                    ['instances', ['project', Q(PROJECT), ['path', Q('/'+root_id),
                      ['reference', Q(ref)], ['unit', '1']]]]]
        for unit in children(definition, 'symbol'):
            for pin in children(unit, 'pin'):
                num = str(child(pin, 'number')[1])
                instance.append(['pin', Q(num), ['uuid', uid()]])
                # Explicit pin labels keep the new eight stages independently auditable.
                schema.append(label(nets[num], *pin_point(instance, pin)))
        schema.append(instance)

    rfp = 'Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'
    cj_url = 'https://datasheet.lcsc.com/datasheet/pdf/0d2be3a8b74744bc825762ee6b25df9d.pdf?productCode=C8549'
    for n in range(1, 9):
        x = 45.72+73.66*((n-1) % 4)
        y = 175.26+50.8*((n-1)//4)
        place(f'Q{n}', 'CJ2305', str(mos[1]), x, y, 0, 'Package_TO_SOT_SMD:SOT-23',
              {'1': f'G{n}', '2': 'VCC', '3': f'S{n}'},
              [('MPN', 'CJ2305'), ('Manufacturer', 'JSCJ'), ('LCSC', 'C8549'),
               ('Datasheet', cj_url), ('Sourcing', 'NEW_PART; not on hand')])
        place(f'R{14+n}', '1k 1%', 'Device:R', x-17.78, y, 90, rfp,
              {'1': f'SEL{n}', '2': f'G{n}'},
              [('MPN', 'RC0805FR-071KL'), ('Sourcing', 'UNCONFIRMED; discuss user resistors')])
        place(f'R{22+n}', '10k', 'Device:R', x+20.32, y, 0, rfp,
              {'1': 'VCC', '2': f'G{n}'}, [('MPN', 'RC0805FR-0710KL'), ('Sourcing', 'USER_STOCK')])
        place(f'R{30+n}', '10k', 'Device:R', x+20.32, y+22.86, 0, rfp,
              {'1': 'VCC', '2': f'D{n}'}, [('MPN', 'RC0805FR-0710KL'), ('Sourcing', 'USER_STOCK')])
    # Open-drain address outputs avoid relying on the ambiguous loaded VOH table.
    for n, mcu_pin in enumerate(['17', '16', '15'], 39):
        place(f'R{n}', '4.7k', 'Device:R', 340.36, 175.26+20.32*(n-39), 0, rfp,
              {'1': 'VCC', '2': f'ADDR{n-39}'}, [('MPN', '0805W8J0472T5E'), ('Sourcing', 'USER_STOCK')])
        mcu_def = libs['MCU_WCH_CH32V0:CH32V003FxPx']
        pin = next(p for u in children(mcu_def, 'symbol') for p in children(u, 'pin')
                   if str(child(p, 'number')[1]) == mcu_pin)
        schema.append(label(f'ADDR{n-39}', *pin_point(symbols['U1'], pin)))

    schema.append(['text', Q('PMOS STUDY: 3.3V +/-5% ONLY. LEDs reversed; MCU rows sink.\n'
        'Requires separate active-low PWM / HIGH-blank firmware. NOT FOR ORIGINAL V3.\n'
        '680R rows; 1k gate series; 10k gate/row pulls; OD addresses + 4.7k pulls.\n'
        'SCHEMATIC ONLY. No PCB/fabrication qualification. 3.3V HC138 drive needs bench verification.'),
        ['at', '40.64', '264.16', '0'], ['effects', ['font', ['size', '1', '1']], ['justify', 'left']], ['uuid', uid()]])
    tidy_pmos_schema(schema)
    write(DEST/(PROJECT+'.kicad_sch'), schema)
    project = json.loads((SOURCE/'ledkiv3_1.kicad_pro').read_text())
    for key, value in project['erc']['rule_severities'].items():
        if value == 'ignore':
            project['erc']['rule_severities'][key] = 'warning'
    project['erc']['erc_exclusions'] = []
    (DEST/(PROJECT+'.kicad_pro')).write_text(json.dumps(project, indent=2)+'\n')
    print(DEST/(PROJECT+'.kicad_sch'))


if __name__ == '__main__':
    main()
