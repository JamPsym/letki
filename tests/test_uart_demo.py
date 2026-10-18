import importlib.util
import os
from pathlib import Path
import pty
import threading
import unittest

spec = importlib.util.spec_from_file_location('uart_demo', Path(__file__).resolve().parents[1] / 'scripts/uart_demo.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = pty.openpty()
        self.link = module.SerialLink(os.ttyname(self.slave), timeout=0.2)

    def tearDown(self):
        self.link.close()
        os.close(self.master)
        os.close(self.slave)

    def test_roundtrip_over_real_tty_with_fragmented_reply(self):
        commands = []
        def board():
            data = bytearray()
            while b'\n' not in data:
                data.extend(os.read(self.master, 80))
            commands.append(bytes(data))
            os.write(self.master, b'LETKI ready\nPO')
            os.write(self.master, b'NG unique-token\r\n')
        thread = threading.Thread(target=board)
        thread.start()
        self.link.ping('unique-token')
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(commands, [b'ping unique-token\n'])

    def test_wrong_echo_rejected(self):
        os.write(self.master, b'PONG old-token\n')
        with self.assertRaisesRegex(RuntimeError, 'Incorrect UART echo'):
            self.link.ping('new-token')

    def test_legacy_lfcr_status_does_not_hide_next_acknowledgement(self):
        os.write(self.master, b'speed_ms=75\n\rOK brightness updated\n')
        self.assertEqual(self.link.read_until('speed_ms='), 'speed_ms=75')
        self.assertEqual(self.link.read_until('OK '), 'OK brightness updated')

    def test_mixed_endings_and_split_crlf_preserve_consecutive_replies(self):
        os.write(self.master, b'speed_ms=75\r\nOK speed updated\n\rPONG token\r')
        self.assertEqual(self.link.read_until('speed_ms='), 'speed_ms=75')
        self.assertEqual(self.link.read_until('OK '), 'OK speed updated')
        os.write(self.master, b'\n')
        self.assertEqual(self.link.read_until('PONG '), 'PONG token')

    def test_timeout_and_firmware_errors(self):
        with self.assertRaises(TimeoutError): self.link.read_until('PONG')
        os.write(self.master, b'I2C ERR counter=1 reason=NACK\n')
        with self.assertRaisesRegex(RuntimeError, 'NACK'):
            self.link.read_until('I2C OK')

    def test_invalid_command_rejected_before_write(self):
        for command in ('x' * 80, 'ping\nmode controller', 'Adaś'):
            with self.assertRaises(ValueError): self.link.send(command)

    def test_utf8_text_commands_and_bounded_input(self):
        text = 't zażółć gęślą jaźń'
        self.link.send_utf8(text)
        self.assertEqual(os.read(self.master, 1024), (text + '\n').encode('utf-8'))
        largest = 't ' + '\U0001f600' * 64
        self.link.send_utf8(largest)
        self.assertEqual(os.read(self.master, 1024), (largest + '\n').encode('utf-8'))
        for command in ('t ' + '\U0001f600' * 65, 't hello\np', 't hi\x1b', 's\x00'):
            with self.assertRaises(ValueError): self.link.send_utf8(command)


if __name__ == '__main__': unittest.main()
