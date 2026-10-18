#!/usr/bin/env python3
"""Run pinned KiCadRoutingTools on isolated Letki v4 working copies."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / 'config/kicad-routing.json').read_text())
TOOL = ROOT / '.tools/kicad-routing-tools'
PYTHON = ROOT / '.tools/kicad-routing-env/bin/python'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doctor():
    if not PYTHON.exists() or not TOOL.exists():
        raise SystemExit('Run python3 scripts/setup_kicad_routing.py first.')
    revision = subprocess.check_output(['git', '-C', str(TOOL), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != PIN['commit']:
        raise SystemExit(f'Unexpected KiCadRoutingTools revision: {revision}')
    dirty = subprocess.check_output(['git', '-C', str(TOOL), 'status', '--porcelain'], text=True)
    if dirty.strip():
        raise SystemExit('KiCadRoutingTools sources differ from the reviewed pin.')
    engine = TOOL / 'rust_router/grid_router.so'
    if not engine.exists() or digest(engine) != PIN['linux_x86_64_engine']['sha256']:
        raise SystemExit('Missing or unexpected Rust engine; run the setup script.')
    code = ('import sys,json,importlib.metadata as m; '
            f'sys.path.insert(0,{str(engine.parent)!r}); '
            'import grid_router,pcbnew,numpy,scipy,shapely,PIL; '
            'print(json.dumps({"engine":grid_router.__version__, '
            '"packages":{n:m.version(n) for n in ["numpy","scipy","shapely","Pillow"]}}))')
    subprocess.run([str(PYTHON), '-c', code], check=True)
    subprocess.run(['kicad-cli', 'version'], check=True)
    print(f'KiCadRoutingTools {PIN["release"]}, commit {revision}', flush=True)


def execute(command, folder, name):
    """Retain every instrument's exit code and full output; never hide findings."""
    started=datetime.now(timezone.utc).isoformat();clock_start=time.monotonic()
    with (folder / f'{name}.log').open('w') as log:
        result = subprocess.run([str(arg) for arg in command], cwd=folder,
                                stdout=log, stderr=subprocess.STDOUT)
    path=folder/'command-metrics.json'
    metrics=json.loads(path.read_text()) if path.exists() else {}
    metrics[name]={'started_utc':started,'duration_seconds':round(time.monotonic()-clock_start,3),
                   'returncode':result.returncode,'command':[str(arg)for arg in command]}
    path.write_text(json.dumps(metrics,indent=2)+'\n')
    print(f'{name}: exit {result.returncode}; {folder / (name + ".log")}', flush=True)
    return result.returncode


def tool(script, *args):
    return [PYTHON, TOOL / script, *args]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['doctor', 'check', 'render', 'route'])
    parser.add_argument('--board', type=Path, default=ROOT / 'hw/ledkiv4/ledkiv4.kicad_pcb')
    parser.add_argument('--work', type=Path, help='New output directory under build/hardware/; must not exist')
    parser.add_argument('--before', type=Path, help='Optional original board for placement arrows')
    parser.add_argument('--nets', nargs='+', help='Exact signal net names for a scoped routing experiment')
    parser.add_argument('--revision',choices=['v4','v4.1'],default='v4',help='Letki geometry profile for independent checks')
    parser.add_argument('--mechanics-config',type=Path,help='Geometry profile for an isolated placement candidate')
    args = parser.parse_args()
    doctor()
    if args.action == 'doctor':
        return
    source = args.board.resolve(strict=True)
    for suffix in ['.kicad_pro', '.kicad_sch', '.kicad_dru']:
        if not source.with_suffix(suffix).is_file():
            raise SystemExit(f'Missing v4 CAD context: {source.with_suffix(suffix)}')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work = (args.work or ROOT / 'build/hardware/kicad-routing' / f'{args.action}-{stamp}').resolve()
    if not work.is_relative_to((ROOT / 'build/hardware').resolve()):
        raise SystemExit('Working copies must be under build/hardware/.')
    if work.exists():
        raise SystemExit(f'Refusing to overwrite an existing working directory: {work}')
    # Copy the complete CAD context; libraries and rules must accompany the PCB.
    files = [p for p in source.parent.iterdir() if p.is_file() and
             (p.suffix in ['.kicad_pcb', '.kicad_pro', '.kicad_sch', '.kicad_dru', '.kicad_sym'] or
              p.name in ['fp-lib-table', 'sym-lib-table'])]
    for directory in source.parent.iterdir():
        if directory.is_dir() and directory.suffix in ['.pretty', '.3dshapes']:
            files.extend(p for p in directory.rglob('*') if p.is_file())
    original = {str(p): digest(p) for p in files}
    work.mkdir(parents=True)
    for path in files:
        target = work / path.relative_to(source.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    board = work / source.name
    spec = PIN['v4']
    results = {}
    try:
        if args.action == 'route':
            if not args.nets:
                raise SystemExit('Routing requires --nets with exact signal names; there is no whole-board default.')
            if any(n in spec['excluded_route_nets'] or any(c in n for c in '*?![') for n in args.nets):
                raise SystemExit('Power/ground and wildcard routing require a separately reviewed plan.')
            # Validate names using native KiCad, outside this host interpreter.
            code = ('import pcbnew,json,sys; b=pcbnew.LoadBoard(sys.argv[1]); '
                    'print(json.dumps([n.GetNetname() for n in b.GetNetsByNetcode().values()]))')
            names = json.loads(subprocess.check_output([str(PYTHON), '-c', code, str(board)], text=True))
            unknown = set(args.nets) - set(names)
            if unknown:
                raise SystemExit(f'Unknown exact net names: {sorted(unknown)}')
            routed = work / f'{source.stem}-routed.kicad_pcb'
            command = tool('py_router/route.py', board, routed, '--nets', *args.nets,
                           '--layers', *spec['layers'], '--layer-costs', *spec['layer_costs'],
                           '--track-width', spec['signal_track_mm'], '--clearance', spec['route_clearance_mm'],
                           '--via-size', spec['via_diameter_mm'], '--via-drill', spec['via_drill_mm'],
                           '--max-ripup', 0, '--keep-input-copper', '--no-fix-drc-settings',
                           '--fab-tier', 'standard', '--escalation', 'off', '--strict-sizes',
                           '--same-net-pad-clearance', 0.15, '--write-fill',
                           '--json-out', work / 'route.json')
            results['route'] = execute(command, work, 'route')
            if routed.exists():
                # Preserve the authored rules for independent grading. v0.23.0
                # can lower floors MID-RUN despite --no-fix-drc-settings. Keep
                # that upstream output as evidence, then restore original context.
                router_project = routed.with_suffix('.kicad_pro')
                if router_project.exists():
                    shutil.copy2(router_project, work / 'router-project-before-restore.json')
                    if digest(router_project) != digest(work / (source.stem + '.kicad_pro')):
                        print('Router changed candidate project metadata; restoring authored project for all checks.', flush=True)
                for suffix in ['.kicad_pro', '.kicad_dru', '.kicad_sch']:
                    original_context = work / (source.stem + suffix)
                    candidate_context = routed.with_suffix(suffix)
                    if original_context.exists():
                        shutil.copy2(original_context, candidate_context)
                board = routed
            else:
                raise SystemExit('No routed candidate was written; inspect route.log.')
        if args.action in ['check', 'route']:
            results['krt-check'] = execute(tool('check_complete.py', board, '--authored-from', source,
                '--clearance', spec['minimum_clearance_mm'], '--min-track-width', spec['minimum_track_mm'],
                '--min-via-diameter', spec['via_diameter_mm'], '--min-via-drill', spec['via_drill_mm'],
                '--timeout', 180, '--json', work / 'krt-check.json'), work, 'krt-check')
            results['kicad-drc'] = execute(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--severity-all',
                '--schematic-parity', '--exit-code-violations', '--format', 'json',
                '-o', work / 'kicad-drc.json', board], work, 'kicad-drc')
            # Geometry independently checks native per-layer pads and wide power feeds.
            geometry=[sys.executable, ROOT / 'scripts/check_v4_geometry.py', board,'--revision',args.revision]
            if args.mechanics_config: geometry.extend(['--config',args.mechanics_config.resolve(strict=True)])
            results['letki-geometry'] = execute(geometry,
                                               work, 'letki-geometry')
        if args.action in ['render', 'route']:
            command = tool('py_tools/render_placement.py', board, '--per-side',
                           '--size', 1800, '-o', work / 'views', '--review-sheet', work / 'review.png',
                           '--json-out', work / 'render.json', '--quiet')
            if args.before:
                command.extend(['--before', args.before.resolve(strict=True), '--arrows'])
            results['render'] = execute(command, work, 'render')
    finally:
        changed = [name for name, sha in original.items()
                   if not Path(name).is_file() or digest(Path(name)) != sha]
        (work / 'workflow.json').write_text(json.dumps({
            'tool_pin': PIN, 'source': str(source), 'source_sha256': original[str(source)],
            'source_files_sha256': original, 'source_files_changed': changed,
            'results': results, 'candidate': str(board),
            'status': 'WORKING COPY ONLY; inspect all findings before promotion'
        }, indent=2) + '\n')
        if changed:
            raise SystemExit(f'Source changed during the run; preserve and review: {changed}')
    print(f'Working copy and reports: {work}')
    if any(results.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
