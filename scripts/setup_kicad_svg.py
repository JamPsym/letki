#!/usr/bin/env python3
"""Fetch the pinned SVG exporter into ignored tools; never installs globally."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    pin=json.loads((ROOT/'config/kicad-svg-extras.json').read_text())
    directory=ROOT/'.tools/kicad-svg-extras'
    if not directory.exists():subprocess.run(['git','clone','--no-checkout',pin['repository'],str(directory)],check=True)
    revision=subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()
    if revision!=pin['commit']:
        if subprocess.check_output(['git','-C',str(directory),'status','--porcelain'],text=True).strip():raise SystemExit('Refusing to replace modified SVG tool sources')
        subprocess.run(['git','-C',str(directory),'fetch','--depth','1','origin',pin['commit']],check=True)
        subprocess.run(['git','-C',str(directory),'checkout','--detach',pin['commit']],check=True)
    print('Pinned KiCad SVG Extras:',pin['commit'])


if __name__=='__main__':main()
