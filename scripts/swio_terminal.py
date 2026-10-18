#!/usr/bin/env python3
"""SWIO terminal with visible UTF-8 input and local line editing."""
import codecs
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import tty
from swio_link import build_terminal


def display_command(line):
    """Keep explicit controls; treat other input as display text, never raw keys."""
    if line in ('', '+', '-', 'p', 'r', '0', 's', 'h', '?', 'a', 't', 'b'):
        return line
    if line.startswith('b '):
        return line
    if line.startswith('t '):
        return line
    if line.startswith(('v ', 'b ')) and line[2:].strip().isascii() and line[2:].strip().isdigit():
        return line
    if len(line) == 17 and line[0] == 'f' and all(c in '0123456789abcdefABCDEF' for c in line[1:]):
        return line
    return 't ' + line


class InputLine:
    """Only Enter submits a locally edited command to the board."""
    def __init__(self):
        self.decoder = codecs.getincrementaldecoder('utf-8')('strict')
        self.clear()

    def clear(self):
        self.text = ''
        self.invalid = False
        self.decoder.reset()

    def feed(self, byte):
        if byte == 3:
            raise KeyboardInterrupt
        if byte in (27, 21):  # Esc / Ctrl+U
            self.clear()
        elif byte in (8, 127):
            if self.decoder.getstate()[0]:
                self.decoder.reset()
            else:
                self.text = self.text[:-1]
        elif byte in (10, 13):
            if self.invalid or self.decoder.getstate()[0]:
                self.clear()
                raise ValueError('Invalid or overlong UTF-8 input; nothing sent')
            text = self.text
            self.clear()
            return text
        elif byte >= 32:
            try:
                text = self.decoder.decode(bytes([byte]))
            except UnicodeDecodeError:
                self.invalid = True
                self.decoder.reset()
                return None
            if len(self.text) + len(text) > 1024 or any(127 <= ord(c) < 160 for c in text):
                self.invalid = True
            else:
                self.text += text
        return None


def run_terminal(command, stdin_fd=None, stdout=None):
    stdin_fd = sys.stdin.fileno() if stdin_fd is None else stdin_fd
    stdout = sys.stdout if stdout is None else stdout
    interactive = os.isatty(stdin_fd) and stdout.isatty()
    original = termios.tcgetattr(stdin_fd) if interactive else None
    master, slave = pty.openpty()
    child = None
    draft = InputLine()
    output, pending = bytearray(), bytearray()
    previous_cr = False
    text_firmware = None
    paused = False

    def draw():
        if interactive:
            stdout.write('\r\033[2K> ' + draft.text)
            stdout.flush()

    def show(line):
        if interactive:
            stdout.write('\r\033[2K')
        stdout.write(line.rstrip('\r\n') + '\n')
        stdout.flush()
        draw()

    try:
        # minichlink changes only its private PTY, never the user's terminal.
        child = subprocess.Popen(command, stdin=slave, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        os.close(slave)
        slave = None
        if interactive:
            tty.setraw(stdin_fd)
            settings = termios.tcgetattr(stdin_fd)
            settings[1] = original[1]  # Preserve normal output newline handling.
            termios.tcsetattr(stdin_fd, termios.TCSANOW, settings)
            show('Type display text or an explicit command, then Enter. Backspace edits; Esc cancels; Ctrl+C exits.')
        os.set_blocking(master, False)
        input_open = True
        while True:
            reads = [child.stdout.fileno()] + ([stdin_fd] if input_open else [])
            ready, writable, _ = select.select(reads, [master] if pending else [], [], 0.25)
            if master in writable:
                try:
                    del pending[:os.write(master, pending)]
                except BlockingIOError:
                    pass
            if child.stdout.fileno() in ready:
                chunk = os.read(child.stdout.fileno(), 4096)
                if not chunk:
                    if output:
                        show(output.decode('utf-8', errors='replace'))
                    break
                output.extend(chunk)
                while b'\n' in output:
                    raw, _, rest = output.partition(b'\n')
                    output = bytearray(rest)
                    line = raw.decode('utf-8', errors='replace')
                    if 'Letki v3 SWIO ready' in line:
                        text_firmware = True
                        show('Text mode: ordinary text is sent as t TEXT. r resumes; p pauses; a holds at the start.')
                    elif 'LETKI interfaces ready' in line:
                        text_firmware = False
                    show(line)
                    if text_firmware and 'speed_ms=' in line and 'paused=' in line:
                        is_paused = 'paused=1' in line
                        if is_paused and not paused:
                            show('Display paused/armed. Enter r to resume scrolling.')
                        paused = is_paused
                if len(output) > 4096:
                    show(output.decode('utf-8', errors='replace'))
                    output.clear()
            if stdin_fd in ready:
                chunk = os.read(stdin_fd, 4096)
                if not chunk:
                    input_open = False
                for byte in chunk:
                    if previous_cr and byte == 10:
                        previous_cr = False
                        continue
                    previous_cr = byte == 13
                    try:
                        line = draft.feed(byte)
                    except ValueError as error:
                        show(str(error))
                        continue
                    if line is not None:
                        if text_firmware is None:
                            show('Wait for the firmware startup banner before sending input.')
                            continue
                        if text_firmware:
                            line = display_command(line)
                        if line:
                            show('> ' + line)
                        pending.extend((line + '\n').encode('utf-8'))
                    draw()
            if not input_open and not pending:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if child is not None:
            if child.poll() is None:
                child.send_signal(signal.SIGINT)
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            child.stdout.close()
        if original is not None:
            termios.tcsetattr(stdin_fd, termios.TCSANOW, original)
            stdout.write('\r\033[2K\n')
            stdout.flush()
        os.close(master)
        if slave is not None:
            os.close(slave)
    return child.returncode if child is not None else 1


def main():
    output = build_terminal()
    return run_terminal(['stdbuf', '-oL', str(output), '-C', 'linke', '-T'])


if __name__ == '__main__':
    raise SystemExit(main())
