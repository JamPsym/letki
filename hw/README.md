# Hardware projects

Each maintained board uses the same basic layout: open its KiCad project directly
in `hw/<board>/`; local libraries and models stay beside it, mechanical source
belongs in `mechanics/` when present, and generated handoffs go in `exports/`.
Keep superseded board-specific designs in `archive/hw/`, raw experiments in
`build/hardware/`, and reusable research in `~/electronics/notes/`.

| Folder | Role | Open |
| --- | --- | --- |
| [ledkiv3.2](ledkiv3.2/README.md) | Accepted main v3.2 after manual edits and trace cleanup; frozen milestone saved | [KiCad](ledkiv3.2/ledkiv3_2.kicad_pro) |
| [ledkiv3.1](ledkiv3.1/README.md) | Accepted v3.1 baseline; frozen source/package saved, physical qualification pending | [KiCad](ledkiv3.1/ledkiv3_1.kicad_pro) |
| [ledkiv4](ledkiv4/README.md) | Preserved v4 prototype candidate | [KiCad](ledkiv4/ledkiv4.kicad_pro) |
| [ledkiv4.1](ledkiv4.1/README.md) | Selected earlier purchase baseline; see current-state and assembly substitutions | [KiCad](ledkiv4.1/ledkiv4_1.kicad_pro) |
| [ledkiv3-ground-demo](ledkiv3-ground-demo/README.md) | Live editable repair demonstration; not a fabrication candidate | [PCB](ledkiv3-ground-demo/ledkiv3.kicad_pcb) |

The original v3 and older revisions are archived. V3.1 circuit-study schematics
are in [the dated archive](../archive/hw/ledkiv3.1-studies-20261015/README.txt).
Automatic `.history/`, editor state and existing frozen export ZIPs are retained.
Do not regenerate CAD or an uploaded package as part of folder maintenance.
