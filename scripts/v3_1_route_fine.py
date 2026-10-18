#!/usr/bin/env python3
"""Bounded fine-grid terminal routing in a complete isolated CAD context."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--work',type=Path,required=True)
p.add_argument('--nets',nargs='+',required=True)
p.add_argument('--width',type=float,default=.15)
p.add_argument('--ordering',choices=['mps','original'],default='mps')
p.add_argument('--reverse-mps',action='store_true')
p.add_argument('--defer-checks',action='store_true',help='Route only; a batch runner must grade serially before comparing candidates')
p.add_argument('--timeout-seconds',type=int,default=300)
p.add_argument('--rip-nets',nargs='*',default=[],help='Exact additional development nets eligible for scoped rip-up')
p.add_argument('--max-ripup',type=int,default=0)
p.add_argument('--net-width',action='append',default=[],metavar='NET=MM',help='Explicit width for an exact net, including scoped rip victims')
p.add_argument('--in1-proposals',action='store_true',help='Development proposal only: penalized In1 access for declared nets; requires exact copper/filled-ground review before acceptance')
p.add_argument('--retain-rejected-proposal',action='store_true',help='Keep the diagnostic engine proposal for a later explicit power/ground repair; native grading remains mandatory')
args=p.parse_args()
assert not args.work.exists()
assert args.source.with_suffix('.kicad_pro').exists() and args.source.with_suffix('.kicad_sch').exists()
assert args.width>=.15 and all(n not in ['GND','VCC'] and not any(c in n for c in '*?![') for n in args.nets)
assert args.timeout_seconds>0 and not (args.reverse_mps and args.ordering!='mps')
assert args.max_ripup>=0
assert not args.retain_rejected_proposal or args.in1_proposals
assert all(n not in ['GND','VCC'] and not any(c in n for c in '*?![') for n in args.rip_nets)
widths={name:float(width) for name,width in (entry.rsplit('=',1) for entry in args.net_width)}
assert all(name in args.nets+args.rip_nets and width>=.15 for name,width in widths.items())
source=args.source.resolve();work=args.work.resolve();context=work/'context'
shutil.copytree(source.parent,context)
board=context/source.name;routed=board.with_stem(board.stem+'-routed')
# Prior experiments may retain a similarly named output beside the input.
# A fresh run must never mistake that inherited file for a new result.
stale={routed.name,routed.with_suffix('.kicad_pro').name,routed.with_suffix('.kicad_prl').name}
for name in stale:
    if (context/name).exists():(context/name).unlink()
authored={path.relative_to(source.parent):path.read_bytes() for path in source.parent.rglob('*') if path.is_file() and not (path.parent==source.parent and path.name in stale)}
before=hashlib.sha256(source.read_bytes()).hexdigest()
layer_costs=['1','5' if args.in1_proposals else '-1','3','1']
command=['/home/pies/letki/.tools/kicad-routing-env/bin/python',
         '/home/pies/letki/.tools/kicad-routing-tools/py_router/route.py',str(board),str(routed),
         '--nets',*args.nets,'--layers','F.Cu','In1.Cu','In2.Cu','B.Cu',
         '--layer-costs',*layer_costs,'--grid-step','0.05',
         '--track-width',str(args.width),'--clearance','0.2','--via-size','0.6','--via-drill','0.3',
         '--max-ripup',str(args.max_ripup),'--keep-input-copper','--no-fix-drc-settings',
         '--fab-tier','standard','--escalation','off','--strict-sizes',
         '--same-net-pad-clearance','0.15','--write-fill','--json-out',str(work/'route.json')]
command+=['--ordering',args.ordering]
if args.reverse_mps:command+=['--mps-reverse-rounds']
if args.rip_nets:command+=['--rip-existing-nets',*args.rip_nets]
if widths:command+=['--power-nets',*widths,'--power-nets-widths',*[str(v) for v in widths.values()]]
environment=dict(os.environ)
policy={'KICAD_RIP_PREEXISTING':'0','KICAD_FINALIZE_RIP':'0',
        'KICAD_NET_RESCUE':'0','KICAD_TERMINAL_ESCALATION':'0',
        'KICAD_RESCUE_CAP_MOVE':'0','PYTHONHASHSEED':'0'}
policy['KICAD_IMPROVEMENT_GATE']='0' if args.retain_rejected_proposal else '1'
environment.update(policy)
start=time.monotonic()
cpu_before=resource.getrusage(resource.RUSAGE_CHILDREN)
timed_out=False
with (work/'route.log').open('w') as log:
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=environment,start_new_session=True)
    try:process.wait(timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out=True
        os.killpg(process.pid,signal.SIGKILL)
        process.wait()
cpu_after=resource.getrusage(resource.RUSAGE_CHILDREN)
profile={'nets':args.nets,'width_mm':args.width,'clearance_mm':.2,'via_mm':[.6,.3],
         'grid_mm':.05,'ordering':args.ordering,'reverse_mps':args.reverse_mps,
         'layers':['F.Cu','In1.Cu','In2.Cu','B.Cu'],'layer_costs':[float(v) for v in layer_costs],
         'In1_proposal_requires_explicit_review':args.in1_proposals,
         'retain_rejected_diagnostic_proposal':args.retain_rejected_proposal,
         'exact_rip_nets':args.rip_nets,'max_ripup':args.max_ripup,'explicit_net_widths_mm':widths,
         'policy':policy,'timeout_seconds':args.timeout_seconds}
(work/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
metrics={'router_exit':process.returncode,'duration_seconds':round(time.monotonic()-start,3),
         'child_cpu_seconds':round(cpu_after.ru_utime+cpu_after.ru_stime-cpu_before.ru_utime-cpu_before.ru_stime,3),
         'child_max_rss_kib':cpu_after.ru_maxrss,'timeout':timed_out,
         'profile_sha256':hashlib.sha256((work/'profile.json').read_bytes()).hexdigest(),
         'command':command,'source_sha256':before,'environment_policy':policy,
         'candidate_written':False,
         'tool_revision':'9399bfb29e072bfe60b10d9cdae20c274fc2a17a'}
(work/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
assert hashlib.sha256(source.read_bytes()).hexdigest()==before,'Source was mutated'
if not routed.exists():
    print(json.dumps(metrics,indent=2))
    raise SystemExit('No output; failure retained in metrics.json and route.log')
shutil.copytree(context,work/'raw-output')
candidate=routed.read_bytes()
for name,data in authored.items():(context/name).write_bytes(data)
board.write_bytes(candidate)
metrics['candidate_written']=True
metrics['candidate_sha256']=hashlib.sha256(candidate).hexdigest()
if args.defer_checks:
    metrics['native_checks']='PENDING_SERIAL_GRADING; not a checked candidate'
    (work/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))
    raise SystemExit(0 if process.returncode==0 else 1)
for name,command in [
    ('drc',['kicad-cli','pcb','drc','--refill-zones','--severity-all','--schematic-parity','--exit-code-violations','--format','json','-o',str(work/'drc.json'),str(board)]),
    ('erc',['kicad-cli','sch','erc','--severity-all','--exit-code-violations','--format','json','-o',str(work/'erc.json'),str(board.with_suffix('.kicad_sch'))])]:
    with (work/(name+'.log')).open('w') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    metrics[name+'_exit']=r.returncode
    if (work/(name+'.json')).exists():
        d=json.loads((work/(name+'.json')).read_text())
        metrics[name+'_counts']={key:len(d.get(key,[])) for key in ['violations','unconnected_items','schematic_parity','ignored_checks']}
        if d.get('violations'):metrics[name+'_types']=dict(Counter(i['type'] for i in d['violations']))
(work/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
print(json.dumps(metrics,indent=2))
