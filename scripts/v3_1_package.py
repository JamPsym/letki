#!/usr/bin/env python3
"""Validate frozen v3.1 sources and export a complete prototype handoff.

No ordering, device access or inventory writes. Output is replaced only after
all gates pass; earlier generated packages are retained with a timestamp.
"""
import argparse, csv, datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'hw/ledkiv3.1';STEM='ledkiv3_1';PCB=PROJECT/(STEM+'.kicad_pcb')
DOCS=['v3_1-five-tile-plan.txt','v3_1-assembly-test.txt','v3_1-qualification.csv','v3_1-cost.txt','v3_1-power-review.txt','v3_1-routing-trials.csv','v3_1-techniques.txt','v3_1-completion-20261015.txt','interface-demo.md','arch-setup.md']
SCRIPTS=['v3_1_package.py','check_v3_1_integrated.py','check_v3_1_manufacturing.py','check_v3_1_power.py','v3_1_bom.py','v3_1_qualify.py','v3_1_mechanics.py','v3_1_diffuser.py','uart_demo.py','uart_link.py','uart_text.py','setup_toolchain.py','compile_commands.py']
CONFIGS=['v3_1-bom.json','v3_1-system.json','v3_1-mechanics.json','v3_1-labels.json','v3_1-power-layout.json','v3_1-firmware-assessment.json','v3_1-procurement-20261014.json','v3_1-delivery.json']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def source_files():
    files=[p for p in PROJECT.rglob('*') if p.is_file() and 'exports' not in p.parts and (p.suffix in ['.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru','.kicad_mod','.kicad_sym','.step','.json'] or p.name in ['README.md','fp-lib-table','sym-lib-table'])]
    for folder in ['firmware','archive/firmware','tests','scripts']:
        files += [p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ['.c','.h','.cpp','.S','.ld','.txt','.md','.py','.json'] and '__pycache__' not in p.parts]
    files += [ROOT/'Makefile',ROOT/'README.md',*(ROOT/'docs'/p for p in DOCS),*(ROOT/'scripts'/p for p in SCRIPTS),*(ROOT/'config'/p for p in CONFIGS)]
    # Independent core checker compares this preserved electrical reference.
    files += [p for p in (ROOT/'archive/hw/ledkiv3.1-studies-20261015/pulse-study').rglob('*') if p.is_file() and (p.suffix in ['.kicad_sch','.kicad_sym','.kicad_mod','.kicad_pro'] or p.name in ['fp-lib-table','sym-lib-table'])]
    return sorted(set(files))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--geometry-python',default=os.environ.get('PCB_GEOMETRY_PYTHON',sys.executable),help='Python with pcbnew and Shapely');ap.add_argument('--tool-prefix',help='WCH GCC tool prefix, as CROSS_COMPILE');ap.add_argument('--inventory-snapshot',type=Path,default=ROOT/'build/hardware/v3_1-integration/inventory-current.json');args=ap.parse_args()
    tool=args.tool_prefix or os.environ.get('CROSS_COMPILE')
    if not tool and (ROOT/'config/local.mk').exists():
        match=re.search(r'^CROSS_COMPILE\s*:?=\s*(\S+)',(ROOT/'config/local.mk').read_text(),re.M);tool=match[1] if match else None
    tool=tool or str(ROOT/'.tools/mrs-1.90/RISC-V_Embedded_GCC/bin/riscv-none-embed-')
    subprocess.run([args.geometry_python,'-c','import pcbnew, shapely'],check=True)
    art=ROOT/'build/hardware/v3_1-package';art.mkdir(parents=True,exist_ok=True);out=Path(tempfile.mkdtemp(prefix='run-',dir=art));commands=[];env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
    def run(*command):
        start=time.monotonic()
        with (out/'commands.log').open('a') as f:subprocess.run([str(x) for x in command],cwd=ROOT,env=env,stdout=f,stderr=f,check=True)
        commands.append({'argv':[str(x) for x in command],'duration_seconds':time.monotonic()-start});(out/'command-metrics.json').write_text(json.dumps(commands,indent=2)+'\n');print('Completed:',' '.join(str(x) for x in command[:4]),flush=True)
    files=source_files();before={str(p.relative_to(ROOT)):sha(p) for p in files};assert args.inventory_snapshot.exists();inventory_before=sha(args.inventory_snapshot)
    run('make','all-variants','-j4');run('make','test')
    run('kicad-cli','sch','erc','--severity-all','--exit-code-violations','--format','json','-o',out/'erc.json',PCB.with_suffix('.kicad_sch'))
    run('kicad-cli','pcb','drc','--refill-zones','--schematic-parity','--severity-all','--exit-code-violations','--format','json','-o',out/'drc.json',PCB)
    d=json.loads((out/'drc.json').read_text());e=json.loads((out/'erc.json').read_text());assert not any(sheet['violations'] for sheet in e['sheets']) and not e['ignored_checks'];assert not any(d[k] for k in ['violations','unconnected_items','schematic_parity','ignored_checks'])
    run(args.geometry_python,ROOT/'scripts/check_v3_1_integrated.py','--board',PCB,'--output',out/'circuit-geometry.json')
    run(args.geometry_python,ROOT/'scripts/check_v3_1_power.py','--board',PCB,'--output',out/'power-connectivity.json')
    run(args.geometry_python,ROOT/'scripts/check_v3_1_manufacturing.py','--board',PCB,'--output',out/'manufacturing.json')
    run(sys.executable,ROOT/'scripts/v3_1_bom.py','--board',PCB,'--output',out/'procurement','--inventory-snapshot',args.inventory_snapshot)
    shutil.copy2(args.inventory_snapshot,out/'procurement/inventory-snapshot.json')
    gerbers=out/'gerbers';gerbers.mkdir()
    run('kicad-cli','pcb','export','gerbers','--check-zones','--subtract-soldermask','--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts','-o',str(gerbers)+'/',PCB)
    job=json.loads((gerbers/(STEM+'-job.gbrjob')).read_text());specs=job['GeneralSpecs'];copper={l['Name']:l['Thickness'] for l in job['MaterialStackup'] if l['Type']=='Copper'}
    assert specs['LayerNumber']==4 and specs['BoardThickness']==1.6 and specs['Finish']=='HAL SnPb'
    assert copper=={'F.Cu':.035,'In1.Cu':.0175,'In2.Cu':.0175,'B.Cu':.035}
    run('kicad-cli','pcb','export','drill','--format','excellon','--excellon-units','mm','--excellon-separate-th','--excellon-oval-format','route','--generate-report','--report-path',out/'drill-report.txt','-o',str(gerbers)+'/',PCB)
    stencil=out/'stencil';stencil.mkdir();run('kicad-cli','pcb','export','gerbers','--layers','F.Paste,B.Paste,Edge.Cuts','-o',str(stencil)+'/',PCB)
    for side,layers in [('front','F.Fab,F.Silkscreen,Edge.Cuts'),('back','B.Fab,B.Silkscreen,Edge.Cuts')]:
        command=['kicad-cli','pcb','export','svg','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','--black-and-white','--sketch-pads-on-fab-layers','--layers',layers,'-o',out/f'assembly-{side}.svg']
        if side=='back':command.append('--mirror')
        run(*command,PCB)
    run('kicad-cli','sch','export','pdf','-o',out/'schematic.pdf',PCB.with_suffix('.kicad_sch'))
    run('kicad-cli','pcb','export','pos','--format','csv','--units','mm','--side','both','-o',out/'positions-native-review.csv',PCB)
    mechanical=out/'mechanical';mechanical.mkdir();run('kicad-cli','pcb','export','step','--force','--subst-models','-o',mechanical/'populated.step',PCB)
    log=(out/'commands.log').read_text();assert 'Could not add 3D model' not in log and 'File not found:' not in log,'Missing component model'
    for tiles in (1,4):run(sys.executable,ROOT/'scripts/v3_1_mechanics.py','--tiles',tiles,'--config',ROOT/'config/v3_1-mechanics.json','--name','letkiv3_1','--output',mechanical/f'{tiles}-tiles','--pcb-step',mechanical/'populated.step')
    shutil.copy2(ROOT/'config/v3_1-mechanics.json',mechanical/'dimensions.json')
    fw=out/'firmware';fw.mkdir();memory=[]
    for variant,profile in [('v3_1-pulse','LETKI_V3_1_PULSE'),('v3_1-interface','LETKI_V3_1_INTERFACE_LED_OFF'),('v3_1-interface-controller','LETKI_V3_1_INTERFACE_LED_OFF'),('v3_1-interface-target','LETKI_V3_1_INTERFACE_LED_OFF')]:
        folder=ROOT/'build'/variant;dest=fw/variant;dest.mkdir()
        for suffix in ['elf','hex','bin','map']:shutil.copy2(folder/('letki.'+suffix),dest/('letki.'+suffix))
        line=subprocess.check_output([tool+'size',str(folder/'letki.elf')],text=True).splitlines()[1].split();text,data,bss=map(int,line[:3]);assert text+data<=16384 and data+bss<=2048
        assert profile.encode() in (dest/'letki.bin').read_bytes(),'Wrong firmware profile'
        memory.append({'variant':variant,'flash_sections_bytes':text+data,'RAM_including_stack_bytes':data+bss,'stack_reservation_bytes':256 if variant=='v3_1-pulse' else 384,'profile':profile,'bin_sha256':sha(dest/'letki.bin'),'flashed':False})
    (fw/'memory.json').write_text(json.dumps(memory,indent=2)+'\n');shutil.copy2(ROOT/'config/v3_1-firmware-assessment.json',fw/'static-assessment.json')
    for name in DOCS:shutil.copy2(ROOT/'docs'/name,out/name)
    for variant in ['v3_1-pulse','v3_1-interface']:shutil.copy2(ROOT/'firmware'/variant/'README.txt',fw/(variant+'-README.txt'))
    (out/'START-HERE.txt').write_text('LETKI v3.1 — CAD-CHECKED PROTOTYPE HANDOFF\n\nRead v3_1-assembly-test.txt before hardware work. The33R tile requires\nthe matching pulse firmware, regulated3.3V and the R49/PD7 provisioning\nprocedure. ESP/head design and physical qualification are deferred.\n\nGerbers:4layers,1.6mm,HALSnPb,35/17.5/17.5/35um. Ordinary tented\n0.6/0.3mm vias; no filling/capping, castellations or edge plating. PTH/NPTH\ndrills are separate. Verify fabricator preview/process/tolerances before\nordering; no paid order was placed. Native positions are review coordinates,\nnot a qualified assembler import. Population-specific BOM marks R11/R12 and\nfirst-provisioning R49; all146footprints are shown in populatedSTEP.\n\nOne/four-tile printable parts support a4+1carrier, not a printed-fit claim.\nSource/check/artifact hashes and memory limits are in manifest.json.\nAll15physical qualification rows remainPENDING. Inventory is a dated\nread-only forecast; no receipt, reservation or consumption was recorded.\n')
    with (out/'v3_1-qualification.csv').open(newline='') as f:qualification=list(csv.DictReader(f))
    assert len(qualification)==15 and all(r['result']=='PENDING' for r in qualification)
    after={str(p.relative_to(ROOT)):sha(p) for p in files};assert before==after,'Source mutation during export';assert inventory_before==sha(args.inventory_snapshot),'Inventory snapshot changed'
    protected_path=ROOT/'build/hardware/v3_1-integration/protected-inputs.json';protected=json.loads(protected_path.read_text()) if protected_path.exists() else {};changed=[name for name,value in protected.items() if sha(ROOT/name)!=value];assert not changed,changed
    manifest={'status':'CAD_CHECKED_PROTOTYPE_HANDOFF; physical qualification pending','revision':'v3.1','created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':after,'source_unchanged_during_export':True,'protected_inputs_unchanged':len(protected),'ERC_findings':0,'DRC_findings':0,'open_connections':0,'schematic_parity_findings':0,'ignored_checks':[],'stackup':specs,'copper_thickness_mm':copper,'firmware':memory,'inventory_snapshot_sha256':inventory_before,'mechanics':'Populated current-pose1and4tile CAD/solder-envelope checks; physical fit pending','qualification_rows_pending':15,'orders_placed':False,'hardware_accessed':False,'shared_inventory_mutated':False,'remaining':['Physical pulse/current/temperature/rail/interface/optical/mechanical qualification','Refresh exact supplier prices and confirm fabricator preview/process before any authorized order','ESP-12F and custom power/control head are a later user-deferred stage']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(out/(STEM+'-gerbers.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(gerbers.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(out/(STEM+'-sources.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,str(p.relative_to(ROOT)))
        z.write(args.inventory_snapshot,'inventory-snapshot.json')
    artifacts={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()};(out/'artifact-sha256.json').write_text(json.dumps(artifacts,indent=2)+'\n')
    with zipfile.ZipFile(out/(STEM+'-handoff.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file() and p.name!=STEM+'-handoff.zip':z.write(p,str(p.relative_to(out)))
    final=PROJECT/'exports/prototype';final.parent.mkdir(exist_ok=True)
    if final.exists():final.rename(final.with_name('prototype-previous-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))
    shutil.move(str(out),final);print('Checked prototype handoff:',final,flush=True)
if __name__=='__main__':main()
