# Preserved project sources

These are superseded development snapshots, retained for history and recovery.
Use [current state](../docs/current-state.md) and the [active hardware index](../hw/README.md)
to choose a current baseline. Do not run old CAD creation/routing helpers against
reviewed active projects.

| Directory | Contents |
| --- | --- |
| `firmware/` | Original v2, v3-strip-test and v3-pwm-experiment sources and vendor notices |
| `hw/` | Earlier boards, mechanical sources, accepted dated baselines and supporting source/configuration records |
| `purchase/` | Superseded sourcing drafts; current decisions are in `config/purchase/` |

Historical firmware remains buildable through `make all-variants`. The original
`sw/` and `hw/ledki*` layouts have migrated here or into maintained source folders;
Git history retains the original locations. Generated images, editor history,
fabrication exports and raw evidence stay outside the source commit.
