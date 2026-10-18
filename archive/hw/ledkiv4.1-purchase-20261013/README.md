# Letki v4.1 TME prototype

Status: CAD-consistent prototype candidate; physical qualification pending.
Open `ledkiv4_1.kicad_pro`. The promoted routing has zero official DRC findings,
zero open connections and zero schematic-parity issues; ERC and independent
pin/net and geometry checks pass. The package exporter repeats these checks.
The previous reviewed v4 source is preserved in `hw/ledkiv4/` and the dated
snapshot `archive/hw/ledkiv4-pre-tme-20261012/`.

This iteration retains the user's stocked CH32V003F4P6 and orange XL-2012UOC.
New supporting parts must have TME sourcing. Prototype availability, electrical
margin and ease of assembly take priority over minimizing every BOM line;
costs remain recorded. Later larger batches may use LCSC after exact-part or
qualified-alternative matching.

Four layers, the 8×8 LED geometry, symmetric seven-hole wire contacts, mounting
holes, SWIO, UART/I2C and all eight row PWM channels are retained. V4.1 uses
SO16 HCT238, DMG2302UK, MIC5504, ALPS SKRPABE010 and GCT USB4105 parts.
UART has Nexperia 74LVC2G34GW buffers and 220 Ω series resistors; scope its
input transitions during first-article qualification.

Generate the purchase handoff from the repository root:

```sh
python scripts/setup_kicad_svg.py
python scripts/v4_1_package.py
```

Validated artifacts go to `exports/prototype/`. Upload
`ledkiv4_1-gerbers.zip` to JLCPCB; use the TME QuickBuy CSV/TXT in `procurement/`
for five boards, one USB head and optional SWIO headers. Default quantities
include spares; minimum-cash and twenty-board comparisons are separate.
The ledger reserves components for four remaining v3 boards. Five new tiles
fit the estimated stocked MCU/LED quantities; twenty need 600 extra LEDs.
Checkout stock/prices and fabricator production files still need confirmation.

See [the design/checks brief](../../docs/v4_1-design.md) and
[order/bring-up instructions](../../docs/v4_1-order-and-bringup.txt).
The handoff includes native sources, assembly SVG/PDF, routing statistics,
via-finish maps and printable/editable mechanical models. Its manifest hashes
the reviewed sources. Work from this native project for later changes; do not
replay old creation, placement or one-time ECO helpers on the routed board.

Open `exports/prototype/routing-review/viewer.html` locally for interactive
per-net SVGs of all four layers, the previous v4 and preserved trial candidates.
The embedded SVGs work without a server. Statistics remain separately readable
in `routing-review/index.html` and its CSV. `docs/v4_1-routing-trials.csv`
preserves the trial numbers for fresh checkouts without ignored working copies.
SVG Extras runs at a pinned commit on isolated copies; matching source/output
hashes let later exports reuse its SVGs safely.
