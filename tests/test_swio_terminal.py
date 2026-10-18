import importlib.util
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('swio_terminal', ROOT / 'scripts/swio_terminal.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InputTests(unittest.TestCase):
    def test_plain_text_cannot_execute_pause_or_arm_commands(self):
        text = 'zobacz adasiu już nie świeci'
        self.assertEqual(module.display_command(text), 't ' + text)
        self.assertEqual(module.display_command('pause'), 't pause')
        self.assertEqual(module.display_command('Adaś'), 't Adaś')
        for command in ('r', 'p', 'a', 's', '+', 'v 75', 'b 25', 'b 0', 'b -1', 'b', 't hello', 't', 'f0123456789abcdef'):
            self.assertEqual(module.display_command(command), command)

    def test_polish_edit_and_submit(self):
        line = module.InputLine()
        for byte in 't Adaś'.encode(): self.assertIsNone(line.feed(byte))
        self.assertEqual(line.text, 't Adaś')
        line.feed(127)
        self.assertEqual(line.text, 't Ada')
        for byte in 'ś działa'.encode(): line.feed(byte)
        self.assertEqual(line.feed(13), 't Adaś działa')
        self.assertEqual(line.text, '')

    def test_cancel_and_reject_incomplete_utf8(self):
        line = module.InputLine()
        for byte in b't draft': line.feed(byte)
        line.feed(27)
        self.assertEqual(line.feed(10), '')
        line.feed(0xC5)
        with self.assertRaises(ValueError): line.feed(10)
        line.feed(ord('s'))
        self.assertEqual(line.feed(10), 's')

    def test_private_pty_visible_input_and_terminal_restoration(self):
        master, slave = pty.openpty()
        original = termios.tcgetattr(slave)
        backend = "import os,tty; tty.setraw(0); print('Letki v3 SWIO ready',flush=True); data=bytearray();\nwhile True:\n b=os.read(0,1)\n if b==b'\\n':\n  print('ACK='+data.hex(),flush=True);data.clear()\n else:data.extend(b)\n"
        runner = ('import sys; sys.path.insert(0,sys.argv[1]); '
                  'from swio_terminal import run_terminal; '
                  'run_terminal([sys.executable,"-u","-c",sys.argv[2]])')
        process = subprocess.Popen([sys.executable, '-c', runner, str(ROOT / 'scripts'), backend],
                                   stdin=slave, stdout=slave, stderr=slave)
        received = bytearray()
        def wait_for(needle):
            deadline = time.monotonic() + 3
            while needle not in received:
                remaining = deadline - time.monotonic()
                self.assertGreater(remaining, 0, received.decode(errors='replace'))
                if select.select([master], [], [], remaining)[0]:
                    received.extend(os.read(master, 4096))
        try:
            wait_for(b'Letki v3 SWIO ready')
            os.write(master, 't Adaśx'.encode() + b'\x7f')
            wait_for('> t Adaś'.encode())
            self.assertNotIn(b'ACK=', received)
            os.write(master, b'\r')
            wait_for(('ACK=' + 't Adaś'.encode().hex()).encode())
            os.write(master, 'zobacz adasiu już nie świeci'.encode() + b'\r')
            wait_for(('ACK=' + 't zobacz adasiu już nie świeci'.encode().hex()).encode())
            # Exiting with an unsent draft still restores terminal settings.
            os.write(master, b's')
            wait_for(b'> s')
            os.write(master, b'\x03')
            process.wait(timeout=4)
            self.assertEqual(termios.tcgetattr(slave), original)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            os.close(master); os.close(slave)


if __name__ == '__main__': unittest.main()
