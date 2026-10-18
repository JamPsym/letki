# Current prototype purchase records

The selected batch is five v4.1 boards with one USB head, hand assembled using
TME order 35700057 and stocked MCU/LEDs. Start with
[the current project state](../../docs/current-state.md).

| File | Use |
| --- | --- |
| `TME-35700057-ordered.csv` | Exact supplier symbols and quantities already ordered; do not import as a new order. |
| `v4.1-assembly-substitutions.json` | Purchased R30/R31 and U5 substitutions relative to the frozen CAD. |
| `JLCPCB-v4.1-cart.json` | Uploaded Gerber identity and the saved cart estimate; PCB checkout taken over by the user. |
| `current-state.json` | Current decision, inventory links and remaining work. |

Pending TME quantities are in `../parts-incoming.csv`, with source provenance
in `../orders/TME-35700057-source.json`. `../parts-stock.csv` retains the old
estimated LCSC shelf stock and four-v3 reservation. Supplier warehouse stock
and ordered quantities do not establish physical receipt.

Earlier Quick Buy drafts, LCSC quantities and wire/tool alternatives were moved
to [the dated purchase archive](../../archive/purchase/20261013-drafts/README.md).
Current order quantities take precedence over generated prototype worksheets.
