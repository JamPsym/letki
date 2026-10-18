# V4.1 source snapshot for the prototype purchase

This snapshot preserves the native CAD, local libraries/models and mechanics
corresponding to Gerbers saved in the JLCPCB cart on 13 October 2026. It remains
an unfabricated prototype with physical qualification pending. The user has
taken over checkout; payment and order confirmation have not been provided.

`snapshot-manifest.json` records all 40 copied files and the uploaded Gerber
SHA-256. Their original bytes are preserved. The local `.history` directory
was left in the working project; it is not promoted into the source archive.
Original Gerber, source and handoff ZIPs are retained under
`build/hardware/v4_1/purchase-snapshot-20261013/`.

The source BOM retains Royalohm 5.1 kΩ and TI TPS2553DBVR. TME order 35700057
instead buys Yageo RC0603FR-075K1L and Diodes AP22653W6-7 for the same lands.
Apply [the purchased assembly substitutions](../../../config/purchase/v4.1-assembly-substitutions.json)
when assembling; R32 remains 33 kΩ, 1%. Do not rewrite this snapshot to reflect
later procurement or routing changes.

Continue development in `hw/ledkiv4.1/`. Read
[the current state](../../../docs/current-state.md) and rerun the hardware
checks for actual circuit/geometry changes. Documentation updates do not
require replacing the already uploaded Gerber ZIP.
