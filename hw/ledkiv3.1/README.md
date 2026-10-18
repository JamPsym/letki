# Letki v3.1 — accepted design baseline

**Accepted as v3.1 on 15 October 2026; CAD checks pass.**
The [baseline record](baseline.json) identifies the exact accepted CAD and
[frozen snapshot](../../archive/hw/ledkiv3.1-baseline-20261015/BASELINE.txt).
That snapshot includes the original checked fabrication/validation package.
Physical qualification remains pending.
Astra completed power distribution, GND stitching, via margins and assembly
silkscreen around the human placement. All 146 component positions, pad/net
geometry, models and the outline are preserved. The board has 974 track
segments and 131 ordinary tented vias. Gate/bias resistors remain 0603;
R1–R8 remain 0805.

Native ERC, DRC, open connections, schematic parity and ignored checks are all
zero. Independent pad/circuit, multilayer power-connectivity and manufacturing
checks pass. GND has three In1 regions joined through rear bridges; VCC has
six In2 regions joined through the deliberate feeds. Both nets are continuous.
The reviewed 2mm VCC crossbar, source feeds, widened column paths and 77 rear
labels are bound by geometry contracts. [Changes, evidence and limits](../../docs/v3_1-completion-20261015.txt).

Run the circuit and manufacturing checks with
`.tools/kicad-routing-env/bin/python scripts/check_v3_1_integrated.py` and
`.tools/kicad-routing-env/bin/python scripts/check_v3_1_manufacturing.py`.
The routed checker includes an independent actual-copper connectivity gate;
changing an exception list alone cannot make disconnected power pass.
The placement-only checker is historical and requires an unrouted board.
Do not replay placement, creation or routing-seed helpers on this source.

Open [ledkiv3_1.kicad_pro](ledkiv3_1.kicad_pro) for both the schematic and PCB.
This is the single human/agent edit target. Read the
[shared workflow](../../docs/v3_1-shared-workflow.txt) before an edit handoff.

Current simplification uses **one 33 Ω E12 resistor per row**, with a selected
1% 0805/125mW part. R58–R65 and JP1/JP2 are removed. Fit R11/R12 on one I²C
pull-up tile only. The tile retains CH32V003F4P6, SN74HC138PWR, eight AO3415A
and eight DMN2056U-7. Supply: externally regulated **3.3 V ±5%**.

Use the matching `make VARIANT=v3_1-pulse` bounded-pulse image or
`make v3_1-interface-demos` LED-off diagnostics. Original v3 and repetitive
MOSFET-study firmware are incompatible. Software profile labels now identify
33R; no image was flashed. First provision still requires R49 open/R38 fitted,
matching firmware/readback and separately authorized PD7 configuration.
See [assembly/qualification](../../docs/v3_1-assembly-test.txt).

The previous checked 34 Ω CAD and frozen exports are preserved in
[the dated archive](../../archive/hw/ledkiv3.1-checked-34R-20261015/ARCHIVE.txt).
The latest routed predecessor is separately saved in
[the pre-placement archive](../../archive/hw/ledkiv3.1-routed-before-placement-20261015/ARCHIVE.txt).
They are not the current fabrication package. Current checked prototype exports belong in exports/prototype/; its manifest
records all gates and source hashes. Fabricator process/preview confirmation
is still required before ordering.
Physical current/timing/thermal/interface/optical/mechanical qualification remains
pending. The fabricator's Plugged/Tented process decision also remains open.
ESP-12F and the power head are deferred until tile hardware verification.

Libraries/models are project-local. Board-specific electrical studies are
archived; general research is in ~/electronics. Do not replay old placement,
creation or routing helpers on this shared board.
