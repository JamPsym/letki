# Archived v3 hardware

Archived on 2026-10-09 after identifying a disconnected ground network. This is the onboard CH32V003 and 74HC138 revision used by the active firmware in `firmware/v3/`.

## Required physical repair

The user connected **C1 pad 1 (GND) to C3 pad 1 (GND)** with a jumper on the working board. Both pads are assigned to the same GND net, but the PCB copper does not join their sections:

- C1's section connects to U2 ground pads 4, 5 and 8.
- C3's section connects to U1 ground pad 7 and C4 pad 2.

KiCad DRC, with zones refilled, reported one missing connection between a GND track on B.Cu and a GND track on In1.Cu. Tracing tracks and vias associated these two tracks with C3 and C1 respectively. The same run reported 198 other violations, including isolated copper and board-edge clearance findings; these have not been resolved or fully reviewed. The local report is `build/hardware/v3-ground-audit/drc.json`.

## Archive contents

The KiCad schematic, PCB, project, diffuser and existing local artifacts were moved without changing their contents. The user's modified project and FreeCAD model were preserved. The physical jumper is documented here, but has not been added to the archived PCB layout. Firmware and speech demos remain active.

The successor [v3.1 revision](../../../hw/ledkiv3.1/README.md) incorporates the demonstrated ground repair. Its missing connection is resolved, but existing DRC findings still need review before fabrication. No new fabrication outputs were generated.

## Experimental printed paste stencils (2026-10-15)

`scripts/v3_stencil.py`, run from the repository root with
`.tools/kicad-routing-env/bin/python`, generates two flat 0.20 mm stencils in
`archive/hw/ledkiv3/exports/stencil-fdm/`. The original PCB is read only and
hash checked. Front has 128 LED openings; rear has 82 component openings and
is mirrored into rear component view. Both sheets are 52.64 × 56.45 mm.

Apertures use approximately 60% of pad area to compensate for the 0.20 mm
sheet versus a nominal 0.12 mm paste deposit. U1/U2 openings are 0.25 ×
1.416 mm, leaving 0.40 mm webs at the 0.65 mm pitch. This is an experimental
FDM adaptation, not a qualified paste-volume or release specification.
Four L slots outside each PCB corner assist alignment. Place the bed side
against the PCB and align the openings directly over the pads; support the
margin on spare boards of matching thickness and tape it down. The rear
pattern is asymmetric and must match the rear component pads. Inspect the
fine IC slots before spreading paste. Let the thin PETG sheets cool before
gently removing them from the plate.

The saved A1 mini job uses the existing external PETG spool, 255 °C nozzle,
70 °C textured plate, Arachne, one 0.20 mm layer and no brim/support. Both
stencils fit one plate. Slicer estimates: 19m23s including preparation,
1.49 g object filament. Native solids/meshes pass; extrusion-path checks
retain all 210 openings and all 32 IC separating webs. Actual fit, release,
paste deposits and printed aperture sizes remain unverified.

Print job/evidence: `build/printer/stencils-v3-job.json` and
`build/hardware/v3-stencil-print/` (profiles, sliced archive, toolpath image
and opening/web checks). Exported STL, STEP, preview and source/pad manifest
are beside `letki-v3-stencils-20261015.gcode.3mf` in the ignored export
directory. Printing does not resolve the archived PCB's known ground fault
or other DRC findings.

For this external-spool printer, `bambu-cli print start` requires `--no-ams`
**before** the positional filename; its default enables AMS and waits for
absent hardware. With `--no-upload`, use the already-uploaded printer-side
basename, not a local path. The initial waiting attempt was cancelled before
extrusion and restarted with those corrected arguments; retain the job record
and check live status before any repeat to avoid duplicate printing.
