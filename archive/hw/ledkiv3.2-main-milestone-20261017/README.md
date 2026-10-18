# Letki v3.2 — accepted main CAD version

Open `ledkiv3_2.kicad_pro`. CH32V006E8R6/QSOP24, 49.6 mm square, 6.2 mm pixels;
west-to-east USART1, south-to-north USART2, shared I²C and separate LED blanking.
All 159 original component placements and padstacks are preserved.

The user accepted the current 1,490-segment board as the main version on
2026-10-17. Native DRC has zero errors and the existing `/ADDR0` dangling-track
warning; opens, parity and ignored checks are zero. Independent continuity
confirms all 76 nets. ERC and the unchanged circuit/placement/padstack checks
retain their earlier results; the acceptance record identifies their scope.
Power uses In2 VCC plus stitched front reinforcement; In1 has seven explicitly
reviewed signal segments on two nets. See [routing and limits](ROUTING.txt).

The full unrouted checkpoint for human routing is
`../../archive/hw/ledkiv3.2-unrouted-20261017/` from the repository root;
copy its complete folder before editing. v3.1 remains preserved.

Checked exports belong in `exports/prototype/`. This is CAD for a prototype;
physical electrical/mechanical tests and fabricator process confirmation remain.
The existing v3/v3.1 firmware is incompatible; the new application and custom
loader have not been implemented or flashed. The older diffuser does not fit.
No stock reservation or purchase is implied.

## Accepted milestone and manual editing

The current accepted main milestone is `v3_2-main-20261017`, preserved in
`archive/hw/ledkiv3.2-main-milestone-20261017/` from the repository root.
[Acceptance record](baseline.json) binds the saved CAD and its checks.
The first robot-routed milestone `v3_2-routed-20261017` remains frozen in
`archive/hw/ledkiv3.2-routed-milestone-20261017/` for comparison.

**Continue manual component/placement/routing changes in this main project.**
The milestones and older unrouted checkpoint stay frozen. Existing fabrication
exports describe the first robot milestone and have not been regenerated for
this accepted main version. Changed CAD needs fresh checks and deliberate review
of its baseline-specific contracts. Preserve later human edits.

## Trace cleanup of the manual working state (2026-10-17)

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

## Fresh point-to-point routing follow-up (2026-10-17)

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
