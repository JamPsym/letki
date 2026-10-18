#!/usr/bin/env python3
"""Generate candidate LCSC quantities from an exported v4 schematic netlist."""
import argparse
import csv
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=Path, default=Path('build/hardware/v4/netlist.xml'))
    parser.add_argument('--output', type=Path, default=Path('build/hardware/v4/candidate-bom.csv'))
    parser.add_argument('--tiles', type=int, default=5)
    parser.add_argument('--heads', type=int, default=1)
    parser.add_argument('--swio-headers', type=int, default=None, help='Optional hand-soldered PicoBlade headers; defaults to one per tile')
    parser.add_argument('--probe-cables', type=int, default=1, help='Reusable probe pigtails, separate from PCB assembly')
    args = parser.parse_args()
    if args.tiles < 1 or not 0 <= args.heads <= args.tiles:
        parser.error('require tiles >= 1 and 0 <= heads <= tiles')
    if args.swio_headers is None: args.swio_headers=args.tiles
    if not 0 <= args.swio_headers <= args.tiles or args.probe_cables < 0:
        parser.error('invalid optional connector or cable quantity')
    groups = defaultdict(list)
    definitions = {}
    pcb_only = {'J1', 'J3', 'JP1', 'JP2', 'H1', 'H2'}
    for comp in ET.parse(args.netlist).findall('./components/comp'):
        ref = comp.attrib['ref']
        fields = {item.attrib['name']: item.text or '' for item in comp.findall('./fields/field')}
        code = fields.get('LCSC', '')
        if fields.get('Population') == 'PCB_ONLY':
            if not ref.startswith('TP') or not (comp.findtext('footprint') or '').startswith('Letki:TestPoint_'):
                raise ValueError(f'{ref}: unrecognized PCB-only feature')
            pcb_only.add(ref)
        if ref in pcb_only:
            if code:
                raise ValueError(f'{ref}: PCB-only feature unexpectedly has an LCSC code')
            continue
        if not re.fullmatch(r'C[0-9]+', code):
            raise ValueError(f'{ref}: missing or invalid LCSC code')
        population = fields.get('Population', 'TILE')
        if population not in ('TILE', 'HEAD_ONLY', 'OPTIONAL_SWIO'):
            raise ValueError(f'{ref}: unknown population {population!r}')
        mpn = fields.get('MPN') or comp.findtext('value') or ''
        definition = (fields.get('Manufacturer', ''), mpn, comp.findtext('footprint') or '')
        if code in definitions and definitions[code] != definition:
            raise ValueError(f'{code}: inconsistent manufacturer, MPN or footprint')
        definitions[code] = definition
        groups[(code, population)].append(ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['status', 'LCSC', 'manufacturer', 'MPN', 'footprint', 'population',
                         'references', 'quantity_per_population', 'assembly_quantity', 'supplier_url'])
        for (code, population), refs in sorted(groups.items()):
            count = {'TILE':args.tiles,'HEAD_ONLY':args.heads,'OPTIONAL_SWIO':args.swio_headers}[population]
            writer.writerow(['CANDIDATE_NOT_RELEASED', code, *definitions[code], population,
                             ' '.join(refs), len(refs), len(refs) * count,
                             f'https://www.lcsc.com/product-detail/{code}.html'])
        if args.probe_cables:
            writer.writerow(['CANDIDATE_MATING_SAMPLE_REQUIRED','C5221408','hanxia',
                             'HX 1.25-3P DT 200mm 28AWG','off-board cable',
                             'PROBE_ACCESSORY','reusable probe pigtail',1,args.probe_cables,
                             'https://www.lcsc.com/product-detail/C5221408.html'])
    print(f'{args.output}: {len(groups)} rows for {args.tiles} tiles, {args.heads} USB heads')
    print('Exact assembly quantities only; supplier MOQ, spares and stock require procurement review.')


if __name__ == '__main__':
    main()
