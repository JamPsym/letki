import os
from pathlib import Path
import pty
import select
import sys
import tempfile
import termios
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from uart_link import UartLink
from letki_tui import Worker


class Board:
    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.original = termios.tcgetattr(self.slave)
        self.port = os.ttyname(self.slave)
        self.commands = []
        self.speed, self.paused = 75, False
        self.brightness = 100
        self.wrong_ping = False
        self.frame_busy = 1
        self.error_speed = None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def emit(self, reply):
        data = (reply + '\r\n').encode()
        os.write(self.master, data[:2])
        os.write(self.master, data[2:])

    def status(self):
        return f'speed_ms={self.speed} paused={int(self.paused)} uptime_ms=100 uart_errors=0 tx_dropped=0 brightness_pct={self.brightness}'

    def command(self, raw):
        self.commands.append(raw)
        text = raw.decode('utf-8')
        if text in ('status', 's'): self.emit(self.status())
        elif text.startswith('ping '):
            if text != 'ping silent': self.emit('PONG ' + ('wrong-token' if self.wrong_ping else text[5:]))
        elif text.startswith('t '): self.paused = False; self.emit('OK text updated')
        elif text.startswith('v '):
            if self.error_speed == int(text[2:]): self.emit('ERR speed rejected')
            else: self.speed = int(text[2:]); self.emit('OK speed updated')
        elif text.startswith('b '):
            self.brightness = int(text[2:]); self.emit('OK brightness updated')
        elif text.startswith('f'):
            if self.frame_busy: self.frame_busy -= 1; self.emit('BUSY')
            else: self.emit('FRAME')
        elif text == 'a': self.paused = True; self.emit('ARMED')
        elif text == 'h': self.emit('+ faster; help'); self.emit('t TEXT / v MS')
        else:
            if text == 'p': self.paused = True
            elif text == 'r': self.paused = False
            elif text == '0': self.speed, self.paused = 75, False
            self.emit(self.status())

    def run(self):
        buffer = bytearray()
        try:
            while not self.stop.is_set():
                if not select.select([self.master], [], [], 0.05)[0]: continue
                for byte in os.read(self.master, 4096):
                    if byte == 27:
                        buffer.clear(); self.emit('UART draft cancelled')
                    elif byte == 10:
                        self.command(bytes(buffer)); buffer.clear()
                    else: buffer.append(byte)
        except OSError: pass

    def unplug(self):
        self.stop.set()
        self.thread.join(timeout=1)
        os.close(self.master)
        self.master = None

    def close(self):
        if self.master is not None: self.unplug()
        os.close(self.slave)


class UartLinkTests(unittest.TestCase):
    def setUp(self):
        self.board = Board()
        self.directory = tempfile.TemporaryDirectory()
        self.log = Path(self.directory.name) / 'uart.log'
        self.link = None

    def connect(self):
        self.link = UartLink(self.board.port, self.log)
        return self.link

    def tearDown(self):
        if self.link: self.link.close()
        self.board.close()
        self.directory.cleanup()

    def test_utf8_lines_controls_frame_retry_and_tty_restoration(self):
        link = self.connect()
        self.assertEqual(self.board.commands[0], b'status')
        self.assertTrue(self.board.commands[1].startswith(b'ping '))
        link.set_text('zażółć gęślą jaźń')
        self.assertIn('t zażółć gęślą jaźń'.encode(), self.board.commands)
        link.set_speed(55)
        link.set_brightness(25)
        self.assertEqual(self.board.brightness, 25)
        link.wait(link.send('p'), 'paused=1')
        link.arm()
        link.set_frame(bytes.fromhex('0011223344556677'))
        self.assertEqual(self.board.commands.count(b'f0011223344556677'), 2)
        for ending in ('\n', '\r', '\r\n', '\n\r'):
            marker = link.send('s' + ending)
            self.assertIn('speed_ms=55', link.wait(marker, 'speed_ms='))
        before = list(self.board.commands)
        for invalid in ('t hello\np', 'x' * 259):
            with self.assertRaises(ValueError): link.send(invalid)
        self.assertEqual(self.board.commands, before)
        link.close(); link.close()
        self.assertEqual(termios.tcgetattr(self.board.slave), self.board.original)
        self.assertIn('FRAME', self.log.read_text())

    def test_existing_tui_worker_serializes_uart_jobs(self):
        link = self.connect(); worker = Worker(link)
        try:
            for request in [('text', 'Adaś'), ('speed', 55), ('pause', None),
                            ('resume', None), ('frame', [1] * 8), ('arm', None),
                            ('reset', None), ('help', None)]:
                self.assertTrue(worker.submit(request))
                result = worker.results.get(timeout=2)
                self.assertTrue(result[0], result)
            self.assertFalse(self.board.paused)
            self.assertEqual(self.board.speed, 75)
        finally: worker.close()

    def test_failure_cancels_draft_and_does_not_mark_action_confirmed(self):
        link = self.connect(); self.board.error_speed = 99; worker = Worker(link)
        try:
            worker.submit(('speed', 99))
            result = worker.results.get(timeout=2)
            self.assertFalse(result[0]); self.assertIn('speed rejected', result[3])
            worker.submit(('status', None))
            self.assertTrue(worker.results.get(timeout=2)[0])
            self.assertEqual(self.board.speed, 75)
        finally: worker.close()

    def test_disconnect_wakes_pending_wait_and_close_is_safe(self):
        link = self.connect()
        marker = link.send('ping silent')
        self.board.unplug()
        with self.assertRaises(RuntimeError): link.wait(marker, 'PONG ', timeout=2)
        self.assertFalse(link.connected)
        link.close()

    def test_wrong_connection_echo_rejected_and_open_failure_cleans_up(self):
        self.board.wrong_ping = True
        with self.assertRaisesRegex(RuntimeError, 'Incorrect UART connection reply'):
            self.connect()
        self.assertEqual(termios.tcgetattr(self.board.slave), self.board.original)
        self.log.unlink()  # Constructor released the log even when handshake failed.
        self.assertFalse(self.log.exists())


if __name__ == '__main__': unittest.main()
