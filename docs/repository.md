# Repository layout and preservation

The 2026-10-18 cleanup records the accumulated development after historical Git
commit `c9ed745`. Source directories already follow the intended split, so their
paths were retained. The previous long root README is preserved in
[development history](development-history.md); the new root README and
[documentation index](README.md) provide current navigation.

## Versioned material

Keep application and vendor sources, tests, build/setup scripts, IDE source
metadata, KiCad projects/local libraries, FreeCAD source models, curated baseline
manifests, project configuration and development decisions in Git. Retain vendor
notices. Hardware baseline/configuration JSON and dated TXT records are source
context and must not be hidden by broad hardware ignore rules.

Retain historical snapshots in `archive/`; builds use `build/`. A source cleanup
does not modify board geometry, qualify hardware, order components, program a
board or regenerate an uploaded fabrication package. Existing source hashes and
readback records remain dated evidence, not a new physical validation claim.

## Local material and backups

The following stay outside Git:

- `build/`: executables, firmware images, readbacks, raw logs, media, local app
  drafts/libraries, experimental work and recovery tarballs.
- `.tools/` and `.local/`: downloaded tools, environments and old IDE/build state.
- CAD editor history, automatic backups, machine preferences and fabrication exports.
- `config/local.mk` and the seven shared-inventory links described in
  [configuration setup](../config/README.md).

A Git push backs up the versioned sources and documentation. It does not back up
these local datasets. Preserve readbacks, accepted manufacturing exports, local
media and the shared electronics inventory separately. A clone can build and run
simulated checks after installing dependencies; media playback and procurement
work additionally need their documented local inputs.

The isolated before-cleanup source snapshot and unchanged-CAD audit live in
`build/repo-cleanup/`. Historical deleted reference PDFs were not restored; the
retained WCH manuals are under `docs/reference/wch/`. The stray slicer
`result.json` was moved into that cleanup evidence directory.

## Working convention

Read `git status` before editing, preserve concurrent user changes, and stage a
reviewed set of source paths. Keep commits and dated milestone records distinct
from generated evidence. Do not force-push to overwrite unrelated work. “Last
system component” describes the planned media host's place in the architecture;
it does not mark the end of project development.


## Cleanup validation — 2026-10-18

`make doctor`, `make all-variants -j4`, `make test`, `make player-test`,
`make control-test` and the four preview-blackout tests passed. Service tests
used a private simulated broker with no physical UART. An isolated export of
the staged source also built the default firmware and passed `make test` without
local inventory links or pre-existing build artifacts (using the installed WCH
toolchain explicitly). All staged JSON parsed, new navigation links resolved,
and79pre-cleanup CAD/model hashes were unchanged. The staged-file audit found
no generated binaries, private-key/token patterns or external symlinks.

Logs and the local pre-cleanup snapshot remain in `build/repo-cleanup/`. These
checks validate the preserved software/source layout; they add no hardware,
optical or manufacturing qualification. No running music session, board firmware,
power setting or supplier order was changed by this cleanup.
