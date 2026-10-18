#!/usr/bin/env python3
"""Check identical UART-chain firmware through PC TX at left / PC RX at right."""
import argparse
import binascii
import glob
import json
from pathlib import Path
import secrets
import struct
import time

from uart_demo import SerialLink


def encode(counter, token, hops=0, errors=0):
    data = struct.pack('<BBHII', 1, hops, counter, token, errors)
    return '@' + (data + struct.pack('<H', binascii.crc_hqx(data, 0xffff))).hex().upper()


def decode(line):
    if not line.startswith('@') or len(line) != 29:
        raise ValueError('UART chain response must be @ plus 28 hex digits')
    data = bytes.fromhex(line[1:])
    if len(data) != 14 or binascii.crc_hqx(data[:12], 0xffff) != struct.unpack('<H', data[12:])[0]:
        raise ValueError('UART chain response CRC mismatch')
    version, hops, counter, token, errors = struct.unpack('<BBHII', data[:12])
    if version != 1:
        raise ValueError('Unsupported UART chain protocol version')
    return dict(hops=hops, counter=counter, token=token, errors=errors)


def run_test(link, boards, count, on_reply=print):
    if not 1 <= boards <= 255 or not 1 <= count <= 65536:
        raise ValueError('boards must be 1..255 and count must be 1..65536')
    replies = []
    started = time.monotonic()
    for i in range(count):
        # Random token rejects old/stale replies, even for repeated counters.
        token = secrets.randbits(32)
        counter = ((i*257) ^ (0xa55a if i & 1 else 0)) & 0xffff
        link.send(encode(counter, token))
        reply = decode(link.read_until('@'))
        if reply['counter'] != counter or reply['token'] != token:
            raise RuntimeError('UART chain returned a stale or changed payload')
        if reply['hops'] != boards:
            raise RuntimeError(f"Expected {boards} boards; packet crossed {reply['hops']}")
        if reply['errors']:
            raise RuntimeError(f"Chain reports {reply['errors']} cumulative node/UART errors")
        replies.append(reply)
        on_reply(f'OK counter={counter} hops={boards} errors=0')
        time.sleep(0.1)
    return dict(result='PASS', boards=boards, count=count, replies=replies,
                elapsed_seconds=round(time.monotonic()-started,3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--boards', type=int, default=2)
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--timeout', type=float, default=2.0)
    parser.add_argument('--report', type=Path, help='Save checked replies as JSON')
    args = parser.parse_args()
    if args.list:
        print('\n'.join(sorted(glob.glob('/dev/serial/by-id/*'))) or 'No serial adapter found.')
        return
    if not args.port or args.timeout <= 0 or not 1 <= args.boards <= 255 or not 1 <= args.count <= 65536:
        parser.error('provide --port; boards 1..255; count 1..65536; positive timeout')
    link = SerialLink(args.port, args.timeout)
    result = {'result': 'FAIL', 'port': args.port, 'boards': args.boards}
    try:
        result.update(run_test(link, args.boards, args.count))
        print(f'PASS: {args.count} checked packets through {args.boards} boards at 115200 8N1.')
    except (OSError, RuntimeError, TimeoutError, ValueError, EOFError) as error:
        result['error'] = str(error)
        raise
    finally:
        link.close()
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, TimeoutError, ValueError, EOFError) as error:
        raise SystemExit(str(error))
