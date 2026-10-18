#!/usr/bin/env python3
"""Apply the HRO 2020-12-08 recommended USB lands and PCB-edge position.

Manufacturer drawing: https://datasheet.lcsc.com/datasheet/pdf/
9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948
Uses the manufacturer's 0.60 mm locator holes; keeps the inherited slightly
oversized front retention drills for insertion clearance.
Run official DRC/connectivity after applying this to a routed development copy.
"""
import argparse
import shutil
from pathlib import Path
from kicad_sexpr import child, children, prop, read, write

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'hw/ledkiv4/Letki.pretty/USB_C_Receptacle_HRO_TYPE-C-31-M-12_Head.kicad_mod'


def lands(footprint, mirror):
    sign = -1 if mirror else 1
    for pad in children(footprint, 'pad'):
        number = str(pad[1])
        if not number:
            child(pad, 'size')[1:] = ['0.6', '0.6']
            child(pad, 'drill')[1] = '0.6'
            continue
        at = child(pad, 'at')
        x = float(at[1])
        if number == 'SH':
            at[1] = str(4.325 if x > 0 else -4.325)
            rear = sign * float(at[2]) < 0
            at[2] = str(sign * (-3.1 if rear else 1.08))
            if not rear:
                child(pad, 'size')[2] = '1.7'
        else:
            if number in ('A1', 'A12', 'B1', 'B12'):
                at[1] = str(3.2 if x > 0 else -3.2)
            if number in ('A4', 'A9', 'B4', 'B9'):
                at[1] = str(2.4 if x > 0 else -2.4)
            at[2] = str(sign * -3.67)
            child(pad, 'size')[2] = '1.14'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pcb', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--update-library', action='store_true')
    args = parser.parse_args()
    if args.update_library:
        local = read(LIB)
        lands(local, False)
        write(LIB, local)
    board = read(args.pcb)
    usb = next(f for f in children(board, 'footprint') if prop(f, 'Reference')[2] == 'J4')
    assert child(usb, 'layer')[1] == 'B.Cu' and child(usb, 'at')[1:] == ['20.32', '46.08', '180']
    lands(usb, True)
    outline = next(x for x in children(board, 'gr_rect') if child(x, 'layer')[1] == 'Edge.Cuts')
    child(outline, 'end')[1:] = ['40.64', '49.27']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write(args.output, board)
    if args.output != args.pcb:
        shutil.copy2(args.pcb.with_suffix('.kicad_pro'), args.output.with_suffix('.kicad_pro'))
    rules = ROOT / 'hw/ledkiv4/ledkiv4.kicad_dru'
    if args.output.with_suffix('.kicad_dru').resolve() != rules:
        shutil.copy2(rules, args.output.with_suffix('.kicad_dru'))
    print('USB lands corrected; board edge now 49.27 mm, body protrudes 0.46 mm. DRC required.')


if __name__ == '__main__':
    main()
