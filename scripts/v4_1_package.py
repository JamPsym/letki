#!/usr/bin/env python3
"""Validate and export the TME-sourced v4.1 prototype purchase handoff.

No ordering, account interaction or flashing. Rejects all unexplained check
exclusions, CAD violations, BOM inconsistencies and missing 3D models.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'hw/ledkiv4.1'
STEM='ledkiv4_1'
PCB=PROJECT/(STEM+'.kicad_pcb')
SCH=PCB.with_suffix('.kicad_sch')
OUTPUT=PROJECT/'exports/prototype'
ART=ROOT/'build/hardware/v4_1'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run(*args):
    with (OUTPUT/'commands.log').open('a')as f:
        subprocess.run([str(a)for a in args],cwd=ROOT,stdout=f,stderr=f,check=True)
    print('Completed:',str(args[0]),str(args[1]),flush=True)


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'commands.log').write_text('')
    source_files=[p for p in PROJECT.rglob('*')if p.is_file() and 'exports'not in p.parts and p.suffix in ['.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru','.kicad_mod','.kicad_sym','.step','.FCStd']]
    source_files += [PROJECT/'fp-lib-table',PROJECT/'sym-lib-table',ROOT/'config/v4_1-parts.json',ROOT/'config/v4_1-mechanics.json',ROOT/'config/parts-stock.csv']
    source_files += [PROJECT/'README.md',ROOT/'config/parts-stock-source.json',
        *(ROOT/'scripts'/name for name in ['v4_1_package.py','v4_1_bom.py','v4_1_via_map.py','v4_1_routing_report.py',
            'check_v4_circuit.py','check_v4_geometry.py','v4_mechanics.py','v4_diffuser.py','kicad_sexpr.py',
            'setup_kicad_svg.py','kicad_svg_report.py']),ROOT/'config/kicad-svg-extras.json',
        *(ROOT/'docs'/name for name in ['v4_1-design.md','v4_1-order-and-bringup.txt','v4_1-qualification.csv','v4_1-routing-trials.csv'])]
    before={str(p.relative_to(ROOT)):digest(p)for p in source_files}
    run('kicad-cli','sch','erc','--severity-all','--exit-code-violations','--format','json','-o',OUTPUT/'erc.json',SCH)
    run('kicad-cli','pcb','drc','--refill-zones','--schematic-parity','--severity-all','--exit-code-violations','--format','json','-o',OUTPUT/'drc.json',PCB)
    drc=json.loads((OUTPUT/'drc.json').read_text());erc=json.loads((OUTPUT/'erc.json').read_text())
    assert not drc['ignored_checks'],'Disabled PCB checks'
    notes={'single_global_label':'Allowed on single-sheet schematic; explicit independent pin-net checks run.',
        'four_way_junction':'Intentional junction topology independently checked.',
        'simulation_model_issue':'No SPICE simulation is claimed; digital vendor models not assigned.'}
    assert all(v['key']in notes for v in erc['ignored_checks']),'Unexplained disabled ERC check'
    run('kicad-cli','sch','export','netlist','--format','kicadxml','-o',ART/'netlist.xml',SCH)
    run(sys.executable,ROOT/'scripts/check_v4_circuit.py','--revision','v4.1')
    run(sys.executable,ROOT/'scripts/check_v4_geometry.py',PCB,'--revision','v4.1')
    run(sys.executable,ROOT/'scripts/v4_1_via_map.py','--output',OUTPUT)
    run(sys.executable,ROOT/'scripts/v4_1_routing_report.py','--output',OUTPUT/'routing-review','--final-drc',OUTPUT/'drc.json')
    for tiles in (5,20):
        for spares in ('0','0.2'):
            run(sys.executable,ROOT/'scripts/v4_1_bom.py','--tiles',tiles,'--spares',spares,'--output',OUTPUT/'procurement')
    gerbers=OUTPUT/'gerbers';gerbers.mkdir(exist_ok=True)
    # Remove only this exporter's generated outputs to prevent stale fabrication layers.
    for p in gerbers.iterdir():
        if p.is_file():p.unlink()
    run('kicad-cli','pcb','export','gerbers','--check-zones','--subtract-soldermask',
        '--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts','-o',str(gerbers)+'/',PCB)
    job=json.loads((gerbers/(STEM+'-job.gbrjob')).read_text())
    specs=job['GeneralSpecs'];copper={l['Name']:l['Thickness']for l in job['MaterialStackup']if l['Type']=='Copper'}
    assert specs['LayerNumber']==4 and specs['BoardThickness']==1.6 and specs['Finish']=='HAL SnPb'
    assert copper=={'F.Cu':.035,'In1.Cu':.0175,'In2.Cu':.0175,'B.Cu':.035}
    run('kicad-cli','pcb','export','drill','--format','excellon','--excellon-units','mm','--excellon-separate-th',
        '--excellon-oval-format','route','--generate-report','--report-path',OUTPUT/'drill-report.txt','-o',str(gerbers)+'/',PCB)
    for purpose,layers in [('stencil','F.Paste,B.Paste,Edge.Cuts'),('front','F.Fab,F.Silkscreen,Edge.Cuts'),('back','B.Fab,B.Silkscreen,Edge.Cuts')]:
        if purpose=='stencil':
            target=OUTPUT/'stencil';target.mkdir(exist_ok=True)
            run('kicad-cli','pcb','export','gerbers','--layers',layers,'-o',str(target)+'/',PCB)
        else:
            command=['kicad-cli','pcb','export','svg','--mode-single','--fit-page-to-board','--exclude-drawing-sheet',
                '--black-and-white','--sketch-pads-on-fab-layers','--layers',layers,'-o',OUTPUT/f'assembly-{purpose}.svg']
            if purpose=='back':command.append('--mirror')
            run(*command,PCB)
    run(sys.executable,ROOT/'scripts/kicad_svg_report.py','--output',OUTPUT/'routing-review','--with-trials','--reuse-verified')
    for name in ('svg-viewer-test.json','svg-viewer-tested.png'):
        if (ART/name).exists():shutil.copy2(ART/name,OUTPUT/'routing-review'/name)
    if (ART/'routing-audit.json').exists():shutil.copy2(ART/'routing-audit.json',OUTPUT/'routing-review/routing-audit.json')
    run('kicad-cli','sch','export','pdf','-o',OUTPUT/'schematic.pdf',SCH)
    run('kicad-cli','pcb','export','pos','--format','csv','--units','mm','--side','both','-o',OUTPUT/'positions.csv',PCB)
    mechanical=OUTPUT/'mechanical';mechanical.mkdir(exist_ok=True)
    run('kicad-cli','pcb','export','step','--force','--subst-models','-o',mechanical/(STEM+'-populated.step'),PCB)
    log=(OUTPUT/'commands.log').read_text()
    assert 'Could not add 3D model'not in log and 'File not found:'not in log,'Missing package model'
    for tiles in (1,4):
        folder=mechanical/f'{tiles}-tiles'
        run(sys.executable,ROOT/'scripts/v4_mechanics.py','--tiles',tiles,'--config',ROOT/'config/v4_1-mechanics.json',
            '--name','letkiv4_1','--output',folder,'--pcb-step',mechanical/(STEM+'-populated.step'))
    for path in [ROOT/'docs/v4_1-design.md',ROOT/'docs/v4_1-qualification.csv',ROOT/'docs/interface-demo.md']:
        shutil.copy2(path,OUTPUT/path.name)
    shutil.copy2(ROOT/'config/v4_1-mechanics.json',OUTPUT/'mechanical-dimensions.json')
    shutil.copy2(ART/'circuit-check.json',OUTPUT/'circuit-check.json')
    shutil.copy2(ART/(STEM+'-geometry.json'),OUTPUT/'geometry-check.json')
    order=ROOT/'docs/v4_1-order-and-bringup.txt';shutil.copy2(order,OUTPUT/'ORDER-AND-BRINGUP.txt')
    after={str(p.relative_to(ROOT)):digest(p)for p in source_files}
    assert before==after,'Source changed during validation/export; rerun on frozen sources'
    manifest={'status':'CAD_CHECKED_FOR_PROTOTYPE_PURCHASE; physical qualification pending',
        'revision':'v4.1','source_sha256':after,'erc_default_notes':notes,
        'pcb_checks_disabled':drc['ignored_checks'],'erc_checks_disabled':erc['ignored_checks'],
        'drc_findings':len(drc['violations']),'open_connections':len(drc['unconnected_items']),
        'schematic_parity_findings':len(drc['schematic_parity']),
        'stackup':job['GeneralSpecs'],'orders_placed':False,
        'remaining':'First-article electrical/optical/mechanical qualification; TME checkout refresh; fabricator preview/process confirmation'}
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(OUTPUT/(STEM+'-gerbers.zip'),'w',zipfile.ZIP_DEFLATED)as z:
        for p in sorted(gerbers.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(OUTPUT/(STEM+'-sources.zip'),'w',zipfile.ZIP_DEFLATED)as z:
        for p in source_files:z.write(p,str(p.relative_to(ROOT)))
    with zipfile.ZipFile(OUTPUT/(STEM+'-handoff.zip'),'w',zipfile.ZIP_DEFLATED)as z:
        for p in sorted(OUTPUT.rglob('*')):
            if p.is_file() and p.name!=(STEM+'-handoff.zip'):z.write(p,str(p.relative_to(OUTPUT)))
    print('Checked v4.1 Gerbers and handoff:',OUTPUT,flush=True)


if __name__=='__main__':main()
