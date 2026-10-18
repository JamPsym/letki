#!/usr/bin/env python3
"""Install the pinned KiCadRoutingTools CLI locally on Linux x86_64."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / 'config/kicad-routing.json').read_text())
DEST = ROOT / '.tools/kicad-routing-tools'
ENV = ROOT / '.tools/kicad-routing-env'


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise SystemExit('This installation pin targets Linux x86_64.')
    if not DEST.exists():
        DEST.parent.mkdir(parents=True, exist_ok=True)
        run('git', 'init', DEST)
        run('git', '-C', DEST, 'remote', 'add', 'origin', PIN['repository'])
        run('git', '-C', DEST, 'fetch', '--depth=1', 'origin', PIN['commit'])
        run('git', '-C', DEST, 'checkout', '--detach', 'FETCH_HEAD')
    head = subprocess.check_output(['git', '-C', str(DEST), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN['commit']:
        raise SystemExit(f'Existing tool checkout has a different revision: {head}. Preserve it and resolve the pin explicitly.')
    dirty = subprocess.check_output(['git', '-C', str(DEST), 'status', '--porcelain'], text=True)
    if dirty.strip():
        raise SystemExit('Tool sources have local changes; preserve them before reinstalling.')
    if not ENV.exists():
        # System KiCad bindings are compiled for Arch's system Python.
        run(sys.executable, '-m', 'venv', '--system-site-packages', ENV)
    python = ENV / 'bin/python'
    run(python, '-m', 'pip', 'install', *PIN['python_dependencies'])
    artifact = PIN['linux_x86_64_engine']
    binary = DEST / 'rust_router/grid_router.so'
    if not binary.exists() or hashlib.sha256(binary.read_bytes()).hexdigest() != artifact['sha256']:
        req = urllib.request.Request(artifact['url'], headers={'User-Agent': 'Letki/KiCadRoutingTools'})
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != artifact['sha256']:
            raise SystemExit('Routing engine checksum mismatch; downloaded bytes were not installed.')
        temporary = binary.with_suffix('.download')
        temporary.write_bytes(payload)
        temporary.replace(binary)
    run(sys.executable, ROOT / 'scripts/kicad_routing.py', 'doctor')
    print('Ready: make pcb-check / make pcb-preview. See docs/kicad-routing.md.')


if __name__ == '__main__':
    main()
