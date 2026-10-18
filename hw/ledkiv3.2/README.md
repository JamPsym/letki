# Letki v3.2 — checked five-board prototype candidate

Open `ledkiv3_2.kicad_pro`. CH32V006E8R6/QSOP24, 49.6 mm square, 6.2 mm pixels;
west-to-east USART1, south-to-north USART2, shared I²C and separate LED blanking.
All 159 original component placements and padstacks are preserved.

The accepted main milestone is preserved unchanged. This fabrication derivative
removes its dangling `/ADDR0` stub, restores the Q3/R25 supply branch widths
and selects six exact passive MPNs. It has 1,489 segments and 299 fixed vias.
The two J2 pin1-marker silk lines also have improved pad clearance.
Fresh ERC, DRC, opens, parity and ignored findings are all zero; independent
continuity confirms all 76 nets. All 159 placements and padstacks remain fixed.
[Fabrication identity](fabrication.json) records the exact source and scope.
Power uses In2 VCC plus stitched front reinforcement; In1 has seven explicitly
reviewed signal segments on two nets. See [routing and limits](ROUTING.txt).

The full unrouted checkpoint for human routing is
`../../archive/hw/ledkiv3.2-unrouted-20261017/` from the repository root;
copy its complete folder before editing. v3.1 remains preserved.

Current checked exports belong in `exports/fabrication-20261017-r2/`. The older
`exports/prototype/` is historical. Read [the handoff](../../docs/v3_2-fabrication-20261017.txt)
and [assembly instructions](ASSEMBLY.txt). This is CAD for a prototype;
physical electrical/mechanical qualification remains. JLCONE defaults are
user-selected for the prototype; currentr2Gerbers are uploaded and the
reference preview inspected. Final engineering production files are unconfirmed.
The existing v3/v3.1 firmware is incompatible; the new application and custom
loader have not been implemented or flashed. The older diffuser does not fit.
No stock reservation or purchase is implied.

The user subsequently confirmed ordering **15 bare boards, split 5+10**, on
17 October 2026. See [the order and next steps](../../docs/v3_2-order-and-bringup.txt).
Receipt is pending; the paid amount and supplier order number are unverified.
The checked export retains its original five-board assembly snapshot. The
[new requirements worksheet](../../config/purchase/v3_2-assembly-requirements-20261017.csv)
covers fifteen v3.2 plus the separate five v3.1 boards, without changing stock
or this CAD. Incoming AliExpress parts are recorded in Electronics; firmware
and physical component/tile qualification remain pending.

## Accepted milestone and manual editing

The parent accepted main milestone is `v3_2-main-20261017`, preserved in
`archive/hw/ledkiv3.2-main-milestone-20261017/` from the repository root.
[Acceptance record](baseline.json) binds the frozen accepted milestone and its
checks; `fabrication.json` binds the current derivative.
The first robot-routed milestone `v3_2-routed-20261017` remains frozen in
`archive/hw/ledkiv3.2-routed-milestone-20261017/` for comparison.

**Continue manual component/placement/routing changes in this main project.**
The milestones and older unrouted checkpoint stay frozen. The new fabrication export identifies this derivative. Historical exports and
comparison snapshots retain their original source identities. Changed CAD needs
fresh checks and deliberate review of baseline-specific contracts. Preserve later human edits.

## Historical trace cleanup of the manual working state (2026-10-17)

The one-chain cleanup retained 68 checked, visually reviewed replacements:
1,850 track segments became 1,594. All 299 vias, 159 footprints, native padstacks,
net topology, widths, supply routing and inner-layer copper are preserved.
All 76 nets remain independently connected; native unconnected items and
schematic parity are zero. The pre-existing dangling `/ADDR0` track warning
remains; no new native findings were introduced. Nineteen proposals made no
useful change; four proposals had ambiguous external contacts and one did not
reduce actual bends, so those five were rejected.

Use the [trace cleanup workflow](../../docs/v3_2-trace-cleanup.txt) for another
isolated pass or one selected chain. Before/after renders, per-chain checks,
source backup and application hashes are in
`build/hardware/v3_2-trace-cleanup-checked-20261017/` from the repository root.
The accepted routed milestone stays frozen. Existing exports describe their
recorded earlier source and need regeneration before fabrication use.

## Historical point-to-point routing follow-up (2026-10-17)

An additional 50 complete connections were deleted and freshly routed with A*,
one at a time, with copper pours excluded from the search: 48 on F.Cu and two
on B.Cu. The main board now has 1,490 track segments, down from 1,594. The
affected paths have 97 fewer bends and add 5.693 mm total length; each accepted
increase stays within both 5% and 0.25 mm. All vias, placements, widths, net
junctions, power routing and inner-layer tracks remain fixed. Thirty-three
unhelpful or rejected proposals retained their original copper.

Native DRC/parity findings remain identical to the manual-state baseline,
including the existing `/ADDR0` dangling-track warning. All 76 nets remain
independently connected after zone refill. Evidence, native comparison renders,
the exact previous PCB and application hashes are in
`build/hardware/v3_2-point-reroute-checked-20261017/` from the repository root.
The source schematic/project/rules and frozen milestone are preserved; existing
fabrication exports still describe their earlier source.

The [first robot version / current routing comparison](https://psym.pl/zobaczadas/v3.2-comparison/)
shows all four layers with linked net highlighting, zoom/pan and a wipe view.
It compares the frozen 2,015-segment milestone with the current 1,490-segment
board, including the manual changes before cleanup. Website source is under
`~/local_network/pieslab0/websites/psym.pl/zobaczadas/`; SVG provenance and
browser/deployment checks are in `build/hardware/v3_2-web-comparison-20261017/`.
