#!/usr/bin/env python3
"""Create auditable TME prototype purchase lists from the v4.1 netlist.

Stocked MCU/LEDs are listed separately. Prices are dated catalogue snapshots,
not checkout quotes. Quantities include supplier minimums, no silent substitutes.
"""
import argparse
import csv
from decimal import Decimal
import json
from math import ceil
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def csvfile(path, headers, rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist',type=Path,default=ROOT/'build/hardware/v4_1/netlist.xml')
    parser.add_argument('--output',type=Path,default=ROOT/'hw/ledkiv4.1/exports/prototype/procurement')
    parser.add_argument('--tiles',type=int,default=5)
    parser.add_argument('--heads',type=int,default=1)
    parser.add_argument('--swio-headers',type=int)
    parser.add_argument('--spares',type=float,default=.2,help='Additional purchase allowance; default20%%, minimum-one spare per fitted purchased part')
    args=parser.parse_args()
    if args.tiles<1 or not 0<=args.heads<=args.tiles:parser.error('require tiles>=1 and 0<=heads<=tiles')
    headers=args.tiles if args.swio_headers is None else args.swio_headers
    if not 0<=headers<=args.tiles:parser.error('invalid header count')
    if not 0<=args.spares<=1:parser.error('require spares between0and1')
    profile=json.loads((ROOT/'config/v4_1-parts.json').read_text())
    parts={p['tme_symbol']:p for p in profile['selected_parts']}
    groups={};stocked={};complete=[]
    for c in ET.parse(args.netlist).findall('./components/comp'):
        ref=c.attrib['ref'];fields={i.attrib['name']:i.text or '' for i in c.findall('./fields/field')}
        population=fields.get('Population','TILE')
        if ref in ['J1','J3','JP1','JP2','H1','H2'] or population=='PCB_ONLY':continue
        count={'TILE':args.tiles,'HEAD_ONLY':args.heads,'OPTIONAL_SWIO':headers}[population]
        mpn=fields.get('MPN') or c.findtext('value')
        qty=count
        complete.append(dict(Reference=ref,MPN=mpn,Value=c.findtext('value'),Footprint=c.findtext('footprint'),Population=population,Quantity=qty,TME=fields.get('TME',''),Source='USER_STOCK' if fields.get('Sourcing','').startswith('USER_STOCK') else 'TME'))
        if fields.get('Sourcing','').startswith('USER_STOCK'):
            stocked.setdefault(mpn,[]).append(ref);continue
        symbol=fields.get('TME');assert symbol in parts,(ref,symbol)
        assert parts[symbol]['mpn']==mpn,(ref,'MPN mismatch')
        group=groups.setdefault(symbol,{'refs':[],'quantity':0})
        group['refs'].append(ref);group['quantity']+=qty
    assert set(groups)==set(parts),'Orphan supplier selection'
    args.output.mkdir(parents=True,exist_ok=True)
    rows=[];totals={};warnings=[]
    for symbol,g in groups.items():
        p=parts[symbol];required=g['quantity']
        minimum=int(p['minimum']);multiple=int(p['multiple'])
        target=required+max(1,ceil(required*args.spares)) if args.spares and required else required
        order=ceil(max(target,minimum)/multiple)*multiple if required else 0
        def price(q):
            tiers=[t for t in p['price_breaks'] if int(t['quantity'])<=q]
            return Decimal(max(tiers,key=lambda t:int(t['quantity']))['unit_net']) if tiers else Decimal(0)
        # A nearby price break may cost less overall; do not add stock merely
        # to report a lower unit price. Magazine quantities remain optional.
        if order:
            candidates={order,*(ceil(max(order,int(t['quantity']))/multiple)*multiple for t in p['price_breaks'])}
            order=min(candidates,key=lambda q:(price(q)*q,q))
        tier=next(iter(sorted((t for t in p['price_breaks'] if int(t['quantity'])<=order),key=lambda t:int(t['quantity']),reverse=True)),None)
        unit=Decimal(tier['unit_net']) if tier and order else Decimal(0)
        subtotal=unit*order;totals[p['currency']]=totals.get(p['currency'],Decimal(0))+subtotal
        stock=p.get('stock_snapshot')
        warning='checkout stock/price refresh required'
        if stock is None:warning='stock not confirmed in available source';warnings.append(symbol+': '+warning)
        elif stock<order:warning='snapshot insufficient; check lead time';warnings.append(symbol+': '+warning)
        rows.append(dict(TME=symbol,Quantity=order,Required=required,Spares=order-required,MPN=p['mpn'],References=' '.join(sorted(g['refs'])),Package=p['package'],Unit_net=str(unit),Currency=p['currency'],Subtotal_net=str(subtotal),Snapshot_stock=stock,Snapshot_age=p['source_age'],Supplier_url=p['supplier_url'],Note=warning))
    name=f'{args.tiles}-boards'+('-minimum' if not args.spares else '')
    csvfile(args.output/f'TME-BUY-{name}.csv',list(rows[0]),rows)
    csvfile(args.output/f'TME-QUICKBUY-{name}.csv',['TME','Quantity'],[{k:r[k]for k in ['TME','Quantity']}for r in rows if r['Quantity']])
    (args.output/f'TME-QUICKBUY-{name}.txt').write_text(''.join(f"{r['TME']}\t{r['Quantity']}\n"for r in rows if r['Quantity']))
    csvfile(args.output/f'ASSEMBLY-BOM-{name}.csv',list(complete[0]),complete)
    inventory={r['MPN']:r for r in csv.DictReader((ROOT/'config/parts-stock.csv').open())}
    stockrows=[]
    for mpn,refs in stocked.items():
        item=inventory[mpn];available=max(0,int(item['purchased'])-int(item['used_max'])-int(item['reserved']))
        required=len(refs)*args.tiles
        stockrows.append(dict(MPN=mpn,Required=required,Conservative_available=available,Shortage=max(0,required-available),References=' '.join(refs),Note='Estimate; current v3 assembly reservations deducted. Count shelf stock before assembly.'))
        if required>available:warnings.append(f'{mpn}: short {required-available}; outside TME purchase scope, stock needed for twenty-tile comparison')
    csvfile(args.output/f'USER-STOCK-{name}.csv',list(stockrows[0]),stockrows)
    result={'tiles':args.tiles,'heads':args.heads,'swio_headers':headers,'spare_fraction':args.spares,'net_totals_by_currency':{k:str(v)for k,v in totals.items()},
        'status':'PCB prototype BOM; catalogue snapshots require checkout refresh',
        'excluded':'PCB, shipping, taxes, tools, optional reusable probe cable, screws/wire/printed parts; stocked MCU and LEDs',
        'warnings':warnings,'no_foreign_exchange_assumed':True}
    (args.output/f'cost-{name}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
