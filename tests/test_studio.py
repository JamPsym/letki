#!/usr/bin/env python3
"""Desktop smoke test; every display operation goes to a tracked simulator."""
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="letki-studio-") as private:
    path = str(Path(private) / "display.sock")
    daemon = subprocess.Popen([str(ROOT / "build/control/letkid"), "--simulate", "--socket", path], cwd=ROOT)
    try:
        until = time.monotonic() + 4
        while not Path(path).exists():
            if daemon.poll() is not None or time.monotonic() > until:
                raise RuntimeError("Isolated simulated service did not start")
            time.sleep(.02)
        result = subprocess.run([str(ROOT / "build/control/letki-control"), "--smoke-test",
                                 "--simulate", "--socket", path,
                                 "--library", str(Path(private) / "library.json")], cwd=ROOT, timeout=20)
        raise SystemExit(result.returncode)
    finally:
        daemon.terminate()
        daemon.wait(timeout=6)
