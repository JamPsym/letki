#!/usr/bin/env python3
"""Compare three exact-net routing strategies, serially and as three processes.

Every arm gets an identical isolated source context. Native checks are serial.
No source promotion; this measures this fixture, not general CPU scaling.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(directory):
    files = {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in directory.rglob('*') if p.is_file()}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--nets', nargs='+', required=True)
    parser.add_argument('--width', type=float, required=True)
    parser.add_argument('--parallel-only', action='store_true', help='New design step; no additional speed benchmark claim')
    parser.add_argument('--profile-set', choices=['orderings','row-necks'], default='orderings')
    args = parser.parse_args()
    source, work = args.source.resolve(), args.work.resolve()
    assert not work.exists()
    work.mkdir(parents=True)
    before = fingerprint(source.parent)
    strategies = ([('mps', [], args.width), ('original', ['--ordering','original'], args.width),
                   ('mps-reverse', ['--reverse-mps'], args.width)] if args.profile_set=='orderings' else
                  [('neck-0.3',['--ordering','original'],.3),
                   ('neck-0.2',['--ordering','original'],.2),
                   ('neck-0.15',['--ordering','original'],.15)])
    phases = {}

    def run(phase, strategy):
        name, extra, width = strategy
        arm = work/phase/name
        command = [sys.executable,str(ROOT/'scripts/v3_1_route_fine.py'),
                   '--source',str(source),'--work',str(arm),'--width',str(width),
                   '--nets',*args.nets,'--defer-checks',*extra]
        arm.parent.mkdir(parents=True, exist_ok=True)
        with (arm.parent/(name+'-wrapper.log')).open('w') as log:
            result = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        print(phase, name, 'wrapper_exit='+str(result.returncode), flush=True)
        return {'name':name,'wrapper_exit':result.returncode,'path':str(arm.relative_to(ROOT)),
                'metrics':json.loads((arm/'metrics.json').read_text()) if (arm/'metrics.json').exists() else None}

    if not args.parallel_only:
        start = time.monotonic()
        serial = [run('serial',strategy) for strategy in strategies]
        phases['serial'] = {'wall_seconds':round(time.monotonic()-start,3),'arms':serial}
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=3) as pool:
        parallel = list(pool.map(lambda strategy: run('parallel',strategy),strategies))
    phases['parallel'] = {'wall_seconds':round(time.monotonic()-start,3),'arms':parallel}
    # These helper threads only launch independent external router processes.
    # Avoid sharing pcbnew/KiCad objects or running native CLI checks together.
    for phase in phases.values():
        for arm in phase['arms']:
            path = ROOT/arm['path']
            pcb = path/'context'/source.name
            if not arm['metrics'] or not arm['metrics'].get('candidate_written'):
                arm['grade'] = 'NO_ROUTER_OUTPUT'
                continue
            for name, command in [
                ('drc',['kicad-cli','pcb','drc','--refill-zones','--severity-all','--schematic-parity','--exit-code-violations','--format','json','-o',str(path/'drc.json'),str(pcb)]),
                ('erc',['kicad-cli','sch','erc','--severity-all','--exit-code-violations','--format','json','-o',str(path/'erc.json'),str(pcb.with_suffix('.kicad_sch'))])]:
                with (path/(name+'.log')).open('w') as log:
                    result = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
                grade = {'exit':result.returncode}
                report = path/(name+'.json')
                if report.exists():
                    data = json.loads(report.read_text())
                    grade.update({key:len(data.get(key,[])) for key in ['violations','unconnected_items','schematic_parity','ignored_checks']})
                    grade['types'] = dict(Counter(v['type'] for v in data.get('violations',[])))
                arm[name] = grade
            print('graded',arm['path'],json.dumps(arm.get('drc')),flush=True)
        phase['router_child_cpu_seconds_sum'] = round(sum(a['metrics']['child_cpu_seconds'] for a in phase['arms'] if a['metrics']),3)
        phase['average_router_cpu_cores'] = round(phase['router_child_cpu_seconds_sum']/phase['wall_seconds'],3)
    assert fingerprint(source.parent) == before, 'Source context changed'
    results = {'fixture_source':str(source.relative_to(ROOT)),
               'input_board_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
               'input_context_sha256':before,'exact_nets':args.nets,'nominal_width_mm':args.width,
               'profiles':[{'name':name,'options':extra,'width_mm':width} for name,extra,width in strategies],
               'phases':phases,'serial_to_parallel_wall_ratio':round(phases['serial']['wall_seconds']/phases['parallel']['wall_seconds'],3) if 'serial' in phases else None,
               'scope':'Three routing-process portfolio on this fixed fixture; strategy quality graded separately. No source promotion or whole-board speedup claim.',
               'limitations':('One paired trial, not a statistical benchmark. Serial phase runs first and may warm filesystem caches. ' if 'serial' in phases else 'Parallel portfolio only; no measured speedup for this step. ')+
                             'CPU means cover measured router descendants; no whole-host utilization claim.'}
    (work/'comparison.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({key:results[key] for key in ['serial_to_parallel_wall_ratio','scope','limitations']},indent=2))


if __name__ == '__main__':
    main()
