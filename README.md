# Letki modular LED display

Letki is a low-cost chain of 8×8 LED tiles with PWM brightness, programmable
text/graphics and synchronized music shows. The current physical baseline is
five v3 boards running the UART-programmable **general firmware R3**. The
independently developed v3.2 hardware and ESP8266/X035 attachment are the next
workstreams; their preparation and qualification status are recorded separately.

## Start here

- [Documentation index](docs/README.md): architecture, firmware, hardware and tests.
- [Current project state](docs/current-state.md): accepted revisions, orders,
  assembly substitutions and next work; later dated entries supersede older ones.
- [R3 milestone](docs/milestones/v3-general-r3-20261017.txt): verified five-board
  firmware, recovery references and physical validation limits.
- [Contributor instructions](AGENTS.md): working rules and hardware permissions.
- [Toolchain setup](docs/arch-setup.md): compiler and host dependencies.

## Desktop app and music

[Letki Studio](host/control/README.md) is a native GTK4/libadwaita application.
It provides text/font controls, brightness modulation, a five-tile pixel canvas,
presets, diagnostics and demos. The `letkid` service owns UART; Studio, the CLI
and other applications share its [local API](host/control/API.md).

```sh
make control-run
```

Drafts stay local until Apply. Applied RAM content runs independently of the GUI;
power cycling restores the saved flash show. Content uploads do not reflash the
application. Close picocom before connecting the service.

The [native C++ player](host/player/README.txt) uses the audio playback clock for
video and LED timing. Studio's Demo tab lists all [five music/video shows](docs/music-demos.md),
including the Laskowski × 2Pac mashup. Video plays on the PC beside the simulator.

```sh
make player
build/player/letki-player --show config/player/my-cyganie-full.json --simulate
make demos-prepare
```

`--simulate` forces PC-only playback. The direct player otherwise discovers a
WCH-Link UART adapter; release the broker's UART connection before using it.
`make demos-prepare` validates and renders local media offline without opening
UART or playing audio. Recordings are optional local data, not included in Git.

## Firmware and checks

The default build retains the original single-board text v3 application. Build
the current five-board general firmware with `make general-images`.

```sh
make doctor
make -j4
make general-images -j4
make test
make all-variants -j4
make player-test
make control-test
```

Builds never program a board. Physical tests and firmware writes follow the
identification, backup, readback and permission rules in [AGENTS.md](AGENTS.md).
Host register mocks and simulations do not establish electrical qualification.

## Layout

| Directory | Contents |
| --- | --- |
| `firmware/` | Maintained applications and separate diagnostic/demo variants |
| `host/` | Native Studio/service, music player and firmware renderers |
| `hw/` | Active KiCad projects, local libraries and mechanical sources |
| `config/` | Project settings, show cue sheets and selected purchase records |
| `scripts/` | Build/setup helpers, host controls and scoped CAD tools |
| `tests/` | Firmware register mocks and host/integration checks |
| `docs/` | Current decisions, architecture, validation and dated history |
| `archive/` | Superseded firmware, hardware and purchase drafts |
| `build/` | Ignored binaries, raw test evidence, media and working experiments |

See [hardware projects](hw/README.md) before opening a board. Existing v3 boards
require the documented C1–C3 ground repair. CAD and manufacturing exports have
their own qualification status; a successful software build is not a fabrication
release. Historical variants retain their notices and remain buildable.

## Development context and local data

The [attachment architecture](docs/attachments-study-20261017.txt) keeps tile
protocols independent of the host: ESP8266 → SPI → X035 → display. The media/TV
host is the **last planned system component**, with the spare N5095/M2S as a
candidate; development can continue after its integration.

Project decisions and source belong in Git. Generated binaries, recordings,
readbacks, caches, CAD editor state and fabrication exports remain local.
Shared electronics inventory is maintained outside this repository; see
[configuration setup](config/README.md) before using procurement generators.
These local datasets and raw evidence need their own backup.

The earlier root README is preserved in [development history](docs/development-history.md).
