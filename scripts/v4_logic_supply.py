#!/usr/bin/env python3
"""Apply the reviewed 3.3 V MCU supply and buffered UART to the unrouted v4.

One-time development transformation. Pin maps follow the linked manufacturer
datasheets; source and exported-netlist checks are independent of this helper.
"""
from copy import deepcopy
from pathlib import Path
from kicad_sexpr import Quoted as Q, child, children, prop, read, write
from v4_buffer_rows import effects, field, instance, label, lib, pins, endpoint

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'hw/ledkiv4'


def box_symbol(name, mapping, width=7.62, height=10.16):
    """mapping: number, name, electrical type, x, y, orientation."""
    result = ['symbol', Q(name), ['pin_names', ['offset', '0.635']],
              ['in_bom', 'yes'], ['on_board', 'yes'],
              field('Reference', 'U', 0, -height-2.54, False),
              field('Value', name, 0, -height-5.08, False),
              ['symbol', Q(name+'_0_1'),
               ['rectangle', ['start', str(-width), str(height)],
                ['end', str(width), str(-height)],
                ['stroke', ['width', '0'], ['type', 'default']],
                ['fill', ['type', 'background']]]]]
    unit = ['symbol', Q(name+'_1_1')]
    for number, text, kind, x, y, angle in mapping:
        unit.append(['pin', kind, 'line', ['at', str(x), str(y), str(angle)],
                     ['length', '5.08'], ['name', Q(text), effects()],
                     ['number', Q(str(number)), effects()]])
    result.append(unit)
    return result


def main():
    path = PROJECT / 'ledkiv4.kicad_sch'
    s = read(path)
    assert not children(read(PROJECT/'ledkiv4.kicad_pcb'), 'segment'), 'PCB already routed'
    insts = {prop(i, 'Reference')[2]: i for i in children(s, 'symbol')}
    assert 'U4' not in insts and 'U6' not in insts, 'Supply/UART stage already applied'
    definitions = child(s, 'lib_symbols')
    power = lib('/usr/share/kicad/symbols/power.kicad_sym', '+3V3')
    power[1] = Q('power:+3V3')
    definitions.append(power)
    # Only these existing power symbols supply the MCU, its local bypass,
    # SWIO voltage reference and two button contacts. LED driver rail stays VCC.
    for ref in ('#PWR07', '#PWR020', '#PWR010', '#PWR018'):
        node = insts[ref]
        assert child(node, 'lib_id')[1] == 'power:VCC', ref
        child(node, 'lib_id')[1] = Q('power:+3V3')
        prop(node, 'Value')[2] = Q('+3V3')
    for n in children(s, 'global_label'):
        if n[1] == 'VCC' and child(n, 'at')[1] == '335.28':
            n[1] = Q('+3V3')
    # Detach MCU UART from the edge contacts; all connector labels remain.
    for name, new, y in [('UTX', 'MCU_UTX', '50.8'), ('URX', 'MCU_URX', '53.34')]:
        nodes = [n for n in children(s, 'label') if n[1] == name
                 and child(n, 'at')[1:3] == ['129.54', y]]
        assert len(nodes) == 1, (name, nodes)
        nodes[0][1] = Q(new)
    uart = box_symbol('SN74LVC2G125DCUR', [
        ('1', '~{1OE}', 'input', -12.7, -7.62, 0),
        ('2', '1A_TX', 'input', -12.7, 5.08, 0),
        ('3', '2Y_RX', 'output', 12.7, -2.54, 180),
        ('4', 'GND', 'power_in', 0, -15.24, 90),
        ('5', '2A_RX', 'input', -12.7, -2.54, 0),
        ('6', '1Y_TX', 'output', 12.7, 5.08, 180),
        ('7', '~{2OE}', 'input', 12.7, -7.62, 180),
        ('8', 'VCC', 'power_in', 0, 15.24, 270)])
    ldo = box_symbol('ME6206A33M3G', [
        ('1', 'GND', 'power_in', 0, -10.16, 90),
        ('2', 'VOUT', 'power_out', 12.7, 0, 180),
        ('3', 'VIN', 'power_in', -12.7, 0, 0)], height=5.08)
    local = read(PROJECT/'Letki.kicad_sym')
    for definition in (uart, ldo):
        local.append(deepcopy(definition))
        cached = deepcopy(definition)
        cached[1] = Q('Letki:'+str(definition[1]))
        definitions.append(cached)
    write(PROJECT/'Letki.kicad_sym', local)
    u4 = instance(s, 'Letki:SN74LVC2G125DCUR', uart, 'U4',
                  'SN74LVC2G125DCUR', 'Package_SO:VSSOP-8_2.3x2mm_P0.5mm', 250.19, 45.72)
    u6 = instance(s, 'Letki:ME6206A33M3G', ldo, 'U6',
                  'ME6206A33M3G', 'Package_TO_SOT_SMD:SOT-23', 50.8, 228.6)
    for node, manufacturer, code, url in [
        (u4, 'TI', 'C21404', 'https://www.ti.com/lit/ds/symlink/sn74lvc2g125.pdf'),
        (u6, 'MICRONE', 'C35259', 'https://img.ichunt.com/doc/pdf/cms/201808/29/f71d85f01883a662ed366ee77b8e7c47.pdf')]:
        prop(node, 'Datasheet')[2] = Q(url)
        node.extend([field('Manufacturer', manufacturer), field('LCSC', code)])
    def connect(node, definition, pin, net):
        p = endpoint(node, pins(definition)[str(pin)])
        n = label(net, *p)
        if net == '+3V3':
            n[0] = 'global_label'
            n.insert(2, ['shape', 'input'])
        s.append(n)
    for pin, net in {1:'GND', 2:'MCU_UTX', 3:'MCU_URX', 4:'GND',
                     5:'UART_RX_IN', 6:'UART_TX_OUT', 7:'GND', 8:'+3V3'}.items():
        connect(u4, uart, pin, net)
    for pin, net in {1:'GND', 2:'+3V3', 3:'VCC'}.items():
        connect(u6, ldo, pin, net)
    resistor = next(n for n in children(definitions, 'symbol') if n[1] == 'Device:R')
    cap = next(n for n in children(definitions, 'symbol') if n[1] == 'Device:C')
    for ref, value, x, y, net1, net2 in [
        ('R26', '2.2k', 299.72, 38.1, 'UART_TX_OUT', 'UTX'),
        ('R27', '2.2k', 299.72, 66.04, 'URX', 'UART_RX_IN'),
        ('R28', '100k', 210.82, 40.64, '+3V3', 'MCU_UTX'),
        ('R29', '100k', 210.82, 68.58, '+3V3', 'UART_RX_IN')]:
        r = instance(s, 'Device:R', resistor, ref, value,
                     'Resistor_SMD:R_0603_1608Metric', x, y)
        connect(r, resistor, 1, net1); connect(r, resistor, 2, net2)
    for ref, value, x, y, net, footprint in [
        ('C7', '100n', 330.2, 45.72, '+3V3', 'Capacitor_SMD:C_0603_1608Metric'),
        ('C8', '4.7u 16V X7R', 25.4, 228.6, 'VCC', 'Capacitor_SMD:C_0805_2012Metric'),
        ('C9', '4.7u 16V X7R', 83.82, 228.6, '+3V3', 'Capacitor_SMD:C_0805_2012Metric')]:
        c = instance(s, 'Device:C', cap, ref, value, footprint, x, y)
        connect(c, cap, 1, net); connect(c, cap, 2, 'GND')
    write(path, s)
    print('Added 3.3 V MCU regulator and dual UART buffering; LED rail remains 5 V.')


if __name__ == '__main__':
    main()
