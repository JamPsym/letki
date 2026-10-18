#!/usr/bin/env python3
"""Control/check the separate v3 hardware-PWM experiment over USART; never flashes."""
import argparse
import json
import secrets
import time
from pathlib import Path
from uart_demo import SerialLink


def fields(line):
    return {k: int(v) for k, v in (item.split('=', 1) for item in line.split()[1:] if '=' in item)
            if v.isdecimal()}


def command(link, text):
    link.send(text)
    if text in ('status', 's'):
        return link.read_until('PWM ')
    if text == 'samples':
        rows = [link.read_until('PAD ') for _ in range(8)]
        if [fields(row)['row'] for row in rows] != list(range(1, 9)):
            raise RuntimeError('Missing or duplicate pad reports')
        return rows
    return link.read_until('OK ')


def check(link, walk=False):
    results = []
    command(link, 'diag')
    for duty in (0, 25, 50, 75, 100):
        command(link, f'd {duty}')
        time.sleep(.03)
        command(link, 'clear')
        time.sleep(.35)
        samples = command(link, 'samples')
        for line in samples:
            row = fields(line)
            if row['mismatch'] or row['high']+row['low'] < 20:
                raise RuntimeError('Bad/insufficient digital pad observations: '+line)
            if duty == 0 and row['high'] or duty == 100 and row['low']:
                raise RuntimeError('Incorrect 0/100% output: '+line)
            if 0 < duty < 100 and not (row['high'] and row['low']):
                raise RuntimeError('PWM did not alternate at pad: '+line)
        print(f'PASS duty={duty}: all eight pads match timer phase', flush=True)
        results.append({'duty': duty, 'samples': samples})
    if walk:
        command(link, 'd 50')
        for row in range(1, 9):
            command(link, f'row {row}')
            print(f'Row {row}/8: all eight columns, 50% PWM — inspect every LED', flush=True)
            time.sleep(2)
        command(link, 'diag')
    for n in range(20):
        link.ping(f'{secrets.token_hex(8)}-{n}')
    status = command(link, 'status')
    parsed = fields(status)
    if parsed['errors'] or parsed['drops']:
        raise RuntimeError('UART errors/drops: '+status)
    command(link, 'fade')
    print('PASS: digital PWM pad checks and 20 exact USART echoes; optical/frequency measurements are separate.', flush=True)
    return {'duties': results, 'status': status, 'visual_row_sweep': walk,
            'limit': 'On-chip digital pads checked away from edges; no external frequency/current/optical measurement claimed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--command', action='append')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--walk', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.check and args.command:
        parser.error('--check and --command are mutually exclusive')
    link = SerialLink(args.port, timeout=3)
    try:
        time.sleep(.3)
        link._write(b'\x1b')
        result = check(link, args.walk) if args.check else [command(link, text) for text in args.command or ['status']]
        if args.output:
            args.output.write_text(json.dumps(result, indent=2)+'\n')
        elif not args.check:
            print(json.dumps(result, indent=2))
    finally:
        link.close()


if __name__ == '__main__':
    main()
