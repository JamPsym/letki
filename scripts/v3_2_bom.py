"""Export v3.2 CAD population BOM; no stock, reservation or sourcing claims."""
import argparse,csv,json,collections
from pathlib import Path
from kicad_sexpr import read,children,child,prop
ap=argparse.ArgumentParser();ap.add_argument('--schematic',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--require-exact',action='store_true',help='Reject purchasing references without a selected MPN');ap.add_argument('--inventory-report',type=Path,help='Read-only shared inventory reporter JSON; never modifies ledgers');a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
parts={}
for s in children(read(a.schematic),'symbol'):
 r=prop(s,'Reference')[2]
 if r.startswith('#'):continue
 fields={p[1]:p[2] for p in children(s,'property')}
 population='NOT_PURCHASED' if child(s,'in_bom')[1]=='no' else 'OPTIONAL_SWIO_HEADER' if r=='J2' else 'ONE_PAIR_PER_I2C_BUS' if r in ['R11','R12'] else 'ALL_TILES'
 spec=''
 if not fields.get('MPN') and r in ['R69','R70','R71','R72','R73']:spec='Generic 0805 resistor; select exact MPN before procurement'
 if not fields.get('MPN') and r=='C6':spec='100 nF 0805 ceramic; select exact MPN/dielectric/rating before procurement'
 rec={'reference':r,'value':fields['Value'],'MPN':fields.get('MPN',''),'footprint':fields['Footprint'],'population':population,'note':'; '.join(filter(None,[fields.get('Assembly',''),spec]))}
 if r in parts:assert parts[r]==rec,('Inconsistent multi-unit part',r)
 parts[r]=rec
assert len(parts)==159
def write(name,rows):
 with (a.output/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write('all-CAD-references.csv',[parts[r] for r in sorted(parts)])
groups={}
for r,p in parts.items():
 if p['population']=='NOT_PURCHASED':continue
 key=(p['value'],p['MPN'],p['footprint'],p['population'])
 groups.setdefault(key,[]).append(r)
rows=[]
for (value,mpn,fp,pop),refs in sorted(groups.items()):
 rows.append({'references':' '.join(sorted(refs)),'value':value,'MPN':mpn,'footprint':fp,'population':pop,'ordinary_tile_fit':len(refs) if pop=='ALL_TILES' else 0,'one_pullup_tile_fit':len(refs) if pop in ['ALL_TILES','ONE_PAIR_PER_I2C_BUS'] else 0,'optional_per_tile':len(refs) if pop=='OPTIONAL_SWIO_HEADER' else 0,'note':'; '.join(sorted({parts[r]['note'] for r in refs if parts[r]['note']}))})
write('population-BOM.csv',rows)
summary={'CAD_footprints':159,'BOM_references':sum(p['population']!='NOT_PURCHASED' for p in parts.values()),'ordinary_tile_fitted_SMT':sum(r['ordinary_tile_fit'] for r in rows),'one_pullup_tile_fitted_SMT':sum(r['one_pullup_tile_fit'] for r in rows),'optional_SWIO_header':1,'exact_MPN_unselected':[r for r,p in parts.items() if p['population']!='NOT_PURCHASED' and not p['MPN']],'sourcing':'CAD intent only; refresh availability, package identity and price before buying. No stock credit/reservation/purchase.'}
assert summary['ordinary_tile_fitted_SMT']==145 and summary['one_pullup_tile_fitted_SMT']==147
if a.require_exact:assert not summary['exact_MPN_unselected'],('Select exact assembly parts',summary['exact_MPN_unselected'])
(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

# Five upright tiles sharing one I2C bus: one pull-up tile, four ordinary.
# Merge equivalent value spellings by exact MPN and footprint for purchasing.
batch={}
for row in rows:
 key=(row['MPN'],row['footprint']);g=batch.setdefault(key,{'MPN':row['MPN'],'footprint':row['footprint'],'references':[],'fitted_quantity_5':0,'optional_quantity_5':0})
 g['references']+=row['references'].split()
 g['fitted_quantity_5']+=row['one_pullup_tile_fit']+4*row['ordinary_tile_fit']
 g['optional_quantity_5']+=5*row['optional_per_tile']
inventory=json.loads(a.inventory_report.read_text()) if a.inventory_report else None
if inventory:
 (a.output/'inventory-snapshot.json').write_text(json.dumps(inventory,indent=2)+'\n')
for (mpn,fp),g in batch.items():
 g['references']=' '.join(sorted(g['references']));lots=[p for p in inventory['lots'] if p['MPN']==mpn] if inventory else []
 # A package mismatch must never receive stock credit merely from similar MPNs.
 for lot in lots:
  package=lot['package'].split()[0].replace('-','').lower()
  if lot['available_for_other_projects']:
   assert package in fp.replace('-','').lower(),('Review inventory package identity',mpn,lot['package'],fp)
 g['available_after_existing_holds']=sum(p['available_for_other_projects'] for p in lots) if inventory else ''
 g['shortfall_5']=max(0,g['fitted_quantity_5']-g['available_after_existing_holds']) if inventory else ''
 g['inventory_basis']='; '.join(f"{p['kind']}: free {p['available_for_other_projects']}, pending {p.get('pending',0)}" for p in lots) if lots else 'No exact usable shelf lot credited'
write('five-board-BOM.csv',[batch[k] for k in sorted(batch)])
assert sum(g['fitted_quantity_5'] for g in batch.values())==727
assert sum(g['optional_quantity_5'] for g in batch.values())==5
(a.output/'five-board-summary.json').write_text(json.dumps({'boards':5,'pullup_tiles':1,'ordinary_tiles':4,'fitted_SMT':727,'optional_headers':5,'inventory_credited':bool(inventory),'inventory_reservations_or_consumption_changed':False,'scope':'Quantity floor for hand assembly, no loss allowance, MOQ or shipping. Shared availability is a dated estimate; confirm counts before assembly. Exactly one R11/R12 pair per connected I2C bus.'},indent=2)+'\n')
