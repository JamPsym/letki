#!/usr/bin/env python3
"""Export explicit v3.1 population variants and an optional read-only forecast.

This never reserves stock, acknowledges delivery, creates a cart or orders.
Placement CSV is a native-coordinate review aid, not a released assembler file.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def expand(text):
    refs = []
    for token in text.split():
        match = re.fullmatch(r'([A-Z]+)(\d+)-\1(\d+)', token)
        if match:
            prefix, first, last = match.groups()
            refs.extend(prefix+str(i) for i in range(int(first), int(last)+1))
        else:
            if not re.fullmatch(r'[A-Z]+\d+', token):
                raise ValueError(token)
            refs.append(token)
    return refs


def normalized(value):
    return value.lower().replace(' ', '').replace('µ', 'u')


def write_csv(path, rows):
    with path.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, default=ROOT/'hw/ledkiv3.1/ledkiv3_1.kicad_pcb')
    parser.add_argument('--config', type=Path, default=ROOT/'config/v3_1-bom.json')
    parser.add_argument('--inventory-snapshot', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'build/hardware/v3_1-integration/bom')
    args = parser.parse_args()
    board = args.board.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    netlist = args.output/'netlist.xml'
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(netlist.resolve()), str(board.with_suffix('.kicad_sch'))], check=True, stdout=subprocess.DEVNULL)
    parts = {c.attrib['ref']: c for c in ET.parse(netlist).getroot().findall('components/comp')}
    config = json.loads(args.config.read_text())
    tiles, pull_tiles = config['batch_tiles'], config['pullup_tiles']
    assert 0 <= pull_tiles <= tiles
    rows, assigned, by_ref = [], set(), {}
    for group in config['groups']:
        refs = expand(group['refs'])
        assert not (assigned & set(refs)), 'Duplicate references'
        assigned.update(refs)
        for ref in refs:
            part = parts[ref]
            assert normalized(part.findtext('value')) == normalized(group['value']), ref
            fields = {f.attrib['name']: f.text for f in part.findall('fields/field')}
            if fields.get('MPN'):
                assert fields['MPN'] in group.get('allowed_cad_MPNs', [group['MPN']]), (ref, fields['MPN'])
            by_ref[ref] = group
        population = group.get('population', 'ALL_TILES')
        batch_count = len(refs)*(pull_tiles if population == 'ONE_PULLUP_TILE' else tiles)
        rows.append({'references': ' '.join(refs), 'value': group['value'], 'MPN': group['MPN'],
                     'footprint': parts[refs[0]].findtext('footprint'), 'supplier': group['supplier'],
                     'supplier_code': group['code'], 'per_ordinary_tile': 0 if population == 'ONE_PULLUP_TILE' else len(refs),
                     'per_pullup_tile': len(refs), 'five_tile_batch': batch_count,
                     'note': group.get('note', '')})
    assert assigned | set(config['excluded_from_purchases']) == set(parts)
    assert not assigned & set(config['excluded_from_purchases'])
    assert sum(r['per_ordinary_tile'] for r in rows) == 140
    assert sum(r['per_pullup_tile'] for r in rows) == 142
    assert sum(r['five_tile_batch'] for r in rows) == 702
    write_csv(args.output/'population-bom.csv', rows)

    import pcbnew
    pcb = pcbnew.LoadBoard(str(board))
    assert {fp.GetReference() for fp in pcb.GetFootprints()} == set(parts), 'PCB is not synchronized with schematic'
    for fp in pcb.GetFootprints():
        assert str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName()) == parts[fp.GetReference()].findtext('footprint'), ('PCB footprint not synchronized', fp.GetReference())
    placements = []
    for fp in pcb.GetFootprints():
        ref = fp.GetReference()
        if ref not in assigned:
            continue
        x, y = pcbnew.ToMM(fp.GetPosition())
        placements.append({'reference': ref, 'MPN': by_ref[ref]['MPN'], 'x_mm': x, 'y_mm': y,
                           'rotation_native_deg': fp.GetOrientationDegrees(),
                           'side': 'top' if fp.GetLayer() == pcbnew.F_Cu else 'bottom',
                           'ordinary_tile_fit': 'DNP' if ref in ['R11','R12'] else 'FIT',
                           'pullup_tile_fit': 'FIT',
                           'first_provisioning': 'DNP until PD7 GPIO confirmed; then power off and fit' if ref == 'R49' else ''})
    write_csv(args.output/'placement-review-native.csv', sorted(placements, key=lambda r: r['reference']))
    forecast = []
    if args.inventory_snapshot:
        inventory = json.loads(args.inventory_snapshot.read_text())
        lots = inventory['lots']
        grouped = {}
        for row in rows:
            grouped.setdefault(row['MPN'], dict(row, five_tile_batch=0))['five_tile_batch'] += row['five_tile_batch']
        for mpn, row in grouped.items():
            exact = [lot for lot in lots if lot['MPN'] == mpn]
            available = sum(lot['available_for_other_projects'] for lot in exact)
            pending_uncommitted = sum(max(0, lot.get('pending',0)-lot.get('hard_reserved',0)-lot.get('planned',0)) for lot in exact if lot['kind'] == 'incoming_order')
            need = row['five_tile_batch']
            forecast.append({'MPN':mpn, 'required':need, 'available_after_existing_holds_and_plans':available,
                             'planned_shelf_use':min(need,available), 'remaining_available_if_used':max(0,available-need),
                             'shortfall_from_on_hand':max(0,need-available), 'uncommitted_pending_NOT_stock':pending_uncommitted,
                             'conditional_shortfall_after_receipt':max(0,need-available-pending_uncommitted),
                             'supplier':row['supplier'], 'supplier_code':row['supplier_code']})
        write_csv(args.output/'stock-forecast.csv', forecast)
    summary = {'scope':config['scope'], 'board':str(board.relative_to(ROOT)),
               'board_sha256':hashlib.sha256(board.read_bytes()).hexdigest(),
               'schematic_sha256':hashlib.sha256(board.with_suffix('.kicad_sch').read_bytes()).hexdigest(),
               'config_sha256':hashlib.sha256(args.config.read_bytes()).hexdigest(),
               'batch_tiles':tiles, 'pullup_tiles':pull_tiles, 'ordinary_tile_components':140,
               'pullup_tile_components':142, 'five_tile_components':702,
               'SMT_batch_components':697, 'THT_batch_headers':5,
               'stock_forecast':forecast, 'extra_hardware':config['extras_for_five_tiles'],
               'release_status':'DEVELOPMENT; placement review CSV is not a fabrication/assembly release'}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['stock_forecast','extra_hardware']},indent=2))


if __name__ == '__main__':
    main()
