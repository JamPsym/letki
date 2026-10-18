"""Acknowledged UART transport for the active text-firmware TUI."""
import os
from pathlib import Path
import re
import secrets
import select
import termios
import threading
import time

from uart_demo import SerialLink

STATUS = re.compile(r'^speed_ms=\d+ paused=[01] uptime_ms=\d+ uart_errors=\d+ tx_dropped=\d+(?: brightness_pct=(?:100|[1-9]?\d))?$')


class UartLink:
    """Keep one 115200 8N1 port open; retain logs and wake waits on disconnect."""
    def __init__(self, port, log_path):
        self.lines = []
        self.condition = threading.Condition()
        self.log = Path(log_path).open('w')
        self.serial = None
        self.reader = None
        self.closed = False
        self.error = None
        self.stop = threading.Event()
        self.label = 'UART · ' + Path(port).resolve().name
        try:
            self.serial = SerialLink(port)
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            time.sleep(0.3)
            # Cancel a leftover UART draft before the first complete command.
            # ESC preserves display state; LF could commit another client's draft.
            self.send('\x1b')
            status = self.wait(self.send('status'), 'speed_ms=', 3)
            if not STATUS.fullmatch(status):
                raise RuntimeError('TTY requires the active USART text firmware')
            token = secrets.token_hex(8)
            reply = self.wait(self.send('ping ' + token), 'PONG ', 3)
            if reply != 'PONG ' + token: raise RuntimeError('Incorrect UART connection reply')
        except TimeoutError as error:
            self.close()
            raise TimeoutError(f'No UART response on {port}. Close other serial apps (such as picocom) and check the board connection.') from error
        except Exception:
            self.close()
            raise

    @property
    def connected(self):
        return not self.closed and self.error is None

    def _record(self, line):
        with self.condition:
            self.log.write(line + '\n')
            self.log.flush()
            self.lines.append(line)
            self.condition.notify_all()

    def _read(self):
        buffer = bytearray()
        try:
            while not self.stop.is_set():
                if not select.select([self.serial.fd], [], [], 0.1)[0]: continue
                try: data = os.read(self.serial.fd, 4096)
                except BlockingIOError: continue
                if not data: raise EOFError('Serial port disconnected')
                buffer.extend(data)
                while b'\n' in buffer:
                    raw, _, rest = buffer.partition(b'\n')
                    buffer = bytearray(rest)
                    self._record(raw.strip(b'\r').decode('utf-8', errors='replace'))
                if len(buffer) > 4096: raise RuntimeError('UART reply has no line terminator')
        except Exception as error:
            if not self.stop.is_set():
                with self.condition:
                    self.error = str(error)
                    self._record('ERROR UART disconnected: ' + self.error)

    def send(self, text):
        with self.condition:
            if not self.connected: raise RuntimeError(self.error or 'UART closed')
            marker = len(self.lines)
            try:
                if text == '\x1b': self.serial._write(b'\x1b')
                else:
                    # TUI actions use SWIO's byte-command spelling. On UART
                    # every complete command, including one key, needs LF.
                    command = text.rstrip('\r\n')
                    self.serial.send_utf8(command)
            except OSError as error:
                self.error = str(error)
                self.condition.notify_all()
                raise
            return marker

    def _wait(self, marker, predicate, description, timeout):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                for line in self.lines[marker:]:
                    if predicate(line): return line
                    if line.startswith('ERR '): raise RuntimeError(line)
                if not self.connected: raise RuntimeError(self.error or 'UART closed')
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError('No UART reply ' + description)
                self.condition.wait(remaining)

    def wait(self, marker, expected, timeout=5):
        return self._wait(marker, lambda line: expected in line, repr(expected), timeout)

    def set_text(self, text):
        if len(text) > 64 or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in text):
            raise ValueError('Invalid display message')
        self.wait(self.send('t ' + text), 'OK text updated')

    def set_speed(self, milliseconds):
        if not 10 <= milliseconds <= 500: raise ValueError('Speed must be 10..500 ms')
        self.wait(self.send(f'v {milliseconds}'), 'OK speed updated')

    def set_brightness(self, percent):
        if not 0 <= percent <= 100: raise ValueError('Brightness must be 0..100 percent')
        self.wait(self.send(f'b {percent}'), 'OK brightness updated')

    def set_frame(self, pixels):
        if len(pixels) != 8: raise ValueError('A display frame has eight columns')
        command = 'f' + bytes(pixels).hex()
        for _ in range(3):
            reply = self._wait(self.send(command), lambda line: line in ('FRAME', 'BUSY'), 'FRAME/BUSY', 2)
            if reply == 'FRAME': return
            time.sleep(0.008)
        raise RuntimeError('Display remained busy')

    def arm(self):
        self.wait(self.send('a'), 'ARMED')

    def close(self):
        with self.condition:
            if self.closed: return
            self.closed = True
            self.stop.set()
            self.condition.notify_all()
        if self.reader is not None: self.reader.join(timeout=1)
        try:
            if self.serial is not None:
                try: self.serial.close()
                except (OSError, termios.error) as error:
                    self._record('ERROR UART cleanup: ' + str(error))
        finally:
            self.log.close()

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
