# Project configuration and external inventory

This directory contains reproducible board settings, music cue sheets,
requirements, device rules and selected purchase records. `local.mk` is an ignored
machine override; start from `local.mk.example`. Do not put credentials or supplier
session data in project configuration.

## Shared electronics inventory

Stock accounting is canonical in the user's shared electronics inventory, outside
this checkout. The existing local symlinks below are intentionally ignored by Git;
cleanup preserves them. They are not needed for firmware/software builds or host
tests. Procurement/BOM/package commands that read them need the shared dataset
connected first; absence must not be interpreted as zero stock or permission to
invent counts.

| Local path | Path beneath the shared inventory directory |
| --- | --- |
| `parts-stock.csv` | `parts-stock.csv` |
| `parts-stock-source.json` | `parts-stock-source.json` |
| `parts-incoming.csv` | `parts-incoming.csv` |
| `smd-storage.json` | `smd-storage.json` |
| `board-reservations.json` | `reservations/letki-incoming-20261017.json` |
| `orders/TME-35700057-source.json` | `orders/TME-35700057-source.json` |
| `orders/TME-35700057-backorders.csv` | `orders/TME-35700057-backorders.csv` |

On a new machine, restore the separately backed-up shared inventory, then create
local symlinks or provide explicit inventory arguments where the command supports
them. For example, from the repository root:

```sh
LETKI_INVENTORY_DIR=/path/to/shared/electronics/inventory
ln -s "$LETKI_INVENTORY_DIR/parts-stock.csv" config/parts-stock.csv
```

Repeat for the mappings above when the local path does not already exist. Keep
on-hand stock, incoming orders and the distinct board reservations separate.
Project-specific [purchase decisions](purchase/README.md) remain versioned here;
the shared ledger and original receipts need their own backup.

## Music recordings

`player/*.json` contains source URLs, local media paths, durations and recording
hashes. The audio/video files under `build/media/` are optional local inputs and
are not part of the Git checkout. The source-time arrangements remain reusable
when the matching local recordings are restored.
