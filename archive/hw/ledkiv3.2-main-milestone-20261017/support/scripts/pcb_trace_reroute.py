#!/usr/bin/env python3
"""Point-to-point A* rerouting of entire trace chains, using native obstacles.

Shares snapshot, native grading, visual review and apply guards with
pcb_trace_cleanup.py. A chain's old copper is absent from the search map.
Filled zones are deliberately absent too; authored rule areas stay obstacles.
No via/layer changes, rip-up of neighbors or attraction to the old path.
"""
from pathlib import Path
import math
import json
import os
import sys
import time
import uuid

import numpy as np
import shapely
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
import pcbnew
import pcb_trace_cleanup as safety
sys.path.insert(0, str(safety.ROOT / '.tools/kicad-routing-tools/rust_router'))
from grid_router import GridRouter, GridObstacleMap


def polyset(poly):
    def points(c):
        return [(c.CPoint(j).x / 1e6, c.CPoint(j).y / 1e6) for j in range(c.PointCount())]
    return unary_union([Polygon(points(poly.COutline(i)),
        [points(poly.CHole(i, h)) for h in range(poly.HoleCount(i))])
        for i in range(poly.OutlineCount())])


def reroute(board_path, chain):
    begin = time.monotonic()
    board = pcbnew.LoadBoard(str(board_path)); layer = chain['layer']
    removed = set(chain['ids']); width = chain['width'] / 1e6
    anchor_ids = set(chain['anchors'])
    items = [*board.GetTracks(), *[p for f in board.GetFootprints() for p in f.Pads()]]
    by_id = {t.m_Uuid.AsString(): t for t in items}
    lands = unary_union([safety.copper(by_id[i], layer) for i in anchor_ids])
    foreign, own, fixed = [], [], []
    for t in items:
        uid = t.m_Uuid.AsString()
        if uid in removed or uid in anchor_ids or not t.IsOnLayer(layer):
            continue
        g = safety.copper(t, layer)
        if not g.is_empty:
            (own if t.GetNetname() == chain['net'] else foreign).append(g)
    for fp in board.GetFootprints():
        if fp.GetReference() in ('H1', 'H2', 'H3', 'H4'):
            p = fp.GetPosition(); fixed.append(Point(p.x / 1e6, p.y / 1e6).buffer(2.45 + width / 2, quad_segs=64))
    # Authored copper keepouts apply even while pours are absent.
    for z in board.Zones():
        if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks():
            fixed.append(polyset(z.Outline()).buffer(width / 2))
    outline = pcbnew.SHAPE_POLY_SET()
    assert board.GetBoardPolygonOutlines(outline, False)
    project = json.loads(Path(board_path).with_suffix('.kicad_pro').read_text())
    edge_clearance = project['board']['design_settings']['rules']['min_copper_edge_clearance']
    legal = polyset(outline).buffer(-(edge_clearance + width / 2))
    ax, ay = chain['points'][0]; bx, by = chain['points'][-1]
    # Lattice origin is anchor A. Prefer a step that reaches both exact anchors;
    # native 1 nm right-angle artifacts are retained at the terminal afterward.
    def fits(step):
        return all(abs(d - round(d / step) * step) <= 1 for d in (bx - ax, by - ay))
    steps = [s for s in (12500, 10000, 6250, 5000) if fits(s)]
    if not steps:
        raise ValueError('Terminals require a finer lattice than this bounded pass')
    step = steps[0] / 1e6; ox, oy = ax / 1e6, ay / 1e6
    # Four mm around the complete old route, clipped to the board. This is a
    # finite search window, not an old-route cost or a retained-copper corridor.
    px = [x / 1e6 for x, y in chain['points']]; py = [y / 1e6 for x, y in chain['points']]
    lx, ly, hx, hy = legal.bounds
    xmin = max(lx - step, min(px) - 4); xmax = min(hx + step, max(px) + 4)
    ymin = max(ly - step, min(py) - 4); ymax = min(hy + step, max(py) + 4)
    gx0, gx1 = math.floor((xmin - ox) / step), math.ceil((xmax - ox) / step)
    gy0, gy1 = math.floor((ymin - oy) / step), math.ceil((ymax - oy) / step)
    xs = ox + np.arange(gx0, gx1 + 1) * step
    ys = oy + np.arange(gy0, gy1 + 1) * step
    assert len(xs) * len(ys) <= 12000000, 'Search raster exceeds bounded memory budget'
    extra = .002  # 2 um numerical guard, separate from authored design rules.
    obstacles = []
    if foreign:
        obstacles.append(unary_union(foreign).buffer(.2 + width / 2 + extra, quad_segs=32))
    if own:
        # Other branches of this same net are also frozen obstacles. Contact
        # within the existing terminal lands is permitted by the topology gate.
        g = unary_union(own).difference(lands)
        obstacles.append(g.buffer(width / 2 + extra).difference(lands.buffer(-extra)))
    obstacles.extend(fixed)
    forbidden = unary_union(obstacles); shapely.prepare(forbidden); shapely.prepare(legal)
    mask = np.empty((len(ys), len(xs)), dtype=np.bool_)
    # Chunk vectorization keeps coordinate temporaries bounded on long routes.
    for y0 in range(0, len(ys), 128):
        yy = ys[y0:y0 + 128, None]
        mask[y0:y0 + 128] = shapely.intersects_xy(forbidden, xs[None, :], yy) | ~shapely.contains_xy(legal, xs[None, :], yy)
    mask[[0, -1], :] = True; mask[:, [0, -1]] = True
    target = (round((bx / 1e6 - ox) / step), round((by / 1e6 - oy) / step), 0)
    source = (0, 0, 0)
    for gx, gy, _ in (source, target):
        if mask[gy - gy0, gx - gx0]:
            raise ValueError('Fixed terminal blocked at conservative raster clearance')
    grid = GridObstacleMap(1); spans = []
    for ix in range(len(xs)):
        edges = np.diff(np.r_[False, mask[:, ix], False].astype(np.int8))
        starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1
        spans.extend((gx0 + ix, gy0 + int(lo), gy0 + int(hi), 0) for lo, hi in zip(starts, ends))
    if spans:
        grid.add_static_blocked_cell_spans_batch(np.asarray(spans, dtype=np.int32))
    # One physical layer makes insertion of a via impossible. No old-path
    # attraction is set. Length plus a modest bend penalty controls the search.
    router = GridRouter(via_cost=1000000, h_weight=1.0, turn_cost=round(.1 / step * 1000),
                        via_proximity_cost=0, layer_costs=[1000])
    path, iterations, stats = router.route_multi(grid, [source], [target], 500000)
    if path is None:
        raise ValueError(f'A* did not find a path in {iterations} states at {step:g} mm')
    points = [path[0]]
    for u, v, z in zip(path, path[1:], path[2:]):
        if (v[0]-u[0], v[1]-u[1]) != (z[0]-v[0], z[1]-v[1]):
            points.append(v)
    points.append(path[-1])
    native = [[round((ox + x * step) * 1e6), round((oy + y * step) * 1e6)] for x, y, _ in points]
    native[0] = list(chain['points'][0]); native[-1] = list(chain['points'][-1])
    added = [dict(uuid=str(uuid.uuid4()), start=a, end=b, width=chain['width'],
                  layer=chain['layer_name'], net=chain['net']) for a, b in zip(native, native[1:])]
    return dict(chain=chain, removed=chain['ids'], added=added,
        max_length_increase_mm=min(.25, chain['length_mm'] * .05),
        router=dict(engine='KiCadRoutingTools Rust GridRouter.route_multi',
                    algorithm='fresh single-layer A*', old_trace_removed=True,
                    pours_in_search=False, grid_step_mm=step, sampling_guard_mm=extra,
                    board_edge_clearance_mm=edge_clearance,
                    max_iterations=500000, iterations=iterations, search_stats=stats,
                    search_window_mm=[xmin,ymin,xmax,ymax],
                    elapsed_seconds=round(time.monotonic()-begin,3)))


if __name__ == '__main__':
    safety.make_patch = reroute
    safety.main()
