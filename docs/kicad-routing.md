# KiCadRoutingTools in Letki

For another project, start with the global
[PCB workflow](../../.local/share/electronics/skills/pcb-workflow/SKILL.md) and
[tool assessment](../../.local/share/electronics/skills/pcb-workflow/references/assessment.md).
The portable helper takes explicit board/context/tool paths and project routing
parameters. This page retains Letki's specific integration and invariants.

[KiCadRoutingTools](https://github.com/drandyhaas/KiCadRoutingTools) is integrated
through its CLI. Codex calls the local scripts directly. This setup does not
install an MCP server or invoke another AI client. The pinned release is
`v0.23.0`, commit `9399bfb29e072bfe60b10d9cdae20c274fc2a17a`.

```sh
make pcb-tools       # first installation; public GitHub/PyPI downloads
make pcb-doctor
make pcb-check
make pcb-preview
```

Source and the verified Rust engine live in ignored `.tools/kicad-routing-tools/`.
The Python environment `.tools/kicad-routing-env/` uses system KiCad bindings,
with SciPy/Shapely installed locally. System Python, the speech environments
and KiCad's existing plugins are preserved. The source commit, release-asset
SHA-256 and Letki routing settings are in `config/kicad-routing.json`.
After an Arch Python upgrade, rebuild this environment against the new system
interpreter; preserve the pinned tool checkout.

Every operation creates a fresh working directory under
`build/hardware/kicad-routing/`, copying the PCB, schematic, project rules and
local libraries. Source hashes are checked afterward. Full logs, instrument
exit codes, tool pin and hashes are kept in `workflow.json`. The wrapper refuses
an existing output directory and never promotes a routed candidate.

`check` runs the upstream completeness instrument, official KiCad DRC with zone
refill and schematic parity, and Letki's geometry/power-feed checker. Any finding
returns a nonzero exit; read each log. The upstream checker supplements KiCad
and has its own geometry assumptions. Neither its `DONE` result nor a KiCad pass
qualifies electrical ratings, optics, soldering or manufacturing.

`render` writes front/rear panels and `review.png`. For placement arrows:

```sh
python3 scripts/kicad_routing.py render \
  --before archive/hw/ledkiv4-offset-wire-20261012/ledkiv4.kicad_pcb
```

For a narrowly scoped signal-routing experiment:

```sh
python3 scripts/kicad_routing.py route --nets /URX /UTX
```

Use `--board PATH` to work from an edited development copy, and `--work PATH`
to choose a new directory under `build/hardware/`. This profile targets Letki
v4. Exact net names are required; wildcards and power/ground nets are refused.
It requests 0.2 mm signals/clearance and 0.6/0.3 mm ordinary vias, keeps input
copper, and disables blocker rip-up and fabrication escalation. The wrapper
restores the authored project/rules/schematic before independent checks.
In1.Cu remains an obstacle/through-via layer, without new signal
tracks. The 2 mm front VCC bus and 1.2 mm rear power feeds require separate
review if deliberately changed. Route success still requires an independent
ERC, circuit/geometry and placement/net audit before source promotion.

The plugin GUI remains available upstream if later wanted. The CLI integration
is enough for the current Codex workflow; no home-directory plugin installer
was run.

For the TME v4.1 iteration, use `--revision v4.1` along with its PCB path.
An isolated placement trial may pass `--mechanics-config PATH` with reviewed
testpoint coordinates. The CLI signal profile still keeps In1 as an obstacle.
The new revision permits separately reviewed short manual In1 escapes where
terminals are enclosed by existing copper; inspect their length and the filled
ground/supply connectivity before promotion. This does not change routing floors
or the plugin's default profile.

Every new wrapper command records start time, elapsed wall time, return code and
arguments in `command-metrics.json`. `scripts/v4_1_routing_report.py` summarizes
actual v4.1 trials in CSV/HTML, keeping engine-reported scores/times distinct from
official DRC/open counts. Inputs differ across trials; these are development
records, not a controlled algorithm benchmark. Earlier runs lack command wall
time; do not infer it from the router's internal time or filesystem timestamps.

## First review, 2026-10-12

The tool found two same-net UART joints accepted by KiCad whose rounded ends
only overlapped. Their centre-lines were repaired in the symmetric v4 copy;
the upstream clearance/connectivity/size score then passed those joins. This
was a useful additional manufacturing review beyond the official rule check.

An isolated smoke test removed a real UART segment, confirmed an open net,
and let the router reconnect it. The result passed official DRC, connectivity,
schematic parity and native Letki geometry with the authored project restored
byte-for-byte. The fixture and candidate were kept under
`build/hardware/kicad-routing/`; that automatic route was not promoted.

Some supplementary reports still require interpretation:

- The routing experiment exposed an upstream mid-run project-floor rewrite
  even with `--no-fix-drc-settings`. The wrapper saves the upstream project as
  evidence, then reinstates the original settings before grading. A routed
  board is accepted only against the authored limits; a successful router
  report alone is insufficient.
- The parser models one size per pad, while the symmetric edge footprint has
  native front/inner round lands and a larger rear oval. Its reported narrow
  SDA joint on In2.Cu is against the rear oval's projection; that track actually
  ends at a via outside the round inner land. Native KiCad geometry is authoritative.
- The placement renderer aggregates seven disconnected contact courtyards into
  a single footprint envelope. Its LED/contact overlap advisories need comparison
  with the individual courtyard loops and official KiCad DRC.
- Copper redundant within existing pads/planes and same-net loops are reported
  by the supplementary copper checker. Do not automatically delete wide power
  feeds or plane reinforcement to satisfy its connectivity-only test.
- Impedance and length matching remain ungraded because this design has no
  specified controlled-impedance or matching requirement. The separate Letki
  checker verifies the deliberately wide VCC path geometrically.

Keep all supplementary findings visible. Do not weaken project severities or
add exclusions to turn an advisory instrument into a green release label.
