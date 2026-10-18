# Live ground-repair demo

This working copy comes from `archive/hw/ledkiv3/`. It demonstrates repairing the disconnected C1/C3 ground sections, using the official KiCad IPC API. It is a demonstration layout, not a fabrication release or a renamed v4 revision.

The repair adds one through GND via at (45.076, 78.000) mm, with 0.5 mm copper diameter and 0.3 mm drill, and a 0.25 mm front-layer trace to the existing ground via at (45.711, 67.356) mm. The route goes around existing copper toward the left edge. This intentionally conservative route is longer than an optimized redesign.

The prechecked repair eliminated the missing ground connection without adding clearance, short, or track-width violations. Other existing DRC findings remain; no fabrication exports were generated. Local reports are under `build/hardware/v3-ground-audit/`.

## Replay in KiCad

The local `.tools/kicad-api/` environment contains `kicad-python==0.8.0`. KiCad's API server has been enabled in Preferences. Open this copy with the existing desktop launcher:

```sh
pcbnew hw/ledkiv3-ground-demo/ledkiv3.kicad_pcb
```

Immediately after the agent's live edit, Ctrl+Z undoes the grouped repair. Save the unrepaired demo before replaying (undo history does not survive closing the editor). Then run:

```sh
.tools/kicad-api/bin/python scripts/pcb_ground_demo.py
```

The script shows the new via for eight seconds, adds the trace, refills zones, selects the repair and saves the demo. It checks the open project path and refuses to add a duplicate via. It does not edit the archive. After undoing, refill zones to update connectivity.
