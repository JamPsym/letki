LETKI V3.1 — HISTORICAL CIRCUIT STUDIES, archived 2026-10-15

These are board-specific design-history schematics, not fabrication candidates.
They retain their local symbols, footprints, projects and exact schematic bytes.
transistor-study: Study A, 8 PMOS column sources; MCU sinks LED current through
680-ohm rows. Decoder output current is bypassed, MCU current remains limiting.
tme-study: Study B2, 8 PMOS plus 8 NMOS, 100-ohm row resistors. Both ICs drive
gates only; its long repetitive PWM interval cannot use the LED short-pulse rating.
pulse-study: Study C, same 16 MOSFETs, 2x68-ohm parallel rows, hardware-ended
short pulses. This is the retained electrical reference for the active tile.

Active PCB: ../../../hw/ledkiv3.1/ledkiv3_1.kicad_pro
Checker: ../../../scripts/check_v3_1_integrated.py
Reusable conclusions: /home/pies/electronics/notes/circuits/2026-10-15-led-matrix-drive-studies.txt
Exact board-specific notes/configuration remain in Letki docs/v3_1-* and config/.
Historical creator/checker scripts are retained under scripts/ as original
provenance. Their old repository-relative assumptions are not a supported
execution interface. Do not replay them against active CAD or this archive.
No study has physical transistor/current/thermal qualification.
