# Letki v3.1 — checked prototype tile

A new schematic simplification is in progress. See
[the next-iteration note](../../docs/v3_1-next-iteration.txt) for the checked
33 Ω candidate. This directory and its frozen exports still represent the
previous 34 Ω circuit; the candidate has no synchronized PCB yet.

Open `ledkiv3_1.kicad_pro`. This is the completed Study C tile promoted into the main
repository on 2026-10-15. The original seed, electrical studies, archived v3 and initial
unrouted integration are preserved. ESP-12F and the custom power head are
explicitly deferred until hardware verification.

The tile retains stocked CH32V003F4P6 and SN74HC138PWR, with eight AO3415A
column sources and eight DMN2056U-7 row sinks. Each row has two 68Ω resistors
in parallel (34Ω). Supply is externally regulated **3.3V ±5%**. All LEDs reverse
relative to v3. Use `make VARIANT=v3_1-pulse`; original v3 and repetitive
MOSFET-study firmware are incompatible. `make v3_1-interface-demos` builds
separate communication images that hold LED rows LOW.

The 40.64×49.27mm four-layer board is fully routed. Native ERC/DRC/open nets/
schematic parity/ignored checks are zero. Independent checks cover 369 retained
core pins, 390 pads, ordinary tented vias, power geometry, fastener clearance
and assembly markings. In1 crossovers are individually whitelisted; the ground
plane remains connected. This establishes CAD intent, not pulse/current,
thermal, optical, supply or production qualification.

Contacts are symmetric ordinary PTH wire holes: top-to-bottom 3V3/3V3/SDA/
SCL/UART/GND/GND. RX is on the left, TX on the right. Enable JP1/JP2 and fit
R11/R12 on only one selected I²C pull-up tile. Rear PicoBlade 53047-0310 and
bare pads share J2: 1 REF3V3, 2 SWIO, 3 GND. The current LinkE cable uses
only pins2/3 with independent board power.

R4 is on the front at (16.45,27.7), beneath a closed pocket in the matching
optical grid. JP2 is on the lower front at (33.5,45.3); remove optics for access.
Silk numbers identify resistors, P1/P2 identify jumpers, C1–C5 retain prefixes.
Full references remain in CAD/Fab/BOM. Six displaced marks have silk leaders.

**First provisioning:** leave R49 open and fit R38. Program/readback the matching
image, then separately authorize/set/readback PD7 GPIO configuration. Power OFF
before fitting R49. Verify debug timer-freeze behavior before powered breakpoint
work. Read `docs/v3_1-assembly-test.txt` from the repository root.

Generate the checked package from the repository root:

```sh
PCB_GEOMETRY_PYTHON=/path/to/python-with-pcbnew-and-shapely python3 scripts/v3_1_package.py
```

Requires KiCad10 CLI/Python, Shapely2, FreeCAD/Pillow host dependencies and WCH
GCC configured as documented in `docs/arch-setup.md`. Current installed geometry
Python is in this repository's ignored `.tools/kicad-routing-env/`.
The exporter checks frozen sources and produces `exports/prototype/` with
Gerbers/drills, schematic, assembly/BOM, matched firmware, populated STEP,
printable 1/4-tile mechanics, source/artifact hashes and qualification worksheet.
Every physical qualification row remains pending. Confirm actual fabricator
preview/process and fresh parts/PCB/assembly prices before an authorized order.
No ordering, inventory changes or hardware access occur during packaging.

The existing exports/prototype package is the byte-identical session handoff;
its manifest/source ZIP records the original session context. Do not interpret
that frozen manifest as hashes of every current main-repository file.
See docs/v3_1-handoff.txt and build/hardware/v3_1-migration/ for migration checks.
The JLCONE quote currently forces Plugged instead of Tented: fabrication remains
on hold until treatment of vias and open solder holes is reconciled.

Repository layout: this directory contains the active KiCad project directly,
its project-local libraries/models and exports/. Superseded circuit study CAD
is in archive/hw/ledkiv3.1-studies-20261015/. The pulse schematic there remains
the checker's immutable electrical reference. General lessons are summarized in
/home/pies/electronics/notes/circuits/2026-10-15-led-matrix-drive-studies.txt.
See ../../docs/v3_1-handoff.txt for firmware, qualification and sourcing links.
