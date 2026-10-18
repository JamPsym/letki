# Letki v4.1 TME prototype

Status: prototype candidate; USB-edge deviation and physical qualification pending.
Open `ledkiv4_1.kicad_pro`. The promoted routing has zero official DRC findings,
zero open connections and zero schematic-parity issues; ERC and independent
pin/net checks pass. The 2026-10-14 [datasheet audit](../../docs/v4-pad-audit.md)
found the GCT USB edge 0.575 mm inward from the manufacturer's reference;
the corrected geometry check exits nonzero and blocks package regeneration
until this deviation is resolved. The package exporter repeats these checks.
The previous reviewed v4 source is preserved in `hw/ledkiv4/` and the dated
snapshot `archive/hw/ledkiv4-pre-tme-20261012/`.

Five prototypes are the selected batch. TME order 35700057 has been placed;
all 20 lines await delivery. Gerbers were saved to the JLCPCB cart as
`ledkiv4_1-gerbers_Y8` (prototype `Y8-10656422A`); the user is finishing checkout,
so no PCB payment/order confirmation is recorded. Read
[the current state](../../docs/current-state.md) and
[purchase records](../../config/purchase/README.md).

At assembly, use Yageo RC0603FR-075K1L for R30/R31 and Diodes AP22653W6-7
for U5, retaining R32 = 33 kΩ, 1%. These are documented same-footprint purchased
substitutions; this frozen native CAD still names the original parts.
See `config/purchase/v4.1-assembly-substitutions.json`. The purchased CAD snapshot
is preserved at `archive/hw/ledkiv4.1-purchase-20261013/`.

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
`ledkiv4_1-gerbers.zip` to JLCPCB. The generated TME QuickBuy CSV/TXT in
`procurement/` describes the original CAD selection, not the placed order or
purchased substitutions. Actual ordered quantities are in
`config/purchase/TME-35700057-ordered.csv`; do not reimport that record as a new
order. Default drafting quantities
include spares; minimum-cash and twenty-board comparisons are separate.
The ledger reserves components for four remaining v3 boards. Five new tiles
fit the estimated stocked MCU/LED quantities; twenty need 600 extra LEDs.
Future supplier quotes require a refresh. Production-file confirmation is
optional and was left off in the saved cart. Physical qualification remains.

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
