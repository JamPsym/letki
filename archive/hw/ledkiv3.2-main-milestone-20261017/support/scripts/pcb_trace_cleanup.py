#!/usr/bin/env python3
"""Isolated, one-chain PCB trace simplification with native acceptance gates.

Run with the KiCadRoutingTools Python environment. Proposal generation never writes the
source project; apply requires the exact reviewed image manifest. `run` snapshots it, grades each proposal sequentially, and
renders accepted changes. Review the renders before transferring final CAD.
"""
import argparse
import collections
import dataclasses
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / '.tools/kicad-routing-tools/py_router'
sys.path.insert(0, str(TOOL))
import pcbnew
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont
from kicad_parser import parse_kicad_pcb
from pcb_modification import smooth_octolinear_chains
from kicad_sexpr import parse, child


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def blocks(text):
    """Locate native root children without rewriting other S-expressions."""
    depth = 0
    quoted = escaped = False
    start = None
    out = []
    for i, c in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                quoted = False
            continue
        if c == '"':
            quoted = True
        elif c == '(':
            if depth == 1:
                start = i
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 1 and start is not None:
                raw = text[start:i + 1]
                tag = re.match(r'\(([^\s()]+)', raw).group(1)
                out.append((start, i + 1, tag, raw))
                start = None
    if depth or quoted:
        raise ValueError('Unbalanced native PCB source')
    return out


def block_uuid(raw):
    node = parse(raw)
    value = child(node, 'uuid')
    return str(value[1]) if value else None


def authored(raw):
    node = parse(raw)
    if node[0] == 'zone':
        node = [x for x in node if not isinstance(x, list)
                or x[0] not in ('filled_polygon', 'fill_segments')]
    return node


def preserve(before, after, removed, added):
    """All unrelated authored objects, including via/padstack/field data."""
    def objects(text, skip):
        return [authored(raw) for _, _, tag, raw in blocks(text)
                if not (tag == 'segment' and block_uuid(raw) in skip)]
    # Native DRC may reorder tracks on save; compare full authored objects,
    # preserving duplicates rather than collapsing them into UUID dictionaries.
    canon = lambda seq: collections.Counter(json.dumps(x, ensure_ascii=False) for x in seq)
    assert canon(objects(before, removed)) == canon(objects(after, added)), 'Unrelated authored CAD changed'


def xy(point):
    return (point.x, point.y)


def copper(item, layer):
    poly = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(poly, layer, 0, 10, pcbnew.ERROR_OUTSIDE)
    def points(contour):
        return [(contour.CPoint(j).x / 1e6, contour.CPoint(j).y / 1e6)
                for j in range(contour.PointCount())]
    return unary_union([Polygon(points(poly.COutline(i)),
        [points(poly.CHole(i, h)) for h in range(poly.HoleCount(i))])
        for i in range(poly.OutlineCount())])


def inventory(board_path):
    board = pcbnew.LoadBoard(str(board_path))
    tracks = [t for t in board.GetTracks() if type(t) == pcbnew.PCB_TRACK
              and t.GetNetname() not in ('GND', 'VCC', '+3V3')
              and t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
    grouped = {i.m_Uuid.AsString() for g in board.Groups() for i in g.GetItems()}
    adj, anchors = collections.defaultdict(list), collections.defaultdict(list)
    for t in tracks:
        for pt in (t.GetStart(), t.GetEnd()):
            adj[(t.GetNetname(), t.GetLayer(), xy(pt))].append(t)
    for t in board.GetTracks():
        if type(t) == pcbnew.PCB_VIA:
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                anchors[(t.GetNetname(), layer, xy(t.GetPosition()))].append(t.m_Uuid.AsString())
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if pad.IsOnLayer(layer):
                    anchors[(pad.GetNetname(), layer, xy(pad.GetPosition()))].append(pad.m_Uuid.AsString())
    def stop(key):
        return bool(anchors[key]) or len(adj[key]) != 2 or len({t.GetWidth() for t in adj[key]}) != 1
    seen, result = set(), []
    source_hash = digest(board_path)
    for start, members in list(adj.items()):
        if not stop(start):
            continue
        for track in members:
            if track.m_Uuid.AsString() in seen:
                continue
            chain, points, cur = [], [start[2]], start
            while True:
                uid = track.m_Uuid.AsString()
                if uid in seen:
                    break
                seen.add(uid)
                chain.append(track)
                end = xy(track.GetEnd()) if xy(track.GetStart()) == cur[2] else xy(track.GetStart())
                points.append(end)
                cur = (start[0], start[1], end)
                if stop(cur):
                    break
                track = next(t for t in adj[cur] if t.m_Uuid.AsString() != uid)
            if len(chain) < 4 or len(anchors[start]) != 1 or len(anchors[cur]) != 1:
                continue
            if any(t.IsLocked() or t.m_Uuid.AsString() in grouped for t in chain):
                continue
            ids = [t.m_Uuid.AsString() for t in chain]
            stable = hashlib.sha256((source_hash + ''.join(sorted(ids))).encode()).hexdigest()[:16]
            result.append(dict(id=stable, source_sha256=source_hash, net=str(start[0]),
                layer=int(start[1]), layer_name=pcbnew.LayerName(start[1]),
                width=chain[0].GetWidth(), ids=ids, points=points,
                anchors=[anchors[start][0], anchors[cur][0]],
                length_mm=sum(t.GetLength() for t in chain) / 1e6))
    return sorted(result, key=lambda c: (-len(c['ids']), c['id']))


def make_patch(board_path, chain):
    pcb = parse_kicad_pcb(str(board_path))
    ids = set(chain['ids'])
    selected = [s for s in pcb.segments if s.uuid in ids]
    assert len(selected) == len(ids) and not any(s.locked for s in selected)
    original = {id(s): s for s in pcb.segments}
    results = [{'new_segments': selected, 'new_vias': []}]
    stats = smooth_octolinear_chains(results, pcb,
        scope_net_ids={selected[0].net_id}, clearance=.2,
        board_edge_clearance=.3, keep_input_copper=True)[-1]
    remaining = {id(s) for s in pcb.segments}
    removed = [s.uuid for i, s in original.items() if i not in remaining]
    added = [s for s in pcb.segments if id(s) not in original]
    assert set(removed) <= ids
    for s in added:
        assert s.net_id == selected[0].net_id and s.layer == selected[0].layer
        assert round(s.width * 1e6) == chain['width']
    if not removed:
        return None
    native = []
    for s in added:
        native.append(dict(uuid=str(uuid.uuid4()),
            start=[round(s.start_x * 1e6), round(s.start_y * 1e6)],
            end=[round(s.end_x * 1e6), round(s.end_y * 1e6)],
            width=chain['width'], layer=chain['layer_name'], net=chain['net']))
    return dict(chain=chain, removed=removed, added=native, smoother_stats=stats)


def apply_text(text, patch):
    def mm(n):
        return f'{n / 1e6:.6f}'.rstrip('0').rstrip('.')
    segments = []
    for s in patch['added']:
        segments.append('(segment\n\t\t(start %s %s)\n\t\t(end %s %s)\n\t\t(width %s)\n\t\t(layer %s)\n\t\t(net %s)\n\t\t(uuid %s)\n\t)' % (
            *map(mm, s['start']), *map(mm, s['end']), mm(s['width']),
            json.dumps(s['layer']), json.dumps(s['net']), json.dumps(s['uuid'])))
    removed = set(patch['removed'])
    edits = [(a, b) for a, b, tag, raw in blocks(text)
             if tag == 'segment' and block_uuid(raw) in removed]
    assert len(edits) == len(removed)
    first = edits[0][0]
    for a, b in reversed(edits):
        text = text[:a] + ('\n\t'.join(segments) if a == first else '') + text[b:]
    return text


def audit(before_path, after_path, patch):
    a, b = pcbnew.LoadBoard(str(before_path)), pcbnew.LoadBoard(str(after_path))
    removed, added = set(patch['removed']), {s['uuid'] for s in patch['added']}
    preserve(Path(before_path).read_text(), Path(after_path).read_text(), removed, added)
    ta = {t.m_Uuid.AsString(): t for t in a.GetTracks()}
    tb = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
    assert ta.keys() - tb.keys() == removed and tb.keys() - ta.keys() == added
    c = patch['chain']; layer, width = c['layer'], c['width']
    # Measure the complete chain, including original pieces the smoother kept.
    old = [ta[i] for i in c['ids']]
    new = [tb[i] for i in set(c['ids']) - removed | added]
    inc = collections.Counter()
    def line(t):
        return LineString([(t.GetStart().x / 1e6, t.GetStart().y / 1e6),
                           (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)])
    oldlines, newlines = unary_union([line(t) for t in old]), unary_union([line(t) for t in new])
    for t in new:
        assert type(t) == pcbnew.PCB_TRACK and t.GetNetname() == c['net']
        assert t.GetLayer() == layer and t.GetWidth() == width
        inc.update([xy(t.GetStart()), xy(t.GetEnd())])
    endpoints = {tuple(c['points'][0]), tuple(c['points'][-1])}
    assert {k for k, v in inc.items() if v == 1} == endpoints
    assert all(v in (1, 2) for v in inc.values())
    # Exact integer graph traversal also rejects separate cycles and components.
    adjacency = collections.defaultdict(list)
    for t in new:
        u, v = xy(t.GetStart()), xy(t.GetEnd())
        assert u != v
        adjacency[u].append(v); adjacency[v].append(u)
    visited, ordered, cur, prev = set(), [], tuple(c['points'][0]), None
    while cur is not None:
        assert cur not in visited
        visited.add(cur); ordered.append(cur)
        nxt = [v for v in adjacency[cur] if v != prev]
        assert len(nxt) <= 1
        prev, cur = cur, nxt[0] if nxt else None
    assert len(visited) == len(inc)
    assert LineString(ordered).is_simple, 'Self-crossing replacement'
    allowance = patch.get('max_length_increase_mm', 0.0)
    assert 0 <= allowance <= min(.25, oldlines.length * .05) + .0000001, 'Excessive length allowance'
    assert newlines.length <= oldlines.length + allowance + .000002, 'Length increase'
    def bends(points):
        dirs = []
        for u, v in zip(points, points[1:]):
            dx, dy = v[0] - u[0], v[1] - u[1]
            g = math.gcd(abs(dx), abs(dy)); dirs.append((dx // g, dy // g))
        return sum(u != v for u, v in zip(dirs, dirs[1:]))
    assert bends(ordered) < bends(c['points']), 'No actual bend reduction'
    oldshape, newshape = unary_union([copper(t, layer) for t in old]), unary_union([copper(t, layer) for t in new])
    anchors = set(c['anchors']); contacts = []
    allpads = [p for f in a.GetFootprints() for p in f.Pads()]
    external = [*a.GetTracks(), *allpads]
    by_id = {t.m_Uuid.AsString(): t for t in external}
    lands = unary_union([copper(by_id[i], layer) for i in anchors]).buffer(.00005)
    for t in external:
        uid = t.m_Uuid.AsString()
        if uid in c['ids'] or t.GetNetname() != c['net'] or not t.IsOnLayer(layer):
            continue
        shape = copper(t, layer)
        was, now = oldshape.distance(shape) <= .00001, newshape.distance(shape) <= .00001
        if uid in anchors:
            assert was and now, ('Terminal contact lost', uid)
            contacts.append(uid)
        elif was or now:
            # Several neighboring tracks can meet within one unchanged pad/via
            # land. Their junction is the terminal anchor, not a new branch.
            # Reject every old or new contact outside the two native lands.
            old_contact = oldshape.intersection(shape.buffer(.00001)).difference(lands)
            new_contact = newshape.intersection(shape.buffer(.00001)).difference(lands)
            assert old_contact.is_empty and new_contact.is_empty, ('External contact outside terminal lands', uid)
    assert set(contacts) == anchors
    # Preserve the project's explicit all-layer fastener copper exclusion.
    for fp in b.GetFootprints():
        if fp.GetReference() in ('H1', 'H2', 'H3', 'H4'):
            center = Point(fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6)
            assert newshape.distance(center) >= 2.45 - .000001, 'M2 copper exclusion'
    # Preserve local geometric topology as well: no new contact between the
    # replaced copper and other same-net copper; old contacts only in anchor lands.
    return dict(status='PASS', segments_before=len(old), segments_after=len(new),
        bends_before=bends(c['points']), bends_after=bends(ordered),
        length_before_mm=oldlines.length, length_after_mm=newlines.length,
        external_contacts=contacts, preserved_vias=sum(type(t) == pcbnew.PCB_VIA for t in a.GetTracks()),
        maximum_path_displacement_mm=oldlines.hausdorff_distance(newlines))


def native_check(context, logdir):
    logdir.mkdir(parents=True, exist_ok=True)
    board = next(context.glob('*.kicad_pcb'))
    def run(name, cmd):
        started = time.monotonic()
        result = subprocess.run([str(x) for x in cmd], capture_output=True, text=True)
        (logdir / (name + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, (name, result.returncode)
        return round(time.monotonic() - started, 3)
    protected = {p: digest(p) for p in context.rglob('*') if p.is_file() and p.suffix in ('.kicad_pro', '.kicad_sch', '.kicad_dru', '.kicad_mod', '.kicad_sym')}
    timings = {}
    timings['drc'] = run('drc', ['kicad-cli', 'pcb', 'drc', '--format', 'json',
        '--severity-all', '--schematic-parity', '--refill-zones', '--save-board',
        '--output', logdir / 'drc.json', board])
    timings['physical'] = run('physical', [sys.executable, ROOT / 'scripts/check_v3_2_copper.py',
        '--board', board, '--all-nets', '--output', logdir / 'physical.json'])
    assert all(digest(p) == h for p, h in protected.items()), 'Native check changed authored context'
    drc = json.loads((logdir / 'drc.json').read_text())
    assert all(k in drc for k in ('violations', 'unconnected_items', 'schematic_parity', 'ignored_checks'))
    assert not drc['ignored_checks'], 'Ignored native checks'
    physical = json.loads((logdir / 'physical.json').read_text())
    assert physical['status'] == 'PASS'
    def findings(items):
        # Track replacements intentionally change UUIDs. Retain description and
        # geometry; native findings elsewhere must stay identical.
        return sorted(json.dumps(x, sort_keys=True) for x in items)
    return dict(timings=timings, findings={k: findings(drc[k]) for k in
        ('violations', 'unconnected_items', 'schematic_parity')},
        connected_nets=len(physical['nets']))


def render(before_path, after_path, patch, report, output):
    a, b = pcbnew.LoadBoard(str(before_path)), pcbnew.LoadBoard(str(after_path))
    removed, added = set(patch['removed']), {s['uuid'] for s in patch['added']}
    c = patch['chain']; layer = c['layer']
    points = [(x / 1e6, y / 1e6) for x, y in c['points']]
    xmin, xmax = min(x for x, y in points) - 1.2, max(x for x, y in points) + 1.2
    ymin, ymax = min(y for x, y in points) - 1.2, max(y for x, y in points) + 1.2
    scale = min(90, 650 / (xmax - xmin), 650 / (ymax - ymin))
    pw, ph = round((xmax - xmin) * scale), round((ymax - ymin) * scale)
    pw = max(pw, 340)
    # Native geometry, not the routing parser's approximate pad model.
    font, small = ImageFont.load_default(size=17), ImageFont.load_default(size=13)
    final = Image.new('RGB', (3 * pw + 40, ph + 110), '#101820')
    for i, (board, title) in enumerate([(a, 'Before'), (b, 'After'), (b, 'Overlay')]):
        canvas = Image.new('RGB', (pw, ph), '#16232e'); draw = ImageDraw.Draw(canvas)
        def poly(polyset, color):
            for j in range(polyset.OutlineCount()):
                contour = polyset.COutline(j)
                pts = [((contour.CPoint(k).x / 1e6 - xmin) * scale,
                        (contour.CPoint(k).y / 1e6 - ymin) * scale)
                       for k in range(contour.PointCount())]
                if len(pts) > 2:
                    draw.polygon(pts, fill=color)
                for h in range(polyset.HoleCount(j)):
                    hole = polyset.CHole(j, h)
                    pts = [((hole.CPoint(k).x / 1e6 - xmin) * scale,
                            (hole.CPoint(k).y / 1e6 - ymin) * scale) for k in range(hole.PointCount())]
                    if len(pts) > 2:
                        draw.polygon(pts, fill='#16232e')
        def item(t, color):
            ps = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(ps, layer, 0, 100, pcbnew.ERROR_INSIDE); poly(ps, color)
        for z in board.Zones():
            if not z.GetIsRuleArea() and z.IsOnLayer(layer):
                poly(z.GetFilledPolysList(layer), '#29323a')
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.IsOnLayer(layer): item(pad, '#77848a')
        for t in board.GetTracks():
            if t.IsOnLayer(layer) and type(t) != pcbnew.PCB_VIA and t.m_Uuid.AsString() not in removed | added:
                item(t, '#64717a')
        if i in (0, 2):
            for t in a.GetTracks():
                if t.m_Uuid.AsString() in removed: item(t, '#ffb14e')
        if i in (1, 2):
            for t in b.GetTracks():
                if t.m_Uuid.AsString() in added: item(t, '#40dfea')
        for t in board.GetTracks():
            if type(t) == pcbnew.PCB_VIA:
                x, y = t.GetPosition().x / 1e6, t.GetPosition().y / 1e6
                xx, yy = (x - xmin) * scale, (y - ymin) * scale
                r, hole = t.GetWidth(layer) / 2e6 * scale, t.GetDrillValue() / 2e6 * scale
                draw.ellipse((xx-r, yy-r, xx+r, yy+r), fill='#d6b654')
                draw.ellipse((xx-hole, yy-hole, xx+hole, yy+hole), fill='#16232e')
        xoff = 10 + i * (pw + 10)
        final.paste(canvas, (xoff, 65)); d = ImageDraw.Draw(final)
        count = report['segments_before'] if i == 0 else report['segments_after']
        d.text((xoff, 8), title + (f': {count} segments' if i < 2 else ': orange old / cyan new'), font=font, fill='white')
        d.text((xoff, 34), f"{c['net']} | {c['layer_name']} | {c['width']/1e6:g} mm", font=small, fill='#b5c5d3')
        d.text((xoff, ph + 78), f"{report['length_before_mm']:.3f} -> {report['length_after_mm']:.3f} mm | fixed vias", font=small, fill='white')
    final.save(output)


def snapshot(source, target):
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('exports', '.history', '*-backups', '*.lck', '*.kicad_prl'))


def run(args):
    source = args.board.resolve()
    assert source.is_file() and not args.output.exists()
    assert args.limit >= 0 and not args.output.resolve().is_relative_to(source.parent)
    args.output.mkdir(parents=True)
    initial = args.output / 'initial'; snapshot(source.parent, initial)
    assert digest(initial / source.name) == digest(source)
    current = args.output / 'current'; snapshot(initial, current)
    chains = inventory(initial / source.name); write_json(args.output / 'chains.json', chains)
    if args.chain:
        chains = [c for c in chains if c['id'] == args.chain]
        assert chains, 'Chain ID does not match this exact source snapshot'
    engine_hash = digest(TOOL / 'pcb_modification.py')
    write_json(args.output / 'source.json', dict(board=str(source), sha256=digest(source),
        engine_file=str(TOOL / 'pcb_modification.py'), engine_sha256=engine_hash,
        proposal_function=make_patch.__module__ + '.' + make_patch.__name__,
        proposal_file=inspect.getsourcefile(make_patch),
        proposal_sha256=digest(Path(inspect.getsourcefile(make_patch)))))
    runner = args.output / 'runner-snapshot'; runner.mkdir()
    for code in {Path(__file__).resolve(), Path(inspect.getsourcefile(make_patch)).resolve()}:
        shutil.copy2(code, runner / code.name)
    baseline = native_check(current, args.output / 'baseline-check')
    accepted, trials = [], []
    for index, chain in enumerate(chains[:args.limit] if args.limit else chains):
        folder = args.output / f'trial-{index:03d}'; folder.mkdir()
        started = time.monotonic()
        try:
            patch = make_patch(current / source.name, chain)
            if patch is None:
                trials.append(dict(chain=chain['id'], net=chain['net'], status='NO_CHANGE')); continue
            write_json(folder / 'patch.json', patch)
            proposed = folder / 'candidate'; snapshot(current, proposed)
            before_text = (current / source.name).read_text()
            (proposed / source.name).write_text(apply_text(before_text, patch))
            geometry = audit(current / source.name, proposed / source.name, patch)
            checks = native_check(proposed, folder / 'checks')
            assert checks['findings'] == baseline['findings'], 'Native finding regression'
            assert checks['connected_nets'] == baseline['connected_nets']
            geometry = audit(current / source.name, proposed / source.name, patch)
            render(current / source.name, proposed / source.name, patch, geometry, folder / 'comparison.png')
            # This is a candidate accumulator only. A human/model must review
            # the generated images before final source promotion.
            record = dict(chain=chain['id'], net=chain['net'], status='CHECKED_CANDIDATE',
                geometry=geometry, checks=checks, seconds=round(time.monotonic()-started, 3))
            write_json(folder / 'report.json', record); trials.append(record)
            accepted.append(str(folder.resolve()))
            shutil.copy2(proposed / source.name, current / source.name)
            print(f"{index}: {chain['net']} {geometry['segments_before']} -> {geometry['segments_after']}", flush=True)
        except (AssertionError, ValueError, RuntimeError, KeyError) as error:
            record = dict(chain=chain['id'], net=chain['net'], status='REJECTED', reason=str(error))
            write_json(folder / 'report.json', record); trials.append(record)
            print(f"{index}: {chain['net']} rejected: {error}", flush=True)
    assert digest(source) == digest(initial / source.name), 'Source changed during run'
    write_json(args.output / 'report.json', dict(status='CANDIDATES_AWAIT_VISUAL_REVIEW',
        input_sha256=digest(source), final_sha256=digest(current / source.name),
        baseline=baseline, accepted_trials=accepted, trials=trials))
    print(f'{len(accepted)} checked candidates; main project unchanged: {args.output}', flush=True)


def apply_reviewed(args):
    work = args.run.resolve()
    report = json.loads((work / 'report.json').read_text())
    review = json.loads(args.review.read_text())
    metadata = json.loads((work / 'source.json').read_text())
    source = Path(metadata['board'])
    assert digest(source) == report['input_sha256'], 'Source has changed; regenerate candidates'
    assert not list(source.parent.glob('*.lck')), 'Close the live PCB editor first'
    assert review['run'] == str(work) and review['status'] == 'VISUALLY_REVIEWED'
    expected = {str(Path(x).resolve()) for x in report['accepted_trials']}
    assert set(review['images']) == expected, 'Every accepted trial needs visual review'
    for folder, image_hash in review['images'].items():
        assert digest(Path(folder) / 'comparison.png') == image_hash, 'Reviewed image changed'
    initial = work / 'initial'
    for path in initial.rglob('*'):
        if path.is_file():
            original = source.parent / path.relative_to(initial)
            assert original.is_file() and digest(path) == digest(original), ('Source context changed', original)
    final = work / 'current' / source.name
    assert digest(final) == report['final_sha256']
    removed, added = set(), set()
    for folder in report['accepted_trials']:
        patch = json.loads((Path(folder) / 'patch.json').read_text())
        removed.update(patch['removed']); added.update(s['uuid'] for s in patch['added'])
        assert json.loads((Path(folder) / 'report.json').read_text())['status'] == 'CHECKED_CANDIDATE'
    preserve(source.read_text(), final.read_text(), removed, added)
    backup = work / 'source-before-apply.kicad_pcb'
    assert not backup.exists(), 'This run has already been applied'
    shutil.copy2(source, backup)
    # Recheck immediately before atomic replacement; the candidate is freshly
    # refilled and every intermediate state was graded, with no source edits.
    assert digest(source) == report['input_sha256']
    temporary = source.with_name('.' + source.name + '.cleanup-tmp')
    assert not temporary.exists()
    shutil.copy2(final, temporary); os.replace(temporary, source)
    assert digest(source) == report['final_sha256']
    write_json(work / 'applied.json', dict(status='APPLIED', board=str(source),
        before_sha256=report['input_sha256'], after_sha256=digest(source),
        accepted_chains=len(expected), backup=str(backup),
        removed_segments=len(removed), added_segments=len(added)))
    print(f'Applied {len(expected)} individually checked and visually reviewed trace replacements.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inv = commands.add_parser('inventory'); inv.add_argument('--board', type=Path, required=True); inv.add_argument('--output', type=Path, required=True)
    batch = commands.add_parser('run'); batch.add_argument('--board', type=Path, required=True); batch.add_argument('--output', type=Path, required=True); batch.add_argument('--limit', type=int, default=0); batch.add_argument('--chain', help='Stable chain ID from inventory; omit for a sequential pass')
    app = commands.add_parser('apply'); app.add_argument('--run', type=Path, required=True); app.add_argument('--review', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'inventory':
        value = inventory(args.board); write_json(args.output, value); print(f'{len(value)} anchored candidate chains')
    elif args.command == 'run':
        run(args)
    else:
        apply_reviewed(args)


if __name__ == '__main__':
    main()
