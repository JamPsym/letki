#!/usr/bin/env python3
"""Compare prototype component purchases, including LCSC minimum quantities.

Quotes are public product-page snapshots under ignored build/hardware/v4/supplier.
Use --refresh explicitly for network access. No cart or order is created.
"""
import argparse
import csv
import datetime as dt
import json
import math
import re
import urllib.request
from collections import defaultdict
from pathlib import Path


def load_inventory(path):
    """Use the conservative shelf count; never infer a part substitution."""
    inventory = {}
    with path.open(newline='') as file:
        for row in csv.DictReader(file):
            code = row['LCSC']
            if code in inventory or not re.fullmatch(r'C[0-9]+', code):
                raise ValueError(f'{code}: duplicate or invalid inventory code')
            bought, used_min, used_max, reserved = (int(row[key]) for key in
                                                   ('purchased', 'used_min', 'used_max', 'reserved'))
            if not 0 <= used_min <= used_max <= bought or not 0 <= reserved <= bought-used_max:
                raise ValueError(f'{code}: invalid purchased/used/reserved quantities')
            inventory[code] = (row['MPN'], bought-used_max-reserved)
    return inventory


def load_magazines(path):
    """Use only per-part capacities confirmed for the user's actual tape."""
    preferences = json.loads(path.read_text())
    capacities = preferences['capacities']
    for code, entry in capacities.items():
        if (not re.fullmatch(r'C[0-9]+', code) or not entry['MPN']
                or type(entry['pieces']) is not int or entry['pieces'] <= 0):
            raise ValueError(f'{code}: invalid magazine capacity')
    bulk = preferences.get('bulk_stock', {})
    if bulk and (bulk['part_type'] != 'resistors' or type(bulk['target_quantity']) is not int
                 or bulk['target_quantity'] <= 0 or bulk['draft_recommendation_total_usd'] < 0):
        raise ValueError('Invalid bulk-stock recommendation settings')
    return capacities, bulk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bom', type=Path, default=Path('build/hardware/v4/candidate-bom.csv'))
    parser.add_argument('--quotes', type=Path, default=Path('build/hardware/v4/supplier'))
    parser.add_argument('--tiles', type=int, nargs='+', default=[5, 20])
    parser.add_argument('--heads', type=int, default=1)
    parser.add_argument('--spares', type=float, default=0)
    parser.add_argument('--inventory', type=Path, help='Deduct exact-MPN shelf stock using conservative remaining counts')
    parser.add_argument('--magazines', type=Path, help='Apply soft storage/bulk-stock preferences and show the minimum-cash alternative')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--swio-headers',type=int,default=None,help='Optional headers per batch; default one per tile')
    parser.add_argument('--probe-cables',type=int,default=1)
    args = parser.parse_args()
    if any(n < 1 or n < args.heads for n in args.tiles) or args.heads < 0 or args.spares < 0:
        parser.error('invalid tile/head/spare quantities')
    if args.probe_cables<0 or (args.swio_headers is not None and any(not 0<=args.swio_headers<=n for n in args.tiles)):
        parser.error('invalid optional header or cable quantity')
    groups = defaultdict(list)
    for row in csv.DictReader(args.bom.open()):
        groups[row['LCSC']].append(row)
    inventory = load_inventory(args.inventory) if args.inventory else {}
    magazines, bulk = load_magazines(args.magazines) if args.magazines else ({}, {})
    for code, rows in groups.items():
        if code in inventory and inventory[code][0] != rows[0]['MPN']:
            raise ValueError(f'{code}: inventory MPN differs from the schematic')
        if code in magazines and magazines[code]['MPN'] != rows[0]['MPN']:
            raise ValueError(f'{code}: magazine MPN differs from the schematic')
    args.quotes.mkdir(parents=True, exist_ok=True)
    quotes = {}
    for code, rows in sorted(groups.items()):
        path = args.quotes / f'{code}.json'
        if args.refresh:
            url = rows[0]['supplier_url']
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            page = urllib.request.urlopen(request, timeout=25).read().decode()
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
            raw = json.loads(match.group(1))['props']['pageProps']['webData']
            data = {k: raw.get(k) for k in ('productCode', 'productModel', 'brandNameEn',
                    'encapStandard', 'minBuyNumber', 'split', 'stockNumber', 'productPriceList')}
            data['checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
            path.write_text(json.dumps(data, indent=2)+'\n')
        data = json.loads(path.read_text())
        if data['productCode'] != code or data['productModel'] != rows[0]['MPN']:
            raise ValueError(f'{code}: supplier MPN differs from the schematic')
        quotes[code] = data
    for tiles in args.tiles:
        suffix = (('-stock' if args.inventory else '') + ('-magazines' if args.magazines else '')
                  + (f'-spares-{args.spares:g}' if args.spares else ''))
        path = args.bom.parent / f'lcsc-prototype-{tiles}-boards{suffix}.csv'
        total = 0
        unavailable = []
        price_options = []
        with path.open('w', newline='') as output:
            writer = csv.writer(output)
            writer.writerow(['status', 'LCSC', 'MPN', 'required', 'with_spares', 'buy_quantity',
                             'unit_USD', 'line_USD', 'stock_snapshot', 'url',
                             'shelf_available_min', 'shelf_used', 'purchase_shortfall',
                             'magazine_capacity', 'magazine_count', 'magazine_status',
                             'minimum_cash_quantity', 'minimum_cash_USD', 'extra_spend_USD', 'quantity_reason'])
            for code, rows in sorted(groups.items()):
                data = quotes[code]
                counts={'TILE':tiles,'HEAD_ONLY':args.heads,
                        'OPTIONAL_SWIO':tiles if args.swio_headers is None else args.swio_headers,
                        'PROBE_ACCESSORY':args.probe_cables}
                fitted = sum(int(r['quantity_per_population']) * counts[r['population']] for r in rows)
                if not fitted:
                    continue
                required = math.ceil(fitted*(1+args.spares))
                available = inventory.get(code, ('', 0))[1]
                shelf_used = min(required, available)
                shortfall = required-shelf_used
                multiple = int(data['split'])
                capacity = magazines.get(code, {}).get('pieces', 0)
                # Only supplier MOQ/multiples constrain an order; storage is optional.
                def rounded(n): return math.ceil(max(n, data['minBuyNumber'])/multiple)*multiple
                quantities = ({rounded(shortfall)} | {rounded(t['ladder']) for t in data['productPriceList']
                                                      if t['ladder'] >= shortfall}) if shortfall else set()
                if shortfall and capacity:
                    quantities.add(rounded(math.ceil(shortfall/capacity)*capacity))
                resistor = all(ref.startswith('R') for r in rows for ref in r['references'].split())
                bulk_quantity = rounded(max(shortfall, bulk['target_quantity'])) if shortfall and bulk and resistor else 0
                if bulk_quantity:
                    quantities.add(bulk_quantity)
                options = []
                for quantity in quantities:
                    tier = max((t for t in data['productPriceList'] if t['ladder'] <= quantity),
                               key=lambda t: t['ladder'])
                    price = float(tier['usdPrice'])
                    options.append((quantity*price, quantity, price))
                available_options = [option for option in options if option[1] <= data['stockNumber']]
                minimum = min(available_options or options) if options else (0, 0, 0)
                cost, quantity, price = minimum
                reason = 'MINIMUM_CASH' if shortfall else 'FROM_SHELF_STOCK'
                if bulk_quantity:
                    proposed = next(option for option in options if option[1] == bulk_quantity)
                    if (proposed[1] > minimum[1] and proposed[0] <= bulk['draft_recommendation_total_usd']
                            and data['stockNumber'] >= proposed[1]):
                        cost, quantity, price = proposed
                        reason = 'LOW_COST_REUSABLE_RESISTOR_STOCK'
                for option_cost, option_quantity, option_price in sorted(options, key=lambda option: option[1]):
                    price_options.append([code, rows[0]['MPN'], option_quantity, f'{option_price:.4f}',
                        f'{option_cost:.4f}', f'{option_cost-minimum[0]:.4f}',
                        option_quantity <= data['stockNumber'], option_quantity == quantity,
                        option_quantity == minimum[1], capacity or '',
                        option_quantity % capacity == 0 if capacity else ''])
                stock = data['stockNumber']
                if stock < quantity:
                    unavailable.append(code)
                total += cost
                status=('FROM_SHELF_STOCK' if not shortfall else 'OUT_OF_STOCK' if stock<quantity else
                        'MATING_SAMPLE_REQUIRED' if any(r['population']=='PROBE_ACCESSORY' for r in rows) else
                        'PROTOTYPE_NOT_PRODUCTION_RELEASE')
                packed_accessory = any(r['population'] in ('OPTIONAL_SWIO', 'PROBE_ACCESSORY') for r in rows)
                magazine_status = ('NO_PURCHASE' if not shortfall else
                                   ('WHOLE_MAGAZINES' if quantity % capacity == 0 else 'PARTIAL_MAGAZINE') if capacity else
                                   'NOT_APPLICABLE' if packed_accessory else
                                   'CAPACITY_UNCONFIRMED' if args.magazines else 'NOT_REQUESTED')
                writer.writerow([status, code, rows[0]['MPN'],
                                 fitted, required, quantity, f'{price:.4f}', f'{cost:.4f}', stock,
                                 rows[0]['supplier_url'], available, shelf_used, shortfall,
                                 capacity or '', f'{quantity/capacity:g}' if capacity else '', magazine_status,
                                 minimum[1], f'{minimum[0]:.4f}', f'{cost-minimum[0]:.4f}', reason])
        if args.magazines:
            with (args.bom.parent/f'lcsc-price-options-{tiles}-boards{suffix}.csv').open('w', newline='') as output:
                writer=csv.writer(output)
                writer.writerow(['LCSC', 'MPN', 'quantity', 'unit_USD', 'line_USD', 'extra_vs_minimum_USD',
                                 'stock_available', 'recommended', 'minimum_cash',
                                 'magazine_capacity', 'whole_magazines'])
                writer.writerows(price_options)
        # Importable stock-available quantities. Cable is clearly separated
        # until the cross-vendor mating sample has passed.
        with path.open() as purchase_file: rows=list(csv.DictReader(purchase_file))
        for label,selected in [('lcsc-available', [r for r in rows if r['status']=='PROTOTYPE_NOT_PRODUCTION_RELEASE']),
                               ('lcsc-probe-accessories',[r for r in rows if r['status']=='MATING_SAMPLE_REQUIRED'])]:
            with (args.bom.parent/f'{label}-{tiles}-boards{suffix}.csv').open('w',newline='') as output:
                writer=csv.writer(output);writer.writerow(['LCSC Part #','Quantity'])
                for row in selected:writer.writerow([row['LCSC'],row['buy_quantity']])
        subtotal_label = 'new purchases subtotal' if args.inventory else 'reference parts subtotal'
        print(f'{tiles} boards / {args.heads} head(s): {subtotal_label} ${total:.2f}; {path}')
        print('Unavailable at snapshot:', ', '.join(unavailable) or 'none')
    print('Excludes PCB, stencil, assembly, shipping and tax. Recheck price/stock before buying.')


if __name__ == '__main__':
    main()
