#!/usr/bin/env python3
"""Send UTF-8 line commands to active Letki text firmware over USART; never flashes."""
import argparse
import glob
import secrets
import time
from uart_demo import SerialLink


def reply_prefix(command):
    if command.startswith('t ') or command == 't': return 'OK text updated'
    if command.startswith('v '): return 'OK speed updated'
    if command.startswith('b '): return 'OK brightness updated'
    if command.startswith('e '): return 'OK effect updated'
    if command.startswith('m '): return 'OK mode updated'
    if command.startswith(('f', 'g')): return 'FRAME'
    if command == 'a': return 'ARMED'
    if command == 'ping' or command.startswith('ping '): return 'PONG'
    if command in ('h', '?', 'help'): return ('+ faster', 't TEXT;')
    return 'speed_ms='


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--command', action='append', help='Repeat for successive acknowledged commands')
    parser.add_argument('--check', action='store_true', help='Check 20 exact echoes and zero UART error/drop counters')
    args = parser.parse_args()
    if args.list:
        ports = sorted(glob.glob('/dev/serial/by-id/*') or glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))
        print('\n'.join(ports) if ports else 'No serial adapter found.')
        return
    if not args.port: parser.error('--port is required')
    if args.check and args.command: parser.error('--check and --command cannot be combined')
    link = SerialLink(args.port)
    try:
        time.sleep(0.3)
        if args.check:
            for n in range(20): link.ping(f'{secrets.token_hex(8)}-{n}')
            link.send('status')
            status = link.read_until('speed_ms=')
            print(status)
            fields = dict(field.split('=', 1) for field in status.split())
            if fields.get('uart_errors') != '0' or fields.get('tx_dropped') != '0':
                raise RuntimeError('Firmware reported UART errors or dropped output')
            print('PASS: 20 exact UART echoes at 115200 8N1; zero errors/drops.')
        else:
            for command in args.command or ['status']:
                link.send_utf8(command)
                reply = link.read_until(reply_prefix(command))
                print(reply)
                if command in ('h', '?', 'help') and reply.startswith('+ faster'):
                    print(link.read_until('t TEXT'))
                if command == 'ping' or command.startswith('ping '):
                    if reply != 'PONG' + command[4:]: raise RuntimeError('Incorrect UART echo')
    finally:
        link.close()


if __name__ == '__main__':
    try: main()
    except (OSError, RuntimeError, TimeoutError, ValueError, EOFError) as error:
        raise SystemExit(str(error))
