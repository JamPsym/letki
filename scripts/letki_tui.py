#!/usr/bin/env python3
"""Vim-style controller for the current Letki v3 display firmware."""
import argparse
from collections import deque
import curses
from dataclasses import dataclass
from pathlib import Path
import queue
import re
import sys
import threading
import time

from swio_link import SwioLink
from uart_link import UartLink

ROOT = Path(__file__).resolve().parents[1]
STATUS = re.compile(r'speed_ms=(\d+) paused=([01]) uptime_ms=(\d+)')
ACTIONS = [('Edit message', 'i'), ('Set scroll speed', 'v'), ('Set brightness', 'b'), ('Pause / resume', 'Space'),
           ('Arm one scroll cycle', 'a'), ('Reset defaults', '0'),
           ('Clear message', ':clear'), ('Refresh status', 's'), ('Firmware help', '?')]
HELP = [
    'TABS       1/2/3 · gt/gT · Tab/Shift+Tab; j/k select, Enter activate',
    'TEXT       i edit · v speed · b brightness · Enter apply · Esc normal/cancel',
    'EDITOR     h/l move · w/b words · 0/$ ends · x delete · i/a insert',
    'PLAYBACK   Space toggle · p pause · r resume · a single cycle · 0 reset',
    'SPEED      + faster / - slower, 5 ms steps within 10..500 ms/pixel',
    'PIXELS     hjkl move · Space/x toggle · w send · c clear · I invert',
    'PIXELS     H edits 16 hex digits; a sent frame holds native scrolling',
    'LOGS       j/k scroll · gg oldest · G newest · Ctrl+d/u ten lines',
    'COMMANDS   :text TEXT :speed MS :brightness PCT :frame HEX :send :clear :invert',
    'COMMANDS   :pause :resume :arm :reset :status :help :quit',
    'QUIT       q / :quit; last board state remains, edits are volatile',
    'HOST FRAME r cannot exit this mode; send text or use 0 to scroll',
    'HELP       ? opens/closes help; q/Esc closes help or cancels an editor',
]


@dataclass
class Editor:
    kind: str
    text: str
    cursor: int = 0
    insert: bool = True

    def key(self, key):
        if key == '\x1b':
            if self.insert:
                self.insert = False
                return None
            return 'cancel'
        if key in ('\n', '\r', curses.KEY_ENTER):
            return 'apply'
        if key in (curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_HOME, curses.KEY_END):
            self.cursor = {curses.KEY_LEFT: max(0, self.cursor - 1),
                           curses.KEY_RIGHT: min(len(self.text), self.cursor + 1),
                           curses.KEY_HOME: 0, curses.KEY_END: len(self.text)}[key]
            return None
        if self.insert:
            if key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                if self.cursor:
                    self.text = self.text[:self.cursor-1] + self.text[self.cursor:]
                    self.cursor -= 1
            elif key == curses.KEY_DC:
                self.text = self.text[:self.cursor] + self.text[self.cursor+1:]
            elif isinstance(key, str) and key.isprintable() and len(self.text) < 1024:
                self.text = self.text[:self.cursor] + key + self.text[self.cursor:]
                self.cursor += len(key)
            return None
        if key == 'q': return 'cancel'
        if key == 'i': self.insert = True
        elif key == 'a': self.cursor = min(len(self.text), self.cursor + 1); self.insert = True
        elif key == 'h': self.cursor = max(0, self.cursor - 1)
        elif key == 'l': self.cursor = min(len(self.text), self.cursor + 1)
        elif key == '0': self.cursor = 0
        elif key == '$': self.cursor = len(self.text)
        elif key == 'x': self.text = self.text[:self.cursor] + self.text[self.cursor+1:]
        elif key == 'w':
            match = re.search(r'\S+\s*', self.text[self.cursor:])
            if match: self.cursor += match.end()
        elif key == 'b':
            match = re.search(r'\S+\s*$', self.text[:self.cursor])
            self.cursor = match.start() if match else 0
        return None


class Model:
    def __init__(self):
        self.tab = 0
        self.selection = 0
        self.editor = None
        self.draft_text = 'ZOBACZ ADAŚ DZIAŁA'
        self.current_text = None
        self.speed = None
        self.brightness = None
        self.paused = None
        self.uptime = None
        self.last_status = None
        self.display_mode = 'scroll (session estimate)'
        self.frame = [0] * 8
        self.sent_frame = None
        self.x = self.y = 0
        self.logs = deque(maxlen=600)
        self.log_offset = 0
        self.notice = 'i edits text · 2 opens pixel editor · ? shows all keys'
        self.busy = False
        self.help = False
        self.prefix = ''
        self.quit = False
        self.connected = True
        self.transport_label = 'WCH-LinkE · SWIO'

    def line(self, line):
        if self.log_offset: self.log_offset = min(599, self.log_offset + 1)
        self.logs.append(line)
        match = STATUS.search(line)
        if match:
            speed, paused, uptime = map(int, match.groups())
            if self.uptime is not None and uptime < self.uptime:
                self.current_text = None
                self.sent_frame = None
                self.display_mode = 'scroll (reset observed)'
            self.speed, self.paused, self.uptime = speed, bool(paused), uptime
            self.last_status = time.monotonic()
            brightness = re.search(r'brightness_pct=(\d+)', line)
            if brightness: self.brightness = int(brightness.group(1))

    def completed(self, action, value):
        if action == 'text':
            self.current_text = value.translate(str.maketrans(
                'abcdefghijklmnopqrstuvwxyząćęłńóśźż', 'ABCDEFGHIJKLMNOPQRSTUVWXYZĄĆĘŁŃÓŚŹŻ'))
            self.draft_text = value
            self.display_mode = 'scroll / repeat'
        elif action == 'frame':
            self.sent_frame = list(value)
            self.display_mode = 'host frame / held'
        elif action == 'arm': self.display_mode = 'single cycle'
        elif action == 'reset': self.display_mode = 'scroll / repeat'
        if action != 'status': self.notice = 'Confirmed: ' + action

    def request(self, action, value=None):
        if action == 'text':
            if len(value) > 64 or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value):
                raise ValueError('Text accepts up to 64 characters, without control characters')
        elif action == 'speed':
            value = int(value)
            if not 10 <= value <= 500: raise ValueError('Speed must be 10..500 ms per pixel')
        elif action == 'brightness':
            value = int(value)
            if not 0 <= value <= 100: raise ValueError('Brightness must be 0..100 percent')
        elif action == 'frame':
            if isinstance(value, str):
                if not re.fullmatch(r'[0-9a-fA-F]{16}', value):
                    raise ValueError('Frame needs exactly 16 hex digits')
                value = list(bytes.fromhex(value))
            if len(value) != 8 or any(not 0 <= n <= 255 for n in value):
                raise ValueError('Frame needs eight bytes')
            value = list(value)
        return action, value

    def begin(self, kind, text):
        self.editor = Editor(kind, text, len(text))
        self.notice = 'Enter applies · Esc switches to normal mode · Esc again cancels'

    def ex(self, text):
        command, _, argument = text.partition(' ')
        if command in ('q', 'quit'): self.quit = True; return None
        if command in ('t', 'text'): return self.request('text', argument)
        if command in ('v', 'speed'): return self.request('speed', argument)
        if command in ('b', 'brightness'): return self.request('brightness', argument)
        if command in ('f', 'frame'): return self.request('frame', argument)
        if command == 'send': return self.request('frame', self.frame)
        if command == 'invert': self.frame = [n ^ 255 for n in self.frame]; return None
        if command == 'clear': return self.request('text', '')
        if command in ('pause', 'resume', 'arm', 'reset', 'status', 'help'):
            return self.request(command)
        raise ValueError('Unknown command; ? lists supported commands')

    def key(self, key):
        if self.editor:
            result = self.editor.key(key)
            if result == 'cancel': self.editor = None; self.notice = 'Draft cancelled; nothing sent'
            elif result == 'apply':
                editor = self.editor
                try:
                    request = self.ex(editor.text) if editor.kind == 'command' else self.request(editor.kind, editor.text)
                except (ValueError, TypeError) as error:
                    self.notice = str(error)
                    return None
                self.editor = None
                return request
            return None
        if key == '\x03': self.quit = True; return None
        if self.help:
            if key in ('?', '\x1b', 'q'): self.help = False
            return None
        if self.prefix:
            prefix, self.prefix = self.prefix, ''
            if prefix == 'g' and key in ('t', 'T'):
                self.tab = (self.tab + (1 if key == 't' else -1)) % 3
            elif prefix == 'g' and key == 'g':
                if self.tab == 2: self.log_offset = max(0, len(self.logs) - 1)
                elif self.tab == 1: self.x = self.y = 0
                else: self.selection = 0
            return None
        if key == 'g': self.prefix = 'g'; return None
        if key == 'q': self.quit = True
        elif key in ('1', '2', '3'): self.tab = int(key) - 1
        elif key == '\t': self.tab = (self.tab + 1) % 3
        elif key == curses.KEY_BTAB: self.tab = (self.tab - 1) % 3
        elif key == ':': self.begin('command', '')
        elif key == '?': self.help = True; return self.request('help')
        elif key == 'i': self.begin('text', self.draft_text)
        elif key == 'v': self.begin('speed', str(self.speed or 75))
        elif key == 'b': self.begin('brightness', str(self.brightness if self.brightness is not None else 100))
        elif key in ('p', 'r', 'a', '0', 'S'):
            return self.request({'p': 'pause', 'r': 'resume', 'a': 'arm', '0': 'reset', 'S': 'status'}[key])
        elif key in ('+', '-'):
            return self.request('faster' if key == '+' else 'slower')
        elif self.tab == 1:
            if key in ('h', curses.KEY_LEFT): self.x = max(0, self.x - 1)
            elif key in ('l', curses.KEY_RIGHT): self.x = min(7, self.x + 1)
            elif key in ('k', curses.KEY_UP): self.y = max(0, self.y - 1)
            elif key in ('j', curses.KEY_DOWN): self.y = min(7, self.y + 1)
            elif key in (' ', 'x'): self.frame[self.x] ^= 1 << self.y
            elif key in ('w', 's', '\n', '\r', curses.KEY_ENTER): return self.request('frame', self.frame)
            elif key == 'c': self.frame = [0] * 8
            elif key == 'I': self.frame = [n ^ 255 for n in self.frame]
            elif key == 'H': self.begin('frame', bytes(self.frame).hex())
        elif self.tab == 2:
            if key in ('k', curses.KEY_UP): self.log_offset = max(0, min(len(self.logs) - 1, self.log_offset + 1))
            elif key in ('j', curses.KEY_DOWN): self.log_offset = max(0, self.log_offset - 1)
            elif key == '\x15': self.log_offset = max(0, min(len(self.logs) - 1, self.log_offset + 10))
            elif key == '\x04': self.log_offset = max(0, self.log_offset - 10)
            elif key == 'G': self.log_offset = 0
            elif key == 's': return self.request('status')
        else:
            if key in ('j', curses.KEY_DOWN): self.selection = min(len(ACTIONS) - 1, self.selection + 1)
            elif key in ('k', curses.KEY_UP): self.selection = max(0, self.selection - 1)
            elif key in ('h', curses.KEY_LEFT): self.tab = (self.tab - 1) % 3
            elif key in ('l', curses.KEY_RIGHT): self.tab = (self.tab + 1) % 3
            elif key == 'G': self.selection = len(ACTIONS) - 1
            elif key == 's': return self.request('status')
            elif key == ' ': return self.request('resume' if self.paused else 'pause')
            elif key in ('\n', '\r', curses.KEY_ENTER):
                choices = ['text', 'speed', 'brightness', 'toggle', 'arm', 'reset', 'clear', 'status', 'help']
                action = choices[self.selection]
                if action == 'text': self.begin('text', self.draft_text)
                elif action == 'speed': self.begin('speed', str(self.speed or 75))
                elif action == 'brightness': self.begin('brightness', str(self.brightness if self.brightness is not None else 100))
                elif action == 'toggle': return self.request('resume' if self.paused else 'pause')
                elif action == 'clear': return self.request('text', '')
                elif action == 'help': self.help = True; return self.request('help')
                else: return self.request(action)
        return None


class DemoLink:
    """Offline UI demonstration; never accesses USB or flashes hardware."""
    def __init__(self):
        self.lines = ['Letki v3 SWIO ready. h=help']
        self.condition = threading.Condition()
        self.speed, self.paused = 75, False
        self.brightness = 100
        self.started = time.monotonic()
    def status(self):
        self.lines.append(f'speed_ms={self.speed} paused={int(self.paused)} uptime_ms={int((time.monotonic()-self.started)*1000)} brightness_pct={self.brightness}')
    def send(self, text):
        marker = len(self.lines)
        if text == 'p': self.paused = True
        elif text == 'r': self.paused = False
        elif text == '0': self.speed, self.paused, self.brightness = 75, False, 100
        elif text == 'h': self.lines.append('+ faster; - slower; p pause; r resume; 0 reset; s status')
        self.status()
        return marker
    def wait(self, marker, expected, timeout=5):
        return next(line for line in self.lines[marker:] if expected in line)
    def set_text(self, text): self.paused = False; self.lines.append('OK text updated')
    def set_speed(self, value): self.speed = value; self.lines.append('OK speed updated')
    def set_brightness(self, value): self.brightness = value; self.lines.append('OK brightness updated')
    def set_frame(self, value): self.lines.append('FRAME')
    def arm(self): self.paused = True; self.lines.append('ARMED')
    def close(self): pass


class Worker:
    def __init__(self, link):
        self.link = link
        self.jobs = queue.Queue(maxsize=8)
        self.results = queue.Queue()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
    def submit(self, request):
        try: self.jobs.put_nowait(request); return True
        except queue.Full: return False
    def run(self):
        while not self.stop.is_set():
            try: action, value = self.jobs.get(timeout=0.1)
            except queue.Empty: continue
            try:
                if action == 'text': self.link.set_text(value)
                elif action == 'speed': self.link.set_speed(value)
                elif action == 'brightness': self.link.set_brightness(value)
                elif action in ('faster', 'slower'):
                    line = self.link.wait(self.link.send('s'), 'speed_ms=')
                    speed = int(STATUS.search(line).group(1))
                    value = max(10, min(500, speed + (-5 if action == 'faster' else 5)))
                    self.link.set_speed(value)
                elif action == 'frame': self.link.set_frame(value)
                elif action == 'arm': self.link.arm()
                else:
                    key = {'pause': 'p', 'resume': 'r', 'reset': '0', 'status': 's', 'help': 'h'}[action]
                    marker = self.link.send(key)
                    self.link.wait(marker, '+ faster' if action == 'help' else 'speed_ms=')
                if action != 'status':
                    self.link.wait(self.link.send('s'), 'speed_ms=')
                self.results.put((True, action, value, None))
            except Exception as error:
                # Escape any partially transmitted firmware editor before another job.
                try: self.link.send('\x1b')
                except Exception: pass
                self.results.put((False, action, value, str(error)))
            finally: self.jobs.task_done()
    def close(self):
        self.stop.set()
        self.thread.join(timeout=6)
        if self.thread.is_alive():
            # Closing the transport makes pending waits fail before the UI exits.
            self.link.close()
            self.thread.join(timeout=3)
        else: self.link.close()


def render(screen, model, demo=False):
    height, width = screen.getmaxyx()
    screen.erase()
    def put(y, x, text, style=0):
        if 0 <= y < height and 0 <= x < width:
            try: screen.addnstr(y, x, str(text), max(0, width-x-1), style)
            except curses.error: pass
    if height < 24 or width < 76:
        put(0, 0, 'Letki needs a terminal at least 76 columns x 24 rows. Resize or press q.')
        screen.refresh(); return
    accent = curses.color_pair(1) | curses.A_BOLD
    muted = curses.color_pair(2)
    good = curses.color_pair(3)
    warning = curses.color_pair(4)
    put(0, 2, 'LETKI  /  DISPLAY CONTROL', accent)
    put(0, width-24, 'OFFLINE DEMO' if demo else model.transport_label, muted)
    for n, label in enumerate(('TEXT', 'PIXELS', 'LOGS')):
        put(2, 2+n*17, f' {n+1} {label} ', curses.A_REVERSE if model.tab == n else muted)
    put(2, width-27, 'BUSY' if model.busy else 'READY' if model.connected else 'DISCONNECTED', good if model.connected else warning)
    speed = '?' if model.speed is None else str(model.speed)
    state = 'unknown' if model.paused is None else 'PAUSED' if model.paused else 'RUNNING'
    if model.display_mode.startswith('host frame'): state = 'FRAME HELD'
    if model.last_status is not None and time.monotonic()-model.last_status > 8: state = 'STATUS STALE'
    brightness = '?' if model.brightness is None else str(model.brightness)
    put(4, 2, f'{state}    {speed} ms/pixel    {brightness}% light    uptime {(model.uptime or 0)/1000:.1f}s', warning if model.paused else good)
    put(5, 2, f'Mode: {model.display_mode}', muted)
    if model.help:
        put(7, 2, 'KEY MAP', accent)
        for i, line in enumerate(HELP): put(8+i, 2, line)
    elif model.tab == 0:
        put(7, 2, 'PLAYBACK', accent)
        for i, (label, binding) in enumerate(ACTIONS):
            put(9+i, 2, ('› ' if model.selection == i else '  ') + label,
                curses.A_REVERSE if model.selection == i else 0)
            put(9+i, 31, binding, muted)
        put(7, 45, 'MESSAGE', accent)
        put(9, 45, 'Confirmed this session:', muted)
        text = model.current_text if model.current_text is not None else '(not queried by firmware)'
        for i in range(3): put(10+i, 45, text[i*(width-48):(i+1)*(width-48)])
        put(14, 45, 'Draft · i to edit · 64 characters', muted)
        for i in range(3): put(15+i, 45, model.draft_text[i*(width-48):(i+1)*(width-48)])
        put(height-6, 2, 'Text is edited locally. No letters become commands while typing.', muted)
    elif model.tab == 1:
        put(7, 2, '8 × 8 FRAME DRAFT', accent)
        for y in range(8):
            put(9+y, 2, str(y+1), muted)
            for x in range(8):
                lit = bool(model.frame[x] & (1 << y))
                style = good if lit else muted
                if (x,y) == (model.x,model.y): style |= curses.A_REVERSE
                put(9+y, 5+x*4, ' ● ' if lit else ' · ', style)
        put(17, 5, ' '.join(f' {x+1} ' for x in range(8)), muted)
        put(9, 43, 'hjkl move · Space toggles')
        put(11, 43, 'w sends draft to the board')
        put(13, 43, 'c clears · I inverts draft')
        put(15, 43, 'H edits raw frame hex')
        put(17, 43, '0 returns to native scrolling', warning)
        put(height-6, 2, 'Draft hex: ' + bytes(model.frame).hex(), muted)
        if model.sent_frame is not None: put(height-5, 2, 'Last confirmed: ' + bytes(model.sent_frame).hex(), muted)
    else:
        put(7, 2, 'DEVICE LOG  ·  j/k scroll  ·  gg/G oldest/newest', accent)
        count = height-14
        end = max(0, len(model.logs)-model.log_offset)
        for i,line in enumerate(list(model.logs)[max(0,end-count):end]):
            put(9+i, 2, line, warning if line.startswith(('ERR','ERROR')) else 0)
    put(height-3, 2, model.notice, warning if model.notice.startswith(('ERR','Error')) else muted)
    footer = 'NORMAL · gt tabs · i text · v speed · b brightness · : command · ? help · q quit'
    cursor = None
    if model.editor:
        editor = model.editor
        footer = f'{"INSERT" if editor.insert else "NORMAL EDIT"} / {editor.kind.upper()}  ·  Enter apply  ·  Esc normal/cancel'
        start = max(0, editor.cursor-(width-8))
        prefix = ':' if editor.kind == 'command' else '> '
        put(height-4, 2, prefix+editor.text[start:], accent)
        cursor = (height-4, min(width-2, 2+len(prefix)+editor.cursor-start))
    put(height-1, 2, footer, accent)
    try:
        curses.curs_set(1 if cursor else 0)
        if cursor: screen.move(*cursor)
    except curses.error: pass
    screen.refresh()


def application(screen, link, demo=False):
    curses.start_color()
    background = -1
    try: curses.use_default_colors()
    except curses.error: background = curses.COLOR_BLACK
    for number, color in enumerate((curses.COLOR_CYAN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW), 1):
        curses.init_pair(number, color, background)
    screen.keypad(True)
    screen.timeout(80)
    if hasattr(curses, 'set_escdelay'): curses.set_escdelay(25)
    model = Model()
    model.transport_label = getattr(link, 'label', model.transport_label)
    worker = Worker(link)
    worker.submit(('status', None))
    cursor = 0
    last_poll = time.monotonic()
    try:
        while not model.quit:
            with link.condition: lines = link.lines[cursor:]; cursor = len(link.lines)
            for line in lines: model.line(line)
            while True:
                try: success, action, value, error = worker.results.get_nowait()
                except queue.Empty: break
                if success: model.completed(action, value)
                else: model.notice = 'Error: ' + error; model.line('ERROR ' + error)
            model.busy = worker.jobs.unfinished_tasks > 0
            if ((hasattr(link, 'process') and link.process.poll() is not None) or
                    not getattr(link, 'connected', True)):
                model.connected = False
                model.notice = 'Device disconnected; q exits. Reopen the TUI to reconnect.'
            if time.monotonic()-last_poll >= 2 and not model.busy and model.connected:
                worker.submit(('status', None)); last_poll = time.monotonic()
            render(screen, model, demo)
            try: key = screen.get_wch()
            except curses.error: continue
            request = model.key(key)
            if request:
                if not model.connected: model.notice = 'Error: device disconnected'
                elif worker.submit(request): model.notice = 'Sending: ' + request[0]
                else: model.notice = 'Error: command queue full; wait for pending replies'
    finally:
        worker.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument('--demo', action='store_true', help='Offline UI preview without a probe')
    transport.add_argument('--port', '--tty', dest='port', help='Use USART at 115200 8N1 through this tty; default is SWIO')
    args = parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error('Run in an interactive terminal (or use a PTY)')
    path = ROOT / 'build/tui'
    path.mkdir(parents=True, exist_ok=True)
    link = None
    try:
        if args.demo: link = DemoLink()
        elif args.port:
            print(f'Connecting through {args.port} at 115200 8N1…', flush=True)
            link = UartLink(args.port, path / (time.strftime('%Y%m%d-%H%M%S')+'-uart.log'))
        else:
            print('Connecting to the v3 board; opening SWIO restarts it…', flush=True)
            link = SwioLink(path / (time.strftime('%Y%m%d-%H%M%S')+'.log'))
        curses.wrapper(application, link, args.demo)
    except (OSError, RuntimeError, TimeoutError, KeyboardInterrupt, curses.error) as error:
        raise SystemExit(str(error))
    finally:
        if isinstance(link, (SwioLink, UartLink)) and not link.log.closed:
            link.close()


if __name__ == '__main__': main()
