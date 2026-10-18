#!/usr/bin/env python3
"""Create Study B from checked Study A, preserving both the source and seed.

One-shot schematic creator. No PCB update, regeneration or source promotion.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v3_1_transistor_study import effects, field, label, pin_point, uid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'hw/ledkiv3.1/transistor-study'
PROJECT = 'ledkiv3_1_tme'
DEFAULT_DEST = ROOT / 'hw/ledkiv3.1/tme-study'
RESISTOR_FP = 'Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder'
PMOS_URL = 'https://www.aosmd.com/sites/default/files/res/datasheets/AO3415A.pdf'
NMOS_URL = 'https://www.diodes.com/datasheet/download/DMN2056U.pdf'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=DEFAULT_DEST)
    dest = parser.parse_args().dest.resolve()
    if dest.exists():
        raise SystemExit('Destination exists: edit the candidate, do not replay the creator.')
    dest.mkdir(parents=True)
    for name in ['LetkiStudy.kicad_sym', 'sym-lib-table', 'fp-lib-table']:
        shutil.copy2(SOURCE / name, dest / name)
    shutil.copytree(SOURCE / 'LetkiStudy.pretty', dest / 'LetkiStudy.pretty')
    schema = read(SOURCE / 'ledkiv3_1_pmos.kicad_sch')
    child(schema, 'paper')[1] = Q('A2')
    root_id = child(schema, 'uuid')[1]
    definitions = {str(s[1]): s for s in children(child(schema, 'lib_symbols'), 'symbol')}
    instances = {str(prop(s, 'Reference')[2]): s for s in children(schema, 'symbol')}

    def update(inst, key, value):
        f = prop(inst, key)
        if f:
            f[2] = Q(value)
        else:
            inst.append(field(key, value))

    def point(node):
        return tuple(round(float(v), 6) for v in child(node, 'at')[1:3])

    def endpoints(wire):
        return [tuple(round(float(v), 6) for v in xy[1:])
                for xy in children(child(wire, 'pts'), 'xy')]

    def pins(inst):
        return {str(child(p, 'number')[1]): pin_point(inst, p)
                for u in children(definitions[str(child(inst, 'lib_id')[1])], 'symbol')
                for p in children(u, 'pin')}

    def add_wire(a, b):
        schema.append(['wire', ['pts', ['xy', *map(str, a)], ['xy', *map(str, b)]],
                       ['stroke', ['width', '0'], ['type', 'default']], ['uuid', uid()]])

    def net_label(name, at):
        node = label(name, *at)
        if name == 'GND':
            node[0] = 'global_label'
            node.insert(2, ['shape', 'input'])
        child(node, 'effects').append(['justify', 'right' if name.startswith('ROW') else 'left', 'bottom'])
        schema.append(node)

    # Remove Study A's eight MCU-side row pullups and their isolated stubs.
    # Their references are reused for the new gate pulldowns, never as LED loads.
    for n in range(31, 39):
        inst = instances[f'R{n}']
        for pt in pins(inst).values():
            connected = [w for w in children(schema, 'wire') if pt in endpoints(w)]
            assert len(connected) == 1, (n, pt, 'expected standalone stub')
            wire = connected[0]
            ends = endpoints(wire)
            schema.remove(wire)
            for tag in ['label', 'global_label']:
                for lab in list(children(schema, tag)):
                    if point(lab) in ends:
                        schema.remove(lab)
        schema.remove(inst)

    # Isolate each LED resistor from its former MCU sink stub. Remove its old
    # floating label; the matching label at the MCU is renamed below.
    for n in range(1, 9):
        inst = instances[f'R{n}']
        pt = pins(inst)['2']
        connected = [w for w in children(schema, 'wire') if pt in endpoints(w)]
        assert len(connected) == 1, (n, pt)
        wire = connected[0]
        ends = endpoints(wire)
        other = next(p for p in ends if p != pt)
        schema.remove(wire)
        for tag in ['label', 'global_label']:
            for lab in list(children(schema, tag)):
                if point(lab) == other:
                    schema.remove(lab)
        # New drain stub is deliberately shorter than the detached segment.
        tip = (pt[0], round(pt[1] + 2.54, 6))
        assert tip != other
        add_wire(pt, tip)
        net_label(f'K{n}', tip)
        update(inst, 'Value', '100 1%')
        update(inst, 'MPN', '0805S8F1000T5E')
        update(inst, 'Supplier', 'TME')
        update(inst, 'Supplier code', 'SMD0805-100R-1%')
        update(inst, 'Sourcing', 'VALUE_UNCONFIRMED; user resistors or later purchase, no stock credit')

    for tag in ['label', 'global_label']:
        for lab in children(schema, tag):
            name = str(lab[1])
            if name in {f'D{n}' for n in range(1, 9)}:
                lab[1] = Q(f'ROW{name[1:]}_CTRL')

    for n in range(1, 9):
        inst = instances[f'Q{n}']
        for key, value in [('Value', 'AO3415A'), ('MPN', 'AO3415A'),
                           ('Manufacturer', 'Alpha & Omega Semiconductor'),
                           ('Datasheet', PMOS_URL), ('Supplier', 'TME'),
                           ('Supplier code', 'AO3415A'), ('Sourcing', 'NEW_PART; not on hand')]:
            update(inst, key, value)
        inst[:] = [node for node in inst if not
                   (isinstance(node, list) and node[0] == 'property' and node[1] == 'LCSC')]

    nmos = deepcopy(next(s for s in children(read('/usr/share/kicad/symbols/Transistor_FET.kicad_sym'), 'symbol')
                         if s[1] == 'Q_NMOS_GSD'))
    nmos[1] = Q('Transistor_FET:Q_NMOS_GSD')
    child(schema, 'lib_symbols').append(nmos)
    definitions[str(nmos[1])] = nmos

    def place(ref, value, lib_id, x, y, angle, footprint, nets, metadata=(), wired_gate=False):
        inst = ['symbol', ['lib_id', Q(lib_id)], ['at', str(x), str(y), str(angle)], ['unit', '1'],
                ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'], ['uuid', uid()],
                field('Reference', ref, x + 3.81, y - 1.27, False),
                field('Value', value, x + 3.81, y + 1.27, ref.startswith('Q')),
                field('Footprint', footprint), *[field(k, v) for k, v in metadata],
                ['instances', ['project', Q(PROJECT), ['path', Q('/' + root_id),
                 ['reference', Q(ref)], ['unit', '1']]]]]
        if angle == 90:
            for fname, offset in [('Reference', -5.08), ('Value', -2.54)]:
                child(prop(inst, fname), 'at')[1:4] = [str(x), str(y + offset), '0']
        else:
            for fname in ['Reference', 'Value']:
                child(prop(inst, fname), 'effects').append(['justify', 'left'])
        schema.append(inst)
        for number, pt in pins(inst).items():
            inst.append(['pin', Q(number), ['uuid', uid()]])
            if wired_gate and ((ref.startswith('Q') and number == '1') or
                               (ref.startswith('R') and number == '2')):
                continue
            dx, dy = pt[0] - x, pt[1] - y
            sx, sy = ((1 if dx > 0 else -1), 0) if abs(dx) > abs(dy) else (0, (1 if dy > 0 else -1))
            tip = (round(pt[0] + 5.08*sx, 6), round(pt[1] + 5.08*sy, 6))
            add_wire(pt, tip)
            net_label(nets[number], tip)
        return inst

    for n in range(1, 9):
        x = 45.72 + 73.66*((n - 1) % 4)
        y = 292.1 + 55.88*((n - 1)//4)
        q = place(f'Q{8+n}', 'DMN2056U-7', str(nmos[1]), x, y, 0,
                  'Package_TO_SOT_SMD:SOT-23', {'1': f'NG{n}', '2': 'GND', '3': f'K{n}'},
                  [('MPN', 'DMN2056U-7'), ('Manufacturer', 'Diodes Incorporated'),
                   ('Datasheet', NMOS_URL), ('Supplier', 'TME'), ('Supplier code', 'DMN2056U-7'),
                   ('Sourcing', 'NEW_PART; not on hand')], wired_gate=True)
        r = place(f'R{41+n}', '1k 1%', 'Device:R', x - 17.78, y, 90,
                  RESISTOR_FP, {'1': f'ROW{n}_CTRL', '2': f'NG{n}'},
                  [('MPN', 'RC0805FR-071KL'), ('Sourcing', 'VALUE_UNCONFIRMED; discuss user resistors')],
                  wired_gate=True)
        a, b = pins(r)['2'], pins(q)['1']
        add_wire(a, b)
        net_label(f'NG{n}', (round((a[0]+b[0])/2, 6), a[1]))
        place(f'R{30+n}', '10k', 'Device:R', x + 20.32, y, 0, RESISTOR_FP,
              {'1': f'NG{n}', '2': 'GND'}, [('MPN', 'RC0805FR-0710KL'), ('Sourcing', 'USER_STOCK')])
        # Bias cathodes toward VCC through the row resistor while its NMOS is
        # off: reset/blank rows do not float. Pull current bypasses the LED R.
        place(f'R{49+n}', '10k', 'Device:R', x + 40.64, y - 15.24, 0, RESISTOR_FP,
              {'1': 'VCC', '2': f'K{n}'}, [('MPN', 'RC0805FR-0710KL'), ('Sourcing', 'USER_STOCK')])

    for inst in children(schema, 'symbol'):
        for instances_node in children(inst, 'instances'):
            for project in children(instances_node, 'project'):
                project[1] = Q(PROJECT)
    for node in list(children(schema, 'title_block')) + list(children(schema, 'text')):
        if node[0] == 'title_block' or 'PMOS STUDY' in str(node[1]):
            schema.remove(node)
    schema.append(['title_block', ['title', Q('Letki v3.1 — TME transistor candidate')],
                   ['date', Q('2026-10-14')], ['rev', Q('Study B2 / five tiles')],
                   ['comment', '1', Q('8 AO3415A + 8 DMN2056U-7; two retained v3 ICs; schematic only')]])
    schema.append(['text', Q('STUDY B: common externally regulated 3.3V +/-5% ONLY.\n'
        'Q1-Q8 = AO3415A column sources; Q9-Q16 = DMN2056U-7 row sinks.\n'
        'LEDs reversed vs v3. 100R row limit; 1k gate series; 10k gate pulls.\n'
        'R50-R57 bias cathodes HIGH through row resistors when row NMOS is OFF.\n'
        'Requires v3_1-mosfet firmware: LOW row blank, active-HIGH PWM, OD addresses.\n'
        'NOT FOR ORIGINAL V3. No PCB/fabrication/physical qualification.\n'
        'V3 ghosting fix retained. LED current/temperature, new MOSFET settling and PWM low end need checks.'),
        ['at', '342.9', '266.7', '0'], ['effects', ['font', ['size', '1.2', '1.2']],
        ['justify', 'left']], ['uuid', uid()]])
    write(dest / (PROJECT + '.kicad_sch'), schema)
    project = json.loads((SOURCE / 'ledkiv3_1_pmos.kicad_pro').read_text())
    assert not project['erc']['erc_exclusions']
    assert 'ignore' not in project['erc']['rule_severities'].values()
    (dest / (PROJECT + '.kicad_pro')).write_text(json.dumps(project, indent=2) + '\n')
    print(dest / (PROJECT + '.kicad_sch'))


if __name__ == '__main__':
    main()
