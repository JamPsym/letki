# Purchase alternatives archived on 13 October 2026

These are historical drafts and source snapshots. The selected purchase is
TME order 35700057 for five v4.1 boards; current records are in
[`config/purchase`](../../../config/purchase/README.md).

The archive preserves 26 files formerly under `config/purchase`: v4.0 LCSC
lists for five/twenty boards, stock-oriented and minimum-quantity variants,
v4.1 TME drafts, cable alternatives, cost comparisons and the former decision
manifest. `snapshot-manifest.json` records their original paths and SHA-256s.
JSON paths inside historical records describe their original locations.

The LCSC twenty-board stock list included 50 TI row buffers, 30 TI UART
buffers, 10 TI USB limiters, 50 Nexperia decoders and 1,000 additional LEDs.
Its parts estimate was 89.01 USD; the minimum twenty-board draft was 40.58 USD,
before PCB, shipping and tax. The user deferred LCSC after seeing 20 USD
shipping and 20 USD tariff at checkout. These figures are dated evidence,
not current supplier quotes or placed LCSC orders.

`evidence/` retains supplier snapshots, the original design/bring-up notes,
parts/mechanics profiles, shelf stock, substitution research and JLCPCB cart
records. Fresh LCSC reads required Samsung C1591 in place of unavailable C14663
and TI DCUT/C2675813 in place of unavailable DCUR/C21404. Those substitutions
belong to the archived LCSC proposal, not the selected TME assembly.

Generated exports, preview screenshots, local tools and firmware readbacks
remain in their original ignored locations. Nothing was ordered or paid by
the agent. Use the actual TME receipt ledger for acquisition and receipt state.
