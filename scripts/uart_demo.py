#!/usr/bin/env python3
"""Linux PC test for the Letki interface-demo firmware; no extra packages."""
import argparse
import glob
import os
import secrets
import select
import termios
import time
import tty


class SerialLink:
    def __init__(self, port, timeout=2.0):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.timeout = timeout
        self.buffer = bytearray()
        try:
            self.original = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
            settings = termios.tcgetattr(self.fd)
            settings[4] = settings[5] = termios.B115200
            settings[2] &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE | termios.CRTSCTS)
            settings[2] |= termios.CS8 | termios.CLOCAL | termios.CREAD
            termios.tcsetattr(self.fd, termios.TCSANOW, settings)
            termios.tcflush(self.fd, termios.TCIOFLUSH)
        except Exception:
            os.close(self.fd)
            raise

    def close(self):
        try:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.original)
        finally:
            os.close(self.fd)

    def send(self, command):
        data = command.encode('ascii')
        if len(data) > 79 or any(c < 32 or c > 126 for c in data):
            raise ValueError('Command must contain at most 79 printable ASCII characters')
        self._write(data + b'\n')

    def send_utf8(self, command):
        data = command.encode('utf-8')
        if len(data) > 258 or any(ord(c) < 32 or ord(c) == 127 for c in command):
            raise ValueError('Command must contain at most 258 UTF-8 bytes and no control characters')
        self._write(data + b'\n')

    def _write(self, data):
        deadline = time.monotonic() + self.timeout
        while data:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [self.fd], [], remaining)[1]:
                raise TimeoutError('Serial write timed out')
            try:
                data = data[os.write(self.fd, data):]
            except BlockingIOError:
                continue

    def read_until(self, prefix):
        deadline = time.monotonic() + self.timeout
        while True:
            while b'\n' in self.buffer:
                raw, _, rest = self.buffer.partition(b'\n')
                self.buffer = bytearray(rest)
                line = raw.strip(b'\r').decode('ascii', errors='strict')
                if line.startswith('LETKI '):
                    continue
                if line.startswith('ERR ') or line.startswith('I2C ERR '):
                    raise RuntimeError(line)
                if line.startswith(prefix):
                    return line
            if len(self.buffer) > 4096:
                raise RuntimeError('Serial data has no line terminator')
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                raise TimeoutError(f'No {prefix!r} reply; check firmware, wiring and logic levels')
            try:
                data = os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            if not data:
                raise EOFError('Serial port disconnected')
            self.buffer.extend(data)

    def ping(self, token):
        self.send('ping ' + token)
        reply = self.read_until('PONG ')
        if reply != 'PONG ' + token:
            raise RuntimeError(f'Incorrect UART echo: {reply!r}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='/dev/serial/by-id/... or /dev/ttyUSB0')
    parser.add_argument('--list', action='store_true', help='List serial adapters without opening them')
    parser.add_argument('--count', type=int, default=20, help='Number of UART pings or I2C transactions')
    parser.add_argument('--timeout', type=float, default=2.0)
    parser.add_argument('--command', help='Send one command, e.g. "mode target"')
    parser.add_argument('--i2c', action='store_true', help='Select controller mode and send checked counters')
    args = parser.parse_args()
    if args.list:
        ports = sorted(glob.glob('/dev/serial/by-id/*'))
        if not ports:
            ports = sorted(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))
        print('\n'.join(ports) if ports else 'No serial adapter found.')
        return
    if not args.port:
        parser.error('--port is required; use --list to find an adapter')
    if not 1 <= args.count <= 65536 or args.timeout <= 0:
        parser.error('--count must be 1..65536 and --timeout must be positive')
    if args.command and args.i2c:
        parser.error('--command and --i2c cannot be combined')
    link = SerialLink(args.port, args.timeout)
    try:
        if args.command:
            link.send(args.command)
            line = link.read_until('')
            print(line)
            if line == 'QUEUED': print(link.read_until('I2C OK '))
            return
        for n in range(args.count if not args.i2c else 1):
            link.ping(f'{secrets.token_hex(8)}-{n}')
        link.send('status')
        status = link.read_until('STATUS ')
        print(status)
        fields = dict(field.split('=', 1) for field in status.split()[1:])
        if fields.get('uart_errors') != '0' or fields.get('tx_dropped') != '0':
            raise RuntimeError('Firmware reported UART receive errors or dropped replies')
        if args.i2c:
            link.send('mode controller')
            print(link.read_until('STATUS mode=controller'))
            for n in range(args.count):
                link.send(f'send {n}')
                link.read_until('QUEUED')
                reply = link.read_until('I2C OK ')
                if reply != f'I2C OK counter={n} reason=reply CRC':
                    raise RuntimeError(f'Unexpected I2C confirmation: {reply}')
                print(reply)
                time.sleep(0.25)
            print(f'PASS: {args.count} I2C counter/CRC confirmations.')
        else:
            print(f'PASS: {args.count} distinct UART ping/replies at 115200 8N1.')
    finally:
        link.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, TimeoutError, ValueError, EOFError) as error:
        raise SystemExit(str(error))
