#!/usr/bin/env python3
"""Apply the checked C1/C3 repair to the open demo board via KiCad IPC."""
import argparse
import time
from pathlib import Path

from kipy import KiCad
from kipy.board_types import Track, Via
from kipy.geometry import Vector2

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'hw/ledkiv3-ground-demo'
POINTS = [(45.076, 78.0), (42.776, 78.9), (32.076, 78.9),
          (31.676, 78.5), (31.276, 77.3), (31.276, 69.4),
          (31.876, 68.8), (42.876, 68.7), (45.711, 67.356)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delay', type=float, default=8,
                        help='Seconds to show the via before drawing the trace')
    args = parser.parse_args()
    if not 0 <= args.delay <= 60:
        parser.error('--delay must be between 0 and 60')
    board = KiCad().get_board()
    if Path(board.document.project.path).resolve() != DEMO:
        raise RuntimeError('Open the ground-demo copy, not the archived board')
    ground = next(net for net in board.get_nets() if net.name == 'GND')
    if any(abs(v.position.x - 45076000) < 10 and
           abs(v.position.y - 78000000) < 10 for v in board.get_vias()):
        raise RuntimeError('Repair via already exists; undo the demo before replaying')
    commit = board.begin_commit()
    try:
        via = Via()
        via.position = Vector2.from_xy_mm(*POINTS[0])
        via.diameter = 500000
        via.drill_diameter = 300000
        via.net = ground
        created = board.create_items(via)
        board.clear_selection()
        board.add_to_selection(created)
        print('GND via added near C3: 0.5 mm copper, 0.3 mm drill.', flush=True)
        time.sleep(args.delay)
        tracks = []
        for start, end in zip(POINTS, POINTS[1:]):
            track = Track()
            track.start = Vector2.from_xy_mm(*start)
            track.end = Vector2.from_xy_mm(*end)
            track.width = 250000
            track.layer = board.get_layer_by_name('F.Cu')
            track.net = ground
            tracks.append(track)
        created += board.create_items(tracks)
        board.push_commit(commit, 'Demo: connect C1 and C3 ground sections')
    except Exception:
        board.drop_commit(commit)
        raise
    board.clear_selection()
    board.add_to_selection(created)
    board.set_active_layer(board.get_layer_by_name('F.Cu'))
    board.refill_zones()
    board.save()
    print('Repair selected, zones refilled, demo saved. Ctrl+Z undoes the repair.', flush=True)


if __name__ == '__main__':
    main()
