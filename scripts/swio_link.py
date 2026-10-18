"""Shared UTF-8-compatible SWIO tooling and automated probe connection."""

import os
from pathlib import Path
import pty
import re
import signal
import subprocess
import threading
import time

def build_terminal():
    ROOT = Path(__file__).resolve().parents[1]
    SOURCE = ROOT / ".tools/ch32fun/minichlink"
    OUTPUT = ROOT / "build/tools/minichlink-utf8"
    if not (SOURCE / "Makefile").exists():
        raise SystemExit("Missing local ch32fun tools; see docs/arch-setup.md")
    
    # Upstream's POSIX ReadKBByte returns plain char. An unsigned-char build
    # prevents high UTF-8 bytes becoming negative and corrupting packed DATA0.
    # Build into ignored artifacts without altering the downloaded tool sources.
    names = re.search(r"^C_S:=(.+)$", (SOURCE / "Makefile").read_text(), re.M)[1].split()
    sources = [SOURCE / name for name in names]
    dependencies = [*sources, *SOURCE.glob("*.h"), Path(__file__).resolve()]
    if not OUTPUT.exists() or any(p.stat().st_mtime > OUTPUT.stat().st_mtime
                                  for p in dependencies):
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "cc", "-O0", "-funsigned-char", "-Wall", "-Wno-unused-function",
            "-DCH32V003", "-DMINICHLINK", "-DTERMINAL_INPUT_BUFFER=0",
            '-DVERSION="letki-utf8"', f"-I{SOURCE}",
            *map(str, sources), "-lpthread", "-lusb-1.0", "-ludev", "-o", str(OUTPUT),
        ], check=True)
    
    return OUTPUT


class SwioLink:
    """Keep one probe connection open, with acknowledged commands and cleanup."""

    def __init__(self, log_path):
        self.lines = []
        self.condition = threading.Condition()
        self.log = Path(log_path).open("w")
        self.master, slave = pty.openpty()
        self.process = subprocess.Popen(
            ["stdbuf", "-oL", str(build_terminal()), "-C", "linke", "-T"],
            stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        os.close(slave)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.wait(0, "Part UUID: d7-73-ab-cd-41-3f-bd-ff", 10)
            self.wait(0, "Letki v3 SWIO ready", 10)
        except Exception:
            self.close()
            raise

    def _read(self):
        for raw in iter(self.process.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").strip()
            self.log.write(line + "\n")
            self.log.flush()
            with self.condition:
                self.lines.append(line)
                self.condition.notify_all()
        with self.condition:
            self.condition.notify_all()

    def send(self, text):
        with self.condition:
            marker = len(self.lines)
            os.write(self.master, text.encode("utf-8"))
            return marker

    def wait(self, marker, expected, timeout=5):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                for line in self.lines[marker:]:
                    if expected in line:
                        return line
                    if line.startswith("ERR "):
                        raise RuntimeError(line)
                if self.process.poll() is not None:
                    raise RuntimeError("SWIO terminal stopped: " + " | ".join(self.lines[-5:]))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"No SWIO reply {expected!r}")
                self.condition.wait(remaining)

    def set_speed(self, milliseconds):
        self.wait(self.send(f"v {milliseconds}\n"), "OK speed updated")

    def set_brightness(self, percent):
        if not 0 <= percent <= 100: raise ValueError('Brightness must be 0..100 percent')
        self.wait(self.send(f'b {percent}\n'), 'OK brightness updated')

    def set_text(self, text):
        if not 0 <= len(text) <= 64 or any(c in text for c in "\r\n\x1b"):
            raise ValueError("Invalid display message")
        self.wait(self.send("t " + text + "\n"), "OK text updated")

    def set_frame(self, pixels):
        if len(pixels) != 8:
            raise ValueError("A display frame has eight columns")
        for _ in range(3):
            marker = self.send("f" + bytes(pixels).hex() + "\n")
            deadline = time.monotonic() + 2
            with self.condition:
                while not any(line == "FRAME" or line == "BUSY"
                              for line in self.lines[marker:]):
                    if self.process.poll() is not None:
                        raise RuntimeError("SWIO terminal stopped")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("No live-frame reply")
                    self.condition.wait(remaining)
                if "FRAME" in self.lines[marker:]:
                    return
            time.sleep(0.008)
        raise RuntimeError("Display remained busy")

    def arm(self):
        self.wait(self.send("a"), "ARMED")
        time.sleep(0.016)  # Allow the queued blank frame to reach the whole display.

    def close(self):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join(timeout=2)
        os.close(self.master)
        self.log.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
