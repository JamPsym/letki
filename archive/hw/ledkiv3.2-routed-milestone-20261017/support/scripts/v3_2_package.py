"""Check and export v3.2 CAD prototype files. No hardware, firmware or orders."""
import argparse,datetime,hashlib,json,os,shutil,subprocess,sys,time,zipfile,re,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',type=Path,default=ROOT/'hw/ledkiv3.2');ap.add_argument('--baseline',type=Path,default=ROOT/'archive/hw/ledkiv3.2-unrouted-20261017/hw/ledkiv3.2/ledkiv3_2.kicad_pcb');ap.add_argument('--geometry-python',default=sys.executable);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--config',type=Path,default=ROOT/'config');ap.add_argument('--evidence',type=Path,nargs='*',default=[]);a=ap.parse_args()
out=a.output.resolve();assert not out.exists(),'Use a fresh output directory';out.mkdir(parents=True);project=a.project.resolve();board=project/'ledkiv3_2.kicad_pcb';start=time.monotonic();commands=[]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=sorted(p for p in project.rglob('*') if p.is_file() and 'exports' not in p.parts and (p.suffix in ['.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru','.kicad_mod','.kicad_sym','.step','.json','.txt'] or p.name in ['README.md','fp-lib-table','sym-lib-table']))
before={str(p.relative_to(project)):sha(p) for p in files}
support={}
for folder,selected in [('scripts',[*Path(__file__).parent.glob('*v3_2*.py'),Path(__file__).with_name('kicad_sexpr.py')]),('config',list(a.config.glob('v3_2*.json'))),('docs',list((Path(__file__).parents[1]/'docs').glob('v3_2*.txt'))),('baseline',[p for p in a.baseline.parent.rglob('*') if p.is_file() and p.suffix not in ['.kicad_prl','.lck']])]:
 for p in selected:support[folder+'/'+str(p.relative_to(a.baseline.parent) if folder=='baseline' else p.name)]=p
support_before={name:sha(p) for name,p in support.items()}
tool_versions={'kicad_cli':subprocess.check_output(['kicad-cli','version'],text=True).strip(),'geometry_python':subprocess.check_output([a.geometry_python,'-c','import sys,pcbnew,shapely; print(sys.version); print(pcbnew.GetBuildVersion()); print("Shapely",shapely.__version__)'],text=True).strip()}
def run(*cmd):
 t=time.monotonic()
 with (out/'commands.log').open('a') as f:r=subprocess.run([str(x) for x in cmd],stdout=f,stderr=f,env=dict(os.environ,QT_QPA_PLATFORM='offscreen'))
 commands.append({'argv':[str(x) for x in cmd],'whole_command_seconds':time.monotonic()-t,'returncode':r.returncode});(out/'command-metrics.json').write_text(json.dumps(commands,indent=2)+'\n');print('Checked/exported',str(cmd[1:4]),flush=True);r.check_returncode()
run('kicad-cli','sch','erc','--severity-all','--exit-code-violations','--format','json','-o',out/'erc.json',board.with_suffix('.kicad_sch'))
run('kicad-cli','pcb','drc','--refill-zones','--schematic-parity','--severity-all','--exit-code-violations','--format','json','-o',out/'drc.json',board)
d=json.loads((out/'drc.json').read_text());e=json.loads((out/'erc.json').read_text());assert e['sheets'] and all(not s['violations'] for s in e['sheets']) and not e['ignored_checks'];assert all(not d[k] for k in ['violations','unconnected_items','schematic_parity','ignored_checks'])
run('kicad-cli','sch','export','netlist','--format','kicadsexpr','-o',out/'schematic.net',board.with_suffix('.kicad_sch'))
run(a.geometry_python,Path(__file__).with_name('check_v3_2_integrated.py'),'--board',board,'--baseline',a.baseline,'--netlist',out/'schematic.net','--labels',a.config/'v3_2-labels.json','--in1-manifest',project/'in1-exceptions.json','--power-manifest',a.config/'v3_2-power.json','--output',out/'independent.json')
run(a.geometry_python,Path(__file__).with_name('check_v3_2_copper.py'),'--board',board,'--all-nets','--output',out/'physical-copper.json')
run(a.geometry_python,Path(__file__).with_name('v3_2_bom.py'),'--schematic',board.with_suffix('.kicad_sch'),'--output',out/'assembly')
for name,layers in [('gerbers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts'),('stencil','F.Paste,B.Paste,Edge.Cuts')]:
 (out/name).mkdir();run('kicad-cli','pcb','export','gerbers','--check-zones','--subtract-soldermask','--layers',layers,'-o',str(out/name)+'/',board)
job=json.loads((out/'gerbers/ledkiv3_2-job.gbrjob').read_text());spec=job['GeneralSpecs'];cu={x['Name']:x['Thickness'] for x in job['MaterialStackup'] if x['Type']=='Copper'}
assert spec['LayerNumber']==4 and spec['BoardThickness']==1.6 and spec['Finish']=='HAL SnPb';assert cu=={'F.Cu':.035,'In1.Cu':.0175,'In2.Cu':.0175,'B.Cu':.035}
run('kicad-cli','pcb','export','drill','--format','excellon','--excellon-units','mm','--excellon-separate-th','--generate-report','--report-path',out/'drill-report.txt','-o',str(out/'gerbers')+'/',board)
def drills(path):
 tools={};counts=collections.Counter();active=None
 for line in path.read_text().splitlines():
  m=re.fullmatch(r'T(\d+)C([\d.]+)',line)
  if m:tools[m[1]]=round(float(m[2]),4)
  m=re.fullmatch(r'T(\d+)',line)
  if m:active=m[1]
  if re.fullmatch(r'X[-+\d.]+Y[-+\d.]+',line):assert active in tools;counts[tools[active]]+=1
 return dict(counts)
via_count=json.loads((out/'independent.json').read_text())['ordinary_tented_vias'];drill_counts={'PTH':drills(out/'gerbers/ledkiv3_2-PTH.drl'),'NPTH':drills(out/'gerbers/ledkiv3_2-NPTH.drl')}
assert drill_counts=={'PTH':{.3:via_count,.6:3,.8:28},'NPTH':{2.2:4}},drill_counts
for side,layers in [('front','F.Fab,F.Silkscreen,Edge.Cuts'),('back','B.Fab,B.Silkscreen,Edge.Cuts')]:
 cmd=['kicad-cli','pcb','export','svg','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','--black-and-white','--sketch-pads-on-fab-layers','--layers',layers,'-o',out/f'assembly-{side}.svg']
 if side=='back':cmd.append('--mirror')
 run(*cmd,board)
run('kicad-cli','pcb','export','svg','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','--black-and-white','--layers','B.Silkscreen,B.Mask,Edge.Cuts','--mirror','-o',out/'rear-labels.svg',board)
run('kicad-cli','sch','export','pdf','-o',out/'schematic.pdf',board.with_suffix('.kicad_sch'))
run('kicad-cli','pcb','export','pos','--format','csv','--units','mm','--side','both','-o',out/'positions-native-review.csv',board)
run('kicad-cli','pcb','export','step','--force','--subst-models','-o',out/'populated.step',board)
log=(out/'commands.log').read_text();assert 'Could not add 3D model' not in log and 'File not found:' not in log,'Missing 3D dependency'
assert before=={str(p.relative_to(project)):sha(p) for p in files},'Source changed during export'
assert support_before=={name:sha(p) for name,p in support.items()},'Supporting source/config/baseline changed during export'
if a.evidence:
 (out/'evidence').mkdir()
 for p in a.evidence:assert not (out/'evidence'/p.name).exists();shutil.copy2(p,out/'evidence'/p.name)
for name,folder in [('gerbers',out/'gerbers'),('sources',project)]:
 with zipfile.ZipFile(out/f'ledkiv3_2-{name}.zip','w',zipfile.ZIP_DEFLATED) as z:
  selected=sorted(folder.iterdir()) if name=='gerbers' else files
  for p in selected:z.write(p,str(p.relative_to(folder)) if name=='gerbers' else 'hw/ledkiv3.2/'+str(p.relative_to(folder)))
  if name=='sources':
   for p in Path(__file__).parent.glob('*v3_2*.py'):z.write(p,'scripts/'+p.name)
   z.write(Path(__file__).with_name('kicad_sexpr.py'),'scripts/kicad_sexpr.py')
   for p in a.config.glob('v3_2*.json'):z.write(p,'config/'+p.name)
   for p in a.baseline.parent.rglob('*'):
    if p.is_file() and p.suffix not in ['.kicad_prl','.lck']:z.write(p,'archive/hw/ledkiv3.2-unrouted-20261017/hw/ledkiv3.2/'+str(p.relative_to(a.baseline.parent)))
   docs=Path(__file__).parents[1]/'docs'
   for p in docs.glob('v3_2*.txt'):z.write(p,'docs/'+p.name)
for p in out.glob('*.zip'):
 with zipfile.ZipFile(p) as z:assert z.testzip() is None
manifest={'status':'CAD_CHECKED_PROTOTYPE','created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'board_sha256':sha(board),'source_sha256':before,'supporting_source_sha256':support_before,'tool_versions':tool_versions,'source_unchanged_during_export':True,'native_counts':dict(ERC=0,DRC=0,opens=0,parity=0,ignored=0),'stackup':spec,'copper_thickness_mm':cu,'drill_counts':drill_counts,'commands':commands,'whole_export_seconds':time.monotonic()-start,'limits':['Firmware/custom loader not implemented or flashed','Physical rail/current/thermal/PWM/network/optical/mechanical qualification pending','6 generic new passives have no selected exact MPN','Native positions are review data, not qualified assembler import','Fabricator process and preview need confirmation before ordering'],'orders':False,'hardware_access':False}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(out/'artifact-sha256.json').write_text(json.dumps({str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},indent=2)+'\n');print('CAD prototype exported to',out)
