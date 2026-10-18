# Letki v3.1 — shared working project

Latest schematic edit: buttons and their RC networks removed; all sixteen
MOSFET stages are native KiCad groups with their own resistors and wiring.
Forty gate/bias resistors now use project-local 0603 hand-solder footprints;
R1–R8 LED-current resistors remain 0805. **PCB synchronization is pending**:
the open board still has the previous button/0805 population. Its old clean
DRC/parity results do not qualify this newer schematic revision.

Both electrical breaks from the [Astra review](../../docs/v3_1-astra-review-20261015.txt)
are repaired: D9–D16 cathodes reconnect to L2/R2, and R39 pin1 to VCC.
Fresh ERC is zero. The updated independent schematic audit passes all 146
components, including the 40 gate/bias 0603 footprints. PCB geometry DRC/open
connections are zero, with 90 remaining schematic parity findings from the
pending PCB update. No checks are ignored. Repair/check evidence is in
`build/hardware/v3_1-astra-fixes/` at the repository root; PCB and firmware
were not edited.

Run `python3 scripts/check_v3_1_integrated.py --schematic-only` from the
repository root during schematic work. Its report explicitly leaves the PCB
unchecked. The default full audit still requires a matching PCB and rejects
the current unsynchronized board; use it again after PCB rework.

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
They are not the current fabrication package. Current exports/ has no released
handoff; generate a new package only after current checks and process review.
Physical current/timing/thermal/interface/optical/mechanical qualification remains
pending. The fabricator's Plugged/Tented process decision also remains open.
ESP-12F and the power head are deferred until tile hardware verification.

Libraries/models are project-local. Board-specific electrical studies are
archived; general research is in ~/electronics. Do not replay old placement,
creation or routing helpers on this shared board.
