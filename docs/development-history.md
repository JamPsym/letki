# Development history preserved during the 2026-10-18 repository cleanup

This is the previous root README, retained as a dated development record.
Use [the project overview](../README.md), [documentation index](README.md) and
[current state](current-state.md) for navigation and current decisions. Historical
status paragraphs describe their recorded date and may have been superseded.
Commands below are still run from the repository root.

---

# Letki modular LED display

The verified five-board v3 chain runs the UART-programmable general firmware R3,
with RAM/flash shows, PWM, queued frames and synchronized PC audio.
The [R3 milestone](../docs/milestones/v3-general-r3-20261017.txt) records the tested
baseline, recovery snapshot, launch commands and limits. Boards use the CH32V003
and 74HC138. The archived v3 hardware requires the documented C1–C3 ground repair;
see [hardware notes](../archive/hw/ledkiv3/README.md). Older firmware/CAD are preserved.

Start with [the current project state](../docs/current-state.md) for the selected
v4.1 prototype batch, placed TME order, saved JLCPCB cart, assembly substitutions
and next physical checks. Default builds remain the original text v3; build the
current chain with `make general-images`. Earlier dated sections below retain
historical test states; the R3 milestone is the current five-board baseline.

The [native C++ music engine](../host/player/README.txt) plays local recordings with
audio-clock-driven PWM, five-tile simulation, text introductions and timed cues.
Build with `make player`; run
`build/player/letki-player --show config/player/my-cyganie-full.json`
for the rebuilt My Cyganie / Don Vasyl show: butterfly-like pairs,
opposing claps, skirts, flowers and woven patterns, with music-driven PWM and source-time beat clocks. [All five full demos](../docs/music-demos.md)
include Tubular Bells instrument theatre, Adagio, L’Amour Toujours and the theatrical Laskowski × 2Pac mashup. Add `--port /dev/ttyACM0` for the physical
chain; without it the WCH-Link chain is detected automatically. `--simulate`
forces PC-only playback, and an absent adapter falls back to simulation. Content streams over UART without
flashing the boards. `make player-test` checks the native driver and audio core.
Video presets show the normal movie on the PC above the simulator; video never
affects LED pixels. `make demos-prepare` silently checks and renders complete
previews without opening audio playback or the physical display. Replay all six original
PWM scenes with `config/player/original-pwm.json`.

The [Letki Studio app and display service](../host/control/README.md) provide text,
fonts/PWM, a five-tile pixel canvas, presets, diagnostics and a Demo tab with
the original six PWM scenes plus the five music/video shows. Studio uses native
GTK4/libadwaita; the small `letkid` service owns UART and exposes a private
[local API](../host/control/API.md) for other applications and `letkictl`.
Launch with `make control-run`; edits stay local until applied. RAM programs run
independently of the GUI, with no Qt, Python runtime or firmware update required.

## V3.1 rework

The current [v3.1 PCB](../hw/ledkiv3.1/README.md) now has completed routing around the human placement, with checked power
feeds and GND stitching. Native ERC/DRC/open nets/parity are zero. Agreed LEDs, contacts
and mechanics are preserved. Firmware and qualification documentation remain here.
See [handoff and research locations](../docs/v3_1-handoff.txt). Physical qualification
and the fabricator's via treatment remain unresolved; this is not an order release.

## Next hardware steps

USART to the PC passed on the identified v3 board using WCH-LinkE at nominal
3.3 V: 20 exact echoes at 115200 8N1 with zero receive errors or dropped replies
after serial initialization. The working text firmware was restored and verified.
Two-board v3 I2C remains a pending physical baseline. Start with
[the interface demo guide](../docs/interface-demo.md) for the recorded startup
procedure, evidence and limits. The original v3 boards need the C1–C3 GND jumper.

Two-board I2C firmware is prepared (2026-10-14): the controller image sends
counter/CRC transactions automatically once per second; the target image listens
at `0x32`. One WCH-LinkE can program them sequentially and stay on the controller.
The user confirms R11/R12 I2C pull-ups are absent on both boards; fit at least
one 4.7 kΩ pair before a physical test. Edge soldering is also pending.
The [Polish procedure](../docs/i2c-v3-test.md) assigns roles, describes display
indicators and records the remaining hardware steps. Prepared image snapshots,
hashes, host-test/build logs and a display preview are in `build/i2c-preparation/`.
Preparation did not flash either board or validate physical I2C.

The user's UART chain arrangement also has prepared firmware: build
`make VARIANT=v3-uart-chain -j4` and use the same image on every board.
PC TX goes to the leftmost RX; each board's right TX goes to the next left RX;
the rightmost TX returns to PC RX. This separate counter/CRC test requires no
master/slave role or I2C pull-ups. [Wiring and PC test](../docs/uart-chain.md).
Physical two-board UART remains pending; preparation does not flash.

V4 is a separate prototype candidate. Its manufacturing package, optional
vertical PicoBlade SWIO connection and removable printed optics/carrier are
documented in [the v4 project](../hw/ledkiv4/README.md). V3 interface results establish
a baseline; v4 still needs its own electrical, mechanical and optical qualification.
Its symmetric contacts now have seven holes between eight LED rows and identical
wire-staple spans; earlier v4 sources are saved in dated archives. The
[KiCadRoutingTools CLI workflow](../docs/kicad-routing.md) adds local checks,
previews and scoped routing experiments: `make pcb-doctor`, `make pcb-check`,
`make pcb-preview`. Routed candidates stay in ignored working copies.

[Next-revision TME research](../docs/tme-next-revision.md) retains the stocked
CH32V003 and orange LEDs and assesses sourcing the remaining parts only from
TME. It is a preliminary sourcing/architecture study; it does not change v4 CAD.

The new TME iteration is [v4.1](../hw/ledkiv4.1/README.md), with reviewed routing
and a repeatable prototype purchase-package exporter. It preserves the stocked MCU/LEDs, symmetric wire
contacts and PWM pin map. Prototype convenience and electrical margin now take
priority over the cheapest individual parts, with costs recorded; larger batches
may use LCSC. The previous v4 sources are retained and additionally snapshotted
in `archive/hw/ledkiv4-pre-tme-20261012/`. See [the v4.1 brief](../docs/v4_1-design.md)
for exact parts, checks, TME quantities and the updated four-v3-board reservation.

The reusable [PCB workflow and tool assessment](../../.local/share/electronics/skills/pcb-workflow/SKILL.md)
and [shelf inventory workflow](../../.local/share/electronics/skills/shelf-inventory/SKILL.md)
are shared globally for other projects. Their index is
[the shared electronics workspace](../../.local/share/electronics/README.md).
Letki's board-specific design, checks and routing commands remain in this project.

Component inventory separates estimated shelf stock in `config/parts-stock.csv`
from placed orders in `config/parts-incoming.csv`. TME order 35700057 has all
20 lines awaiting delivery; its export reports warehouse availability, not
physical receipt. Record received quantities in `on_hand_confirmed` after
counting them. Order provenance is in `config/orders/`; actual ordered quantities
and purchased substitutions are in [the current purchase records](../config/purchase/README.md).
Earlier buying drafts are in `archive/purchase/20261013-drafts/`. Native CAD
for the saved JLCPCB cart is frozen in `archive/hw/ledkiv4.1-purchase-20261013/`.
The stock, incoming, storage and order-provenance paths now link to the shared
canonical inventory. After recording second-v3 consumption on 2026-10-14,
the v3 reservation covers three unassembled boards and missing parts on the two
assembled boards. Consumption and reservation release were recorded together.
A separate
shared planning record exposes the selected v4.1 batch's five MCU / 320 LEDs
to other projects without claiming that assembly has consumed them.

## Active project

Cost minimization is a primary design requirement. The CH32V003, inexpensive supporting chips and solderable board-edge connections are deliberate choices. The compact four-layer PCB is also deliberate: the user selected it for JLCPCB's favourable pricing at this size. Compare total parts, PCB, fabrication options and assembly cost before changing these choices; fewer layers or more integrated parts are not automatically cheaper. Production readiness must resolve electrical and manufacturing issues while preserving this cost intent.

| Path | Contents |
| --- | --- |
| `firmware/v3/` | Active firmware, WCH SDK, startup, linker script and MounRiver project |
| `firmware/interface-demo/` | Separate prepared UART and two-board I²C demos, with their own WCH SDK |
| `firmware/v3/User/main.c` | Sample message and `SCROLL_STEP_MS` animation speed |
| `firmware/v3/User/display.c` | V3 pin mapping, column scan and double buffering |
| `firmware/v3/User/font.c` | Existing uppercase and Polish glyphs |
| `firmware/v3/User/text.c` | Scrolling frame generation |
| `firmware/v3/User/swio.c` | Nonblocking logs and live controls through the debug probe |
| `firmware/v3/User/uart.c`, `uart_line.c` | USART receive queue, nonblocking output and bounded UTF-8 command lines |
| `firmware/v3/User/message.c` | Bounded UTF-8 custom messages and Polish uppercase conversion |
| `firmware/v3/User/frame_input.c` | Live frames sent by host demos |
| `firmware/v3/User/font_compact.c` | Compact Polish font used by the host renderer |
| `archive/hw/ledkiv3/` | Archived v3 KiCad board, FreeCAD diffuser and ground-jumper notes |
| `hw/ledkiv3.1/` | Single shared v3.1 schematic/PCB; current placement complete and synchronized, routing pending |
| `archive/hw/ledkiv3.1-ground-repair-20261014/` | Former ground-repair-only v3.1, preserved as a reference; will not be produced |
| `hw/ledkiv4/` | V4 candidate under development: low-cost orange LEDs, buffered drive; fully routed candidate; production validation pending |
| `hw/ledkiv4.1/` | New TME prototype iteration; native KiCad sources and repeatable purchase-package exporter |
| `hw/ledkiv3-ground-demo/` | Working copy demonstrating the C1/C3 ground repair through live KiCad IPC; not a fabrication release |
| `archive/` | Earlier boards, v2 text firmware, PWM experiment and verified strip test |
| `tests/` | Host tests for scrolling, Unicode, GPIO sequencing and frame changes |
| `scripts/`, `config/` | Toolchain, editor, preview and local configuration |

`build/`, `.tools/` and `.local/` are ignored local artifacts. `build/board-readback/` contains the original flash backup and the verified 100 ms strip-test readback. `.local/` retains old Windows builds, IDE state and CAD backups.

## Build and preview

For a native Wayland test window and direct agent controls, use
`make renderer-run BOARDS=5`. The C renderer shares firmware geometry, supports
configurable strips (keyboard presets 1–5), reads/writes test state through a
local socket and exports PNGs. `make renderer-test` runs deterministic integration
checks. See [the native renderer guide](../host/renderer/README.md).

Second-v3 assembly check (2026-10-14): `make VARIANT=v3-scan-demo` builds the
separate [row/column/pixel scan](../firmware/scan-demo/README.md). It was flashed
and all 5,228 bytes readback verified on UUID `d7-6e-ab-cd-41-3a-bd-ff`, after
two matching full-flash backups. Explicitly authorized PD7 GPIO configuration
changed USER from 0x17 to 0x1f with its inverse byte; all other option bytes
were preserved and verified. Live SWIO startup, pause/resume and all three
phases passed. After assembly corrections, the user confirmed all LEDs and
the complete display work. The previously reported dead column is resolved;
the precise repair was not recorded. Evidence is in
`build/board-readback/second-v3-scan-20261013T220549Z/` (UTC timestamp;
local date 2026-10-14). Tests and all variants build successfully; no CAD or
programmer power controls changed. The last agent-verified image on the second
board is the scan demo; instructions for flashing the wave demo were subsequently
provided, without a verified follow-up flash. Next: solder board-edge connections,
check continuity/shorts and prepare the still-pending two-board I2C test.

Run from the repo root:

```sh
make doctor
make -j4
make test
make compdb
clangd --check=firmware/v3/User/main.c --tweaks=
python3 scripts/preview_text.py
```

`make` now builds v3 by default. Outputs are `build/v3/letki.elf`, `.hex`, `.bin` and `.map`. The preview script uses the firmware's actual font and frame renderer to generate `build/preview/text-scroll.gif` and `message.png`; it needs Pillow (`python-pillow` on Arch). GIF frame durations are rounded to the format's 10 ms resolution.

Change the wide string in `User/main.c` to edit the sample. Leading and trailing spaces separate repetitions. `SCROLL_STEP_MS` defaults to 75 ms per pixel. Normal glyph cells are eight columns wide and spaces two columns wide; unsupported characters are blank.

The display scans a column every 500 µs (250 Hz full frames), independently of scrolling, with nominal 10 kHz hardware PWM on all eight row pins. Frames and global brightness changes switch at a complete scan boundary. Rows become driven-low GPIOs during a 100 µs column blank; only lit rows return to timer output afterward. This removed the previous-row ghost pixels reported during PWM testing. USART, SWIO, I2C and button pins are preserved. The unfinished old PWM experiment remains archived.

Current measurement follow-up (2026-10-14): the separate design session's
`v3-current-demo` was flashed on the second v3 (`d7-6e-ab-cd-41-3a-bd-ff`).
All 5,240 image bytes matched readback after two matching 16 KiB backups;
option bytes and programmer power settings were preserved. Host tests and live
SWIO startup/status/blank/restore passed. The board now selects the bottom-left
R1/S1 pixel at brightness 100 with nominal 10% scan duty. Current, supply and
waveform measurements remain pending. This supersedes the scan demo as the
last verified image on that board. Evidence: `build/board-readback/current-demo-20261014/`.

## Board mapping

The strip test called the decoder outputs rows. In the actual v3 layout, S1–S8 run left to right and select cathode columns; D8–D1 run top to bottom and drive anode rows.

| Signal | GPIO |
| --- | --- |
| Decoder A0, A1, A2 | PC7, PC6, PC5 |
| Rows top to bottom, D8–D1 | PD7, PC0, PD3, PD4, PC4, PC3, PA1, PD2 |
| SWIO | PD1 |
| USART TX / RX | PD5 / PD6 |

Orientation follows the front of the KiCad layout. Confirm orientation and scrolling on the physical board during the first text firmware test.

## Hardware status

The connected WCH-LinkE runs firmware 2.16 and successfully identifies the CH32V003 with 16 KiB flash and read protection disabled. Flashing and readback verification were tested with the 100 ms strip test, and the user confirmed its faster line cycling. The user confirmed the text animation works. The subsequent SWIO firmware was flashed and all 5,068 image bytes matched readback. Logs and live speed, pause, resume and reset commands were verified through the WCH-LinkE. The custom-text update was subsequently flashed and its 6,712 image bytes matched readback. Polish text replacement and overlength rejection were verified through the UTF-8 terminal. The terminal was closed with the original sample scrolling at 75 ms per pixel.

The pre-PWM USART/text/live-frame image used 13,764 bytes of flash sections and 1,744 bytes of RAM sections, including the reserved 256-byte stack. It was flashed on UUID `d7-73-ab-cd-41-3f-bd-ff` and all image bytes matched readback. Working flash was preserved with two matching full readbacks first. Live USART tests covered Polish text, speed, pause/resume, arm, frames, invalid input and 20 exact echoes during fast scrolling of a 64-character message, with zero receive errors and dropped replies. SWIO controls and the UTF-8 PC helper also passed. The board was left running the original sample at 75 ms per pixel. V4 CAD is unchanged. See [Arch setup](../docs/arch-setup.md) for the explicit flashing command and USB setup.

## USART text controls

The active text firmware now accepts **115200 baud, 8N1, no flow control** over USART, alongside SWIO. Connect adapter TX to board URX/PD6 (J3 pin 5), adapter RX to UTX/PD5 (J1 pin 5), and common GND. Use compatible logic levels; the tested WCH-LinkE already supplies this board through its 3V3 pin. Leave the existing power arrangement unchanged and do not connect an additional supply. Actual rail voltage was not measured; see [the physical interface record](../docs/interface-demo.md).

```sh
python3 scripts/uart_text.py --list
PORT=/dev/serial/by-id/usb-wch.cn_WCH-Link_02858F0687B7-if01
python3 scripts/uart_text.py --port "$PORT" --command 't zażółć gęślą jaźń'
python3 scripts/uart_text.py --port "$PORT" --command 'v 75' --command status
python3 scripts/uart_text.py --port "$PORT" --check
```

USART accepts complete lines after Enter (LF or CRLF). All active-firmware output uses CRLF (`\r\n`), including status, help, acknowledgements, errors and ping replies. PC readers also tolerate the older LF and LFCR reports; the TUI sender accepts either CRLF or LFCR command suffixes. Use `t TEXT` for UTF-8 text, `v MS` for speed, `b PERCENT` for brightness, `f` plus 16 hex digits for a frame, and the existing single-letter controls below. `status` and `help` alias `s` and `h`; `ping TOKEN` returns an exact `PONG TOKEN` and is USART-only. Ordinary unprefixed text is rejected, so its letters cannot pause or arm the scroll. The text limit is 64 characters; the line buffer permits a two-byte prefix and 256 UTF-8 payload bytes. Esc cancels an unsent USART draft; Backspace removes its last character. Invalid UTF-8, overlong lines and receive errors reject input without applying it.

USART drafts are separate from SWIO input. Display-changing USART commands return `ERR busy` during a pending SWIO text/speed/brightness/frame edit; finish or cancel that edit first. USART `status`, `help` and `ping` remain available. Replies and status logs go to both interfaces; neither waits for a connected host. Status retains speed/pause/uptime and adds `uart_errors` and `tx_dropped`. It does not read back the current message or framebuffer. Changes remain volatile.

Only the short receive ISR publishes bytes and error flags into a fixed 64-entry queue. Parsing, logging and transmit polling run in the foreground; PWM scanning remains independent of command handling, with paired display buffers. The 128-byte transmit queue drops whole replies if full. Send one command and wait for its response before sending the next. First-open WCH-LinkE startup errors were observed in the earlier demo; the successful preparation sequence in [the interface guide](../docs/interface-demo.md#physical-usart-to-pc-run-2026-10-12) remains documented. Errors are reported and not silently cleared.

Local programming and live-test evidence is preserved in `build/board-readback/text-usart-20261011T230140Z/`. The final image SHA-256 is `b19b8063a8d33eeba805c865a7e29550899c294fae08580fd5ca27ef6473ea34`. Keep USART and SWIO sessions closed before probe operations. The separate `uart_demo.py` targets interface-demo firmware; use `uart_text.py` for this active text application.

## SWIO logs and live controls

For a full-screen Vim-style controller, run `make tui` over SWIO or `make tui PORT=/dev/ttyACM2` over USART. The same Text, Pixels and Logs tabs work with either transport. You can also use `python3 scripts/letki_tui.py --tty /dev/ttyACM2`. Close other apps using the chosen serial port first. `make tui-demo` previews it without hardware. See the [TUI guide](../docs/tui.md) for bindings and state-reporting limits.

The existing probe connection carries bidirectional messages while the display refreshes. No UART cable is needed. From the repo root:

```sh
python3 scripts/swio_terminal.py
```

The wrapper builds a local minichlink variant with unsigned character handling, so Polish UTF-8 bytes are packed correctly; downloaded tool sources remain unchanged. It shows a visible `> ` input line and retains submitted commands in the output. Backspace edits locally; Esc or Ctrl+U clears the draft. **Press Enter to send every command**, including single-character commands. Opening this terminal restarts the board. It prints a startup message and status every five seconds. Commands:

With the text firmware, ordinary text such as `zobacz adasiu już nie świeci` is automatically sent as `t TEXT`. Explicit controls below remain commands. The wrapper reports when the display is paused or armed; enter `r` to resume. The raw firmware protocol still requires `t`: unprefixed text sent through another tool can execute embedded letters as commands (`a` arms and holds at the first frame).

| Key | Action |
| --- | --- |
| `h` or `?` | Show help |
| `s` | Show speed, paused state and uptime |
| `t YOUR TEXT` then Enter | Replace the scrolling message with up to 64 characters |
| `+` | Faster scrolling, reduce the interval by 5 ms, minimum 10 ms |
| `-` | Slower scrolling, increase the interval by 5 ms, maximum 500 ms |
| `p` / `r` | Pause / resume scrolling; LED refresh continues |
| `0` | Restore 75 ms scrolling, 100% brightness and resume |
| `v 75` then Enter | Set an exact 10–500 ms scroll interval |
| `b 25` then Enter | Set global brightness to 0–100%; 0 blanks the LEDs |
| `a` | Hold the current message at its start for a timed cue |

Custom text accepts UTF-8, converts lowercase Latin and Polish letters to uppercase, and adds blank spacing between repetitions. The font supports A–Z, ĄĆĘŁŃÓŚŹŻ and spaces; other valid characters render blank. `t` then Enter clears the display. Backspace removes a character; Esc cancels editing. Invalid UTF-8 or overlong input leaves the previous message intact. Applying a message restarts its scroll and resumes animation while retaining the speed.

For example, type `t zobacz adaś działa` and press Enter. Wait for `OK text updated`. The previous message keeps running until Enter. Changes are temporary and reset when the MCU restarts. Ctrl+C closes the terminal. It owns the programmer while open; close it before flashing or using another debugger.

The firmware uses the [minichlink terminal packet format](https://github.com/cnlohr/ch32fun/blob/master/minichlink/minichlink.c) over debug DATA0/1, rather than the vendor SDK's SDI printf format. Keep this transport in the foreground: it has a fixed 128-byte TX queue and never waits for the host. Logs and replies are best effort; a full queue drops whole messages. Send commands individually if you need every reply. Scrolling and refresh keep running when the terminal disconnects.

## Local speech demo

[Polish TTS demo setup](../docs/tts-demo.md) covers the current native-rate voice environment, SWIO frames and selected synchronization points. The active short demo uses Supertonic 3 with native slow speech and a continuous compact-font caption. Run `.tools/native-tts/bin/python scripts/tts_native.py` and edit `config/native-demo.json`. Audio can wait at selected words while fixed-speed captions catch up. Earlier GPU, word-scene and waveform-stretching experiments remain available for comparison.

## Archived projects

See [archive/README.md](../archive/README.md). Archived firmware still builds:

```sh
make VARIANT=v2 -j4
make VARIANT=v3-strip-test -j4
make VARIANT=v3-pwm-experiment -j4
make all-variants -j4
```

Archived outputs go to `build/archive/<variant>/`. Application and CAD source files were preserved during archiving, including the verified strip test's 100 ms setting. The existing modified v3 diffuser is preserved in the archived v3 hardware project. Deleted reference PDFs remain in Git history.

For future agent work, read [AGENTS.md](../AGENTS.md).

## Prepared interface tests

The [interface demo guide](../docs/interface-demo.md) covers PC ↔ USART and controller ↔ target I²C on two boards. Run `make interface-demos -j4` to build all three roles. `python3 scripts/uart_demo.py --list` lists serial adapters. Firmware builds, host protocol tests and simulated peripheral checks pass. Physical USART passed on the existing v3 with the documented serial initialization; two-board I²C is pending. The working text/TTS firmware remains the default and was restored after the UART test.


## PWM experiment and active brightness

On 2026-10-12 the v3 row nets were checked against WCH's default timer mappings:
D8–D5 use TIM2 CH4–CH1; D4–D1 use TIM1 CH4–CH1. PD1 remains SWIO; its
complementary timer output is disabled. The existing USER byte already makes
PD7 a GPIO rather than NRST. No option-byte or programmer-power changes were made.

The separate sparse experiment is `firmware/pwm-demo/User/`, sharing v3's SDK,
startup and linker script without altering the historical PWM archive:

```sh
make VARIANT=v3-pwm-demo -j4
python3 scripts/pwm_demo.py --port /dev/ttyACM2 --check --walk
```

Selecting/flashing that experiment is separate from building. It supports
`d 0..100`, `fade`, `rows`, `row 1..8`, `diag`, `samples`, `scan 1000/2000`
and `blank 0/1`, each followed by Enter. The row sweep exercises all 64 LEDs
with at most one LED per selected column. On-chip digital-pad samples matched
0/25/50/75/100% timer phases on all eight outputs; exact USART echoes passed.
The user confirmed ghost pixels disappeared after GPIO-low blanking. These
observations do not replace external frequency/current measurements or a
recorded per-pixel optical inspection.

The active text firmware now supports `b 0..100` over SWIO/USART. A value is
applied only after Enter; invalid, incomplete or cancelled input preserves
brightness. Status adds `brightness_pct`; settings are volatile. Brightness 0
keeps scanning, animation and commands running with the LEDs dark. `0` restores
100% brightness and the original speed/mode. In the TUI, `b` edits brightness
and `:brightness 25` applies an exact value. Percentage uses gamma 2.2 mapping to PWM duty within
the active window; the 100 µs blank interval remains at every column transition.

Working readbacks and raw PWM/brightness results are in
`build/board-readback/pwm-20261012T111419Z/`. The initial brightness build used 15,556 flash
bytes and 1,764 RAM bytes including the unchanged 256-byte stack; the conservative
foreground plus all three ISR paths sum to 224 bytes. Runtime stack high-water
and absolute PWM frequency remain unmeasured. The former text/USART firmware
and each experimental image's verified readback are retained.

The [WCH reference manual v1.9](../docs/reference/wch/CH32V003RM.PDF) and
[datasheet v1.3](../docs/reference/wch/CH32V003DS0.PDF) are preserved vendor copies
recovered from this repository's history. The attempted direct download did not
return PDFs; these copies are not claimed to be the latest manufacturer revision.


## Gamma brightness

`b 0..100` is a perceptual brightness setting, mapped through a gamma 2.2
lookup table. For example, 25/50/75% settings give approximately 4.75/21.75/53.08%
PWM duty during the lit interval. Status and the TUI continue to show the
requested percentage. Zero is fully off; 100 is full duty. Nonzero settings
have at least one timer tick, so the lowest few settings share a level.

The active driver uses 1,200 PWM steps with a nominal 12 MHz counter, retaining
the 10 kHz PWM, 100 µs GPIO-low column blank and 250 Hz frame scan. The 202-byte
lookup table stays in flash; no floating-point work runs on the MCU. The sparse
PWM experiment remains linear for diagnostic duty-cycle checks.

Gamma build verification (2026-10-12): `make -j4` and `make test` passed.
Host tests check all 101 settings against the curve on all eight timer channels,
including endpoints, monotonicity and latching at the full-scan boundary.
The identified v3 was backed up twice, flashed and readback verified (15,792
image bytes; RAM sections remain 1,764 bytes including stack). Live USART
brightness settings 0/1/5/10/25/50/75/100 and 20 exact pings passed with zero
errors/drops; the board was restored to the original text, 75 ms/pixel, 100%.
Evidence: `build/board-readback/gamma-20261012T125521Z/summary.json`.
Optical uniformity and the increased-resolution PWM waveform were not measured.


## Standalone 8×8 visual demo

The separate [radial-wave application](../firmware/visual-demo/README.md) runs
independently on v3, with gamma-corrected per-pixel PWM. Build it with
`make VARIANT=v3-visual-demo`; the default `make` still builds the text firmware.
`b PERCENT`, `v MS`, pause/resume and reset work over SWIO or UART.
Use `python3 scripts/preview_wave.py` for the offline animated preview.

### Latest v3 current-test state (2026-10-14)

The second v3 now runs the isolated full-S1-column current test: eight pixels,
brightness 100, nominal 10% pixel duty. All 5,428 image bytes matched readback
after two matching backups; option bytes were preserved. Host command checks
and SWIO startup/status/blank/restore passed. This supersedes the single-pixel
image as its latest verified state. Current/rail readings for this load are
pending; electrical qualification is not established. Evidence:
`build/board-readback/current-column-20261014/summary.json`.

Full-column measurements completed: user reports 20 mV across each R1-R8
at 3.309 V supply. For nominal 51 ohm and 10% scan duty, total estimates
are 3.14 mA average and 31.4 mA during pulses; waveform remains unmeasured.
Display subsequently blanked via acknowledged SWIO 0. Reset re-enables the
full-column default. See the user-current-measurement.json in the evidence
directory above; these readings do not qualify the original decoder load.

## Physical two-board UART-chain result (2026-10-14)

Both assembled v3 boards passed the complete PC TX -> left RX -> left TX ->
right RX -> right TX -> PC RX chain using the same 10136-byte image.
Left UUID: `d7-73-ab-cd-41-3f-bd-ff`; right UUID: `d7-6e-ab-cd-41-3a-bd-ff`.
Each board had two matching 16 KiB backups and complete image readback
verification; option bytes and programmer power settings were preserved.
User confirmed existing WCH-LinkE 3V3/GND power through the soldered bridge
and the LinkE TX/RX connection. The host serial device is
`/dev/serial/by-id/usb-wch.cn_WCH-Link_02858F0687B7-if01` (`/dev/ttyACM0`).

At configured 115200 8N1, all 20 distinct checked requests returned with two
hops, matching random tokens/counters and valid CRCs. Every accumulated
diagnostic count was zero. Right SWIO, held open during UART traffic, confirmed
`CHAIN position=2 counter=46665 ok=20 bad=0 drop=0 uart=0 txdrop=0`.
The original pre-initialization host tty settings were restored and verified.
Both boards retain UART-chain firmware; last accepted counter is 46665.
Matrix appearance was not independently inspected. Actual rail/baud/waveforms
and runtime stack high-water were not measured in this run. This confirms
physical two-board UART transport; two-board I2C remains untested, and it does
not qualify v4 buffers or resolve the measured v3 decoder-loading limitation.

Evidence: `build/board-readback/uart-chain-20261014/live-result.json`,
`uart-traffic.log`, `right/swio-live-test.log`, both board summaries/backups
and readbacks. Image SHA256:
`4b805c9b432766bb231e833b73fc7d17c398d1f9079c053c73f776992821f547`.

## Physical two-board I2C result (2026-10-14)

The existing two assembled v3 boards passed 20 consecutive physical I2C
exchanges with matching requested counters and `reason=reply CRC`, configured
for 100 kHz. Left/original UUID `d7-73-ab-cd-41-3f-bd-ff` is controller
(12412-byte image); right/second UUID `d7-6e-ab-cd-41-3a-bd-ff` is target
at 7-bit address 0x32 (12396-byte image). Both images matched readback after
two matching full-flash backups per board; all option bytes preserved and
no programmer power commands. User confirmed existing WCH-LinkE 3V3/GND
power through the soldered edge bridge and one nominal 4.7k R11/R12 pair
fitted on the left board. UART TX/RX wires remained connected but commands
and acceptance evidence used SWIO; no host serial port was opened in this run.

Controller final checked status: ok=20, fail=0, counter=46665, uart_errors=0,
tx_dropped=0, auto=0. Then `auto on` was acknowledged; the controller now
increments from 46666 once per second. Right target startup/status previously
verified clean; its final UART/drop diagnostics were not separately read.
Visual counter agreement, actual frequency/waveforms/rail/current and runtime
stack remain unmeasured in this run. This establishes v3 physical I2C packet
transport, not v4/v4.1 logic/power/buffer or production qualification.

Evidence: `build/board-readback/i2c-two-v3-20261014/live-result.json`,
`controller-swio.log`, `commands.json`, setup/source hashes and each board's
identity/backups/readback/options/summary. Final firmware remains I2C controller
and target, with automatic counting on. This supersedes older pending-I2C
status paragraphs. No CAD or purchases changed during this test.

## Two-board ping-pong demo (2026-10-14)

User wanted a visual indication of board communication. Separate
`firmware/pingpong-demo/` forms one 16x8 bouncing-ball scene. Left advances
a phase only after matching I2C reply CRC; right renders received phases only.
Corner indicators derive from successful exchanges; failures or 1.5s without
valid transport freeze the last ball and light the corner steadily. Pause
continues communicated held phases. Uses unchanged active binary/PWM display
driver and shared interface-demo I2C/protocol sources; no UART initialization.
Build: `make pingpong-demos -j4`; default v3 text unchanged. Preview:
`build/preview/pingpong.gif`; host tests, all variants and clangd passed.
Left/right images are 10988/10448 bytes; RAM including 256-byte stack is
672/664 bytes; conservative foreground+both ISR stack sum 240 bytes, runtime
high-water unmeasured. Evidence: `build/pingpong-validation.json`.

Left/original board was flashed/readback verified after two matching backups
and unchanged option bytes/power. It passed 20 consecutive CRC-confirmed phase
updates against the existing right interface-demo target, plus pause (continued
exchanges with held phase) and resume. Last checked status:
`PONG role=left phase=21 ok=24 bad=0 link=1 paused=0 ms=100`.
Right/second board was then identified, flashed and readback verified after
two matching full backups; option bytes and programmer power were preserved.
With both final demo images running, right received 32 consecutive CRC-validated
phases, covering a full horizontal round trip, with zero receiver failures:
`PONG role=right phase=151 ok=32 bad=0 link=1 paused=0 ms=100`.
Both boards are left running at 100 ms/step. Optical seam quality, physical
link-loss behaviour and runtime stack high-water remain unmeasured. Evidence:
`build/board-readback/pingpong-20261014/left-live-result.json`,
`right-live-result.json` and each board's `summary.json`.


## Two-board standard text candidate

`make strip-text-images` prepares separate left/right images with compact Polish
text **LETKI DZIAŁA**, bounce by default, continuous scrolling as an alternative,
and standard UART text/speed/brightness/pause/status/ping controls. I2C carries
the right tile's pixels; its UART forwards replies to the PC.
`make renderer-text` demonstrates the shared firmware logic in the native
Wayland window before programming. [Candidate guide](../firmware/strip-text/README.md).
Frozen images/hashes are in `build/strip-text-prepared/`; both fit the CH32V003.
They have not been flashed; physical boards still run the verified ping-pong demo.


## Standard text right receiver flashed (2026-10-14)

At the user's explicit request, right UUID d7-6e-ab-cd-41-3a-bd-ff was
programmed with the frozen 6652-byte standard text receiver. All bytes matched
readback, two full 16KiB backups matched, option bytes were unchanged and no
programmer power commands were issued. SWIO verified the correct receiver
startup and status: seq=0 ok=0 fail=0 link=0 uart_errors=0 tx_dropped=0.
This is receiver startup validation, not a passed two-image transport test.
Left remains the prior ping-pong image; the right needs matching 14-byte frames
from the new head before it can display text. Old diagnostic requests may be
rejected. Evidence: build/board-readback/strip-text-20261014/right/summary.json,
right/swio-live.log and right-live-result.json. Prepared manifest is now
RIGHT_FLASHED_LEFT_PENDING. Next is moving only SWIO to the left for the
matching head image; existing power/GND and UART/I2C wiring stay in place.


## Standard text pair programmed and tested (2026-10-14)

Left/original d7-73-ab-cd-41-3f-bd-ff was identified and flashed with the frozen
12320-byte standard text head. All bytes matched readback after two matching
full 16KiB backups; option bytes and programmer power were unchanged. Right
retains its previously verified 6652-byte receiver. Both now run standard text.

Physical UART passed 20 exact random-token replies through the right's transparent
relay, with zero head receive-error/drop counters under fast 10ms scrolling.
Mode changes, pause/resume, speed, brightness 25/100, Polish UTF-8, 64-character
input, rejected 65-character/invalid UTF-8/invalid speed/brightness, legacy eight-
column frames and full sixteen-column frames passed. The head's real RAM snapshot
showed 1839 successful new 14-byte I2C frame CRC acknowledgements and zero I2C
failures; scene and committed revisions matched. Read-only debug snapshots briefly
halted the head and then resumed it. A subsequent UART check confirmed uptime
advanced 610ms across a 600ms host wait, with zero UART errors/drops. This checks
software clock progress, not waveform timing or oscillator calibration.

The initial adapter opening missed the boot banner; the first subsequent status
was an invalid line, then status replied cleanly with hardware UART counters zero.
Failed startup logs were preserved; no reset/counter clearing was used to obtain
the passing full test. Host uart_text.py now recognizes mode/full-strip-frame
acknowledgements and both legacy/new help formats; live m scroll/m bounce/help/
status and seven host serial tests passed. Final state is LETKI DZIAŁA, bounce,
75ms/column, unpaused, brightness 100, host-frame mode off; SWIO remains on left.

Evidence: build/board-readback/strip-text-20261014/summary.json, per-board backups/
readbacks/options, pair-live-result.json, UART traffic/raw log, head counter/scene
snapshots and post-ram-clock.json. Prepared manifest is BOTH_FLASHED_PAIR_TESTED.
Right final cumulative diagnostics, optical rendering, rail/current/waveforms and
runtime stack high-water were not independently measured. No CAD/stock/purchases
changed. Earlier left-pending statements are superseded.


## Third v3 assembly test (2026-10-16)

Third-board UUID `d7-69-ab-cd-41-35-bd-ff` passed the separate scan demo
without USART connected. The user explicitly authorized flashing/testing this
board and a PD7 reset-to-GPIO option change. Two identical full 16 KiB flash
backups were saved first. All 5,228 scan-image bytes matched readback.
USER changed from 0x17 to 0x1f with its inverse byte; all other option bytes
were preserved and verified. No programmer power commands were issued.

Live SWIO startup, pause/status/help/resume and a complete row/column/pixel
cycle passed. The user confirmed all LEDs and patterns look correct.
The board remains running the automatic scan at brightness 100, unpaused.
Evidence and backups: `build/board-readback/third-v3-20261016/summary.json`
and adjacent files. Rail/current/waveform and runtime stack high-water were
not measured; USART and inter-board interfaces were not tested in this session.
No CAD or inventory changes were made; assembly consumption is not inferred
from the functional test.


## Fourth v3 assembly scan test (2026-10-16)

Fourth-board UUID `d7-50-ab-cd-41-1c-bd-ff` was identified and tested with
unchanged `v3-scan-demo`. Two matching full 16 KiB flash backups were saved.
The user separately authorized PD7 GPIO configuration for this board: USER
changed from 0x17 to 0x1f with its inverse byte; all other option bytes were
preserved and verified. All 5,228 programmed image bytes matched readback.
No programmer power commands or separate erase operations were issued.

SWIO startup, pause/status/help/resume and a complete row/column/64-pixel scan
cycle passed. `make test` passed. The board remains in automatic scan mode,
brightness 100, unpaused. The user confirmed all eight rows, eight columns and 64 individual pixels
look correct, without missing LEDs or ghosting. Rail/current/waveforms, runtime stack, USART and inter-board interfaces were
not measured/tested in this session. No CAD or inventory changes were made;
assembly consumption is not inferred from this test.

Evidence and backups: `build/board-readback/fourth-v3-20261016/summary.json`
and adjacent files. This identifies the fourth assembled board; the fifth
board and full five-board chain still need their own tests.


## Fifth v3 assembly scan test (2026-10-16)

Fifth-board UUID `d7-56-ab-cd-41-22-bd-ff` passed the unchanged v3 scan demo.
Two matching full 16 KiB flash backups were preserved before updates. The user
explicitly requested reset-pin reprogramming: PD7 was configured as GPIO
(USER 0x17 to 0x1f plus inverse), with all other option bytes preserved and
verified. All 5,228 programmed image bytes matched readback. No programmer
power commands or separate erase operations were issued.

SWIO startup, pause/status/help/resume and a complete row/column/64-pixel cycle
passed. The user confirmed all patterns look correct, without missing LEDs
or ghosting. The board remains running automatic scan, brightness 100,
unpaused. Evidence/backups: `build/board-readback/fifth-v3-20261016/summary.json`
and adjacent files. The unchanged image matches the third/fourth scan images;
`make test` passed earlier in this session.

The last two assemblies now have individual scan/readback/SWIO and user optical
checks recorded. The complete five-board chain remains untested. USART,
inter-board interfaces, rail/current/waveforms and runtime stack were not
measured in this test. No CAD or inventory changes; assembly consumption is
not inferred from functional validation.


## Falling text, brightness pulse and five-tile candidate (2026-10-16)

Prepared third text mode `m fall`: word-wrapped, centered lines moving from
above the top down through the bottom, using the existing compact Polish font.
`m fall` enables brightness modulation; `e off` makes it steady, `e pulse`
enables it in any mode. `b 0..100` remains the brightness ceiling. Pause holds
both movement and modulation. Gamma/PWM scanning remains in the existing driver.

`make strip-five-images -j4` builds a separate head and four receiver images
for 40x8 geometry, at addresses 0x32/0x33/0x34/0x35 from left to right after
the head. UART replies relay through all receivers. The head commits a scene
after all four CRC replies; receivers publish sequentially on arrival, without
synchronized scan clocks or batch rollback. Retain common SDA/SCL/GND, one
existing pull-up pair and the existing UART chain. Physical UUID-to-position
mapping must be established before flashing; assembly order is not assumed.

`make test`, all firmware variants, seven native renderer tests and clangd
main/scene checks passed. Five-head sections: 13,572 bytes flash, 1,952 bytes
RAM including the 256-byte stack. Foreground maximum 204 bytes plus retained
conservative ISR budget 48 gives 252 bytes; runtime high-water is unmeasured.
The original two-tile build commands remain available. Frozen previous images
and board readbacks remain intact. New binaries, hashes and evidence:
`build/strip-text-fall-prepared/manifest.json`.

Five-board preview: `build/strip-text-preview/fall.gif`. Launch with
`python3 scripts/demo_strip_text.py --boards 5 --mode fall --text 'LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM'`.
No hardware was flashed during preparation; five-board electrical/transport and
new optical effects still need physical testing after soldering. No CAD changes.


## Five-board head and live chain test (2026-10-16)

Leftmost head UUID `d7-50-ab-cd-41-1c-bd-ff` programmed with the frozen
13,572-byte five-tile head image. Two matching full 16 KiB backups saved;
all image bytes matched full-flash readback, all option bytes preserved,
no programmer power or separate erase commands. SWIO startup/status passed.
All five positions are now programmed, left to right:

1. Head: d7-50-ab-cd-41-1c-bd-ff.
2. Receiver 0x32: d7-56-ab-cd-41-22-bd-ff.
3. Receiver 0x33: d7-69-ab-cd-41-35-bd-ff.
4. Receiver 0x34: d7-73-ab-cd-41-3f-bd-ff.
5. Receiver 0x35: d7-6e-ab-cd-41-3a-bd-ff.

Physical USART returned 20 exact random tokens through all four transparent
receiver relays. Scroll/bounce/fall, pulse on/off, speed, pause/resume,
brightness, Polish text and 64-character bounds passed; invalid mode/effect,
brightness/speed and 65-character text were rejected. Initial adapter open
returned an invalid line and head uart_errors=2; subsequent first-run tests
added no UART errors/drops. Logs and counters were retained without clearing.

Head RAM snapshot showed 4,466 I2C CRC acknowledgements and zero failures,
committed falling mode at 100 ms, ceiling 70, pulse phase 19, actual driver 61
and PWM 404. The batch logic commits after all four receiver replies. This is
logical packet/scene evidence; receiver cumulative diagnostics and waveform/
rail/current/runtime stack were not independently measured.

A second RAM inspection found the head had restarted during the diagnostic
window (uptime 90,340 -> 661 ms and default bounce). Cause was not established.
The failed comparison and both snapshots were preserved; do not claim that
this probe session resumed without reset. Falling mode was restored via UART.
A separate serial-only run passed another 20 exact pings and the controls,
with zero head UART errors/drops during that run and uninterrupted uptime
progress across ten 0.5 s waits. No probe operations or counter resets occurred
in that final serial run. Its zero counters follow the observed restart and
do not supersede the initial UART startup error record.

Left running **LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM**, fall, 100 ms/row,
brightness ceiling 70, pulse enabled, unpaused. Optical confirmation pending.
Evidence/backups: `build/board-readback/strip-five-20261016/summary.json`,
per-position records, `attempt1-*`, `head-fall-a/b*`, UART raw/traffic and
`chain-live-result.json`. Earlier preparation/head-pending paragraphs are
superseded. No CAD or inventory changes; scan clocks remain independent.

The two-diffuser print is still RUNNING, latest 90%, layer 10/25, no print/HMS
errors; completion not yet verified (`build/printer/diffusers-two-job.json`).


## Stronger brightness pulse flashed (2026-10-16)

User confirmed all five boards work correctly, but found the original pulse
amplitude too low. The head alone was updated to a 5–100% brightness envelope
(relative to `b` ceiling), over 64 animation steps instead of 32. Four-line
pulse period gives successive fully visible falling lines different brightness
levels; at 100 ms/row the cycle lasts 6.4 s. At ceiling 70 the requested driver
range is approximately 4–70. Existing gamma correction and scan/blanking remain.

Head UUID d7-50-ab-cd-41-1c-bd-ff: two matching full 16 KiB working backups
saved before updating; all 13,580 image bytes matched readback; all option
bytes preserved, no programmer power or separate erase commands. Receivers
and their position mapping remain unchanged. `make test` and all seven native
renderer tests passed; RAM remains 1,952 bytes including 256 stack, conservative
stack sum 252 unchanged. Preview clip: `build/strip-text-pulse-prepared/pulse.gif`.

SWIO startup/status passed. First UART open rejected an invalid startup line;
subsequent 20 exact pings, mode/text/speed/brightness/effect acknowledgements
and two seconds of uptime progress passed. Head errors stayed at the startup
baseline 1, drops 0; no clearing or reset to obtain a clean counter. No RAM
diagnostic reads were used in this run. Left running the same Polish falling
sentence, 100 ms/row, ceiling 70, pulse on, unpaused. Stronger-pulse optical
assessment pending. Original all-five optical confirmation is retained.

Newest head image/hash: `build/strip-text-pulse-prepared/manifest.json`.
New backups/readback/status/live evidence:
`build/board-readback/strip-five-pulse-20261016/summary.json`. Earlier frozen
candidate and all five initial program records are preserved. No CAD/stock edits.


## Six-scene PWM simulation, MCU budget and PC soundtrack (2026-10-16)

User requested simulation before any further five-board flashing. Added a
native 40x8 PWM show with Silk ribbon, Ripple garden, Ember trails, Five lanterns,
Light ladder and Daisy chain. Independent 0–100 pixel levels, integer synthesis,
38.4-second exact loop with 960 ms crossfades. `make renderer-pwm` opens it;
N selects next scene, A auto, Space pause, +/- brightness. Visible native
window was inspected; complete recordings and six-scene sheet are in
`build/pwm-show/`. Desktop floating/resize attempts failed; preview remains
in its ordinary tiled window. No unrelated windows were closed or modified.

A separate full MCU candidate builds via `make pwm-show-images`: head plus
four addressed receivers, each running the same integer core locally from
14-byte phase/scene/brightness packets (new magic 0xb6, rejecting text 0xa6).
No full 320-pixel buffer on the head. Link/batch/scan limitations are in
`firmware/pwm-show/README.md`. Actual WCH link results: head 11,116 flash /
1,620 RAM including 256 stack (428 RAM free); receivers 7,712 / 1,164 (884 free).
Foreground max 128 plus retained 48 ISR allowance = 176 / 256 stack; runtime
high-water and real-time throughput unmeasured. Pattern/packet/head/receiver
host tests, eight renderer tests, all firmware variants and head clangd passed.
Exact sizes/hashes/stack evidence: `build/pwm-show/resources.json`.

User then requested PC music/voice synchronization in a bell-led progressive
style. Prepared original music and original complete-phrase narration using
local CPU Supertonic M1, native speed 0.95, no waveform stretching. Source
`config/pwm-show-audio.json` and `scripts/pwm_show_audio.py`; earlier speech
config/ROCm untouched. Audio DAC presentation time drives absolute simulator
phase; Space pauses audio and light. One full 38.4-second PC playback completed
without audio warnings; 38 scene/tick checks cover all six scenes. A standalone
narrated MP4 is `build/pwm-show/pwm-show-narrated.mp4`; replay with
`.tools/native-tts/bin/python scripts/pwm_show_audio.py`, optional `--loop`.
PC audio is not a claim of measured physical board synchronization.

No MCU, serial, probe, power, option-byte or CAD operation occurred in this
PWM-show task. Real boards retain the previously verified falling-text firmware
and stronger pulse; picocom was left alone. New PWM images remain unflashed.


## PWM show head programmed only (2026-10-16)

User explicitly requested flashing the head (position 1 from left). Identified
UUID d7-50-ab-cd-41-1c-bd-ff and preserved two matching full 16 KiB working
flash backups before writing. All 11,116 frozen head-image bytes matched
full-flash readback. All option bytes preserved; no programmer power or
separate erase commands. SWIO banner and complete status passed: 40 ms,
unpaused, requested brightness 100, UART errors 0/drops 0.

Positions 2..5 retain the previously verified text receivers (0xa6). They reject
new PWM phase packets (0xb6), so the PWM head cannot complete its four-receiver
batch and advance the show yet. No full-chain/optical PWM pass is claimed.
Matching PWM receiver images are built but unflashed. PC music/narration still
targets the simulator, not the physical chain. The earlier complete text/pulse
state is no longer active across the entire chain; original images/readbacks
and the immediately preceding working head are preserved.

Evidence/backups: `build/board-readback/pwm-show-20261016/summary.json` and
`position-1/`. SWIO remains on position 1; no terminal left open. No CAD or
inventory changes. This supersedes the earlier all-PWM-images-unflashed status
only for the head.


## PWM receiver position 2 programmed (2026-10-16)

On the user's request to flash the next board, the probe UUID
`d7-56-ab-cd-41-22-bd-ff` identified recorded position 2 from the left.
Programmed the matching PWM-show tile1 receiver (I2C 0x32): all 7,712 image
bytes matched full-flash readback after two identical full 16 KiB backups.
Option bytes and programmer power were preserved. SWIO startup and complete
PWM receiver status reply passed; terminal closed afterward.

Positions 1 and 2 now run PWM-show firmware; positions 3..5 still require their
matching receiver updates before the complete show can advance and be tested.
PC music/narration remains synchronized to the simulator only.
Evidence/backups: `build/board-readback/pwm-show-20261016/position-2/`;
current deployment summary: `build/board-readback/pwm-show-20261016/summary.json`.
SWIO is on position 2. This supersedes the preceding head-only deployment status.


## PWM receiver position 3 programmed (2026-10-16)

Probe UUID `d7-69-ab-cd-41-35-bd-ff` matched recorded position 3 from the left.
Flashed matching PWM-show tile2 receiver (I2C 0x33) after two identical full
16 KiB backups. All 7,712 image bytes matched full-flash readback; options and
programmer power preserved. SWIO startup and complete receiver status passed;
terminal closed. Evidence: `build/board-readback/pwm-show-20261016/position-3/`.
Positions 1..3 now run PWM-show; positions 4..5 still require updates before
full-chain testing. PC audio remains simulator-only. SWIO is on position 3.
This supersedes the preceding deployment status.


## PWM receiver position 4 programmed (2026-10-16)

Probe UUID `d7-73-ab-cd-41-3f-bd-ff` matched recorded position 4 from the left.
Flashed matching PWM-show tile3 receiver (I2C 0x34) after two identical full
16 KiB backups. All 7,712 image bytes matched full-flash readback. Existing
option bytes (USER ff) and programmer power were preserved. SWIO startup and
complete receiver status passed; terminal closed. Evidence:
`build/board-readback/pwm-show-20261016/position-4/`.
Positions 1..4 now run PWM-show; position 5 still requires its update before
full-chain testing. PC audio remains simulator-only. SWIO is on position 4.
This supersedes the preceding deployment status.


## All five PWM-show images programmed (2026-10-16)

Final probe UUID `d7-6e-ab-cd-41-3a-bd-ff` matched recorded position 5.
Flashed matching tile4 PWM receiver (I2C 0x35) after two identical full 16 KiB
backups; all 7,712 bytes matched full-flash readback. Option bytes and programmer
power preserved. SWIO startup/status passed and terminal closed. Evidence:
`build/board-readback/pwm-show-20261016/position-5/` and parent `summary.json`.
All five positions now have matching PWM-show firmware, superseding the prior
mixed deployment. Full-chain visual confirmation is pending. Picocom was found
open and left undisturbed; no new UART traffic pass is claimed. PC audio still
drives only the simulator. SWIO remains on rightmost position 5.


## Five-tile PWM show visually confirmed (2026-10-16)

After all five matching PWM-show images were programmed and readback/startup
verified, the user confirmed: "works." This records a user-observed full-chain
visual pass, superseding pending visual confirmation. No instrumented PWM,
current, optical timing or runtime stack measurement was performed; no new
UART traffic test is claimed. PC music/narration still targets the simulator.
Evidence: `build/board-readback/pwm-show-20261016/summary.json`.

## Physical five-tile music and narration

Close picocom first (Ctrl+A, then Ctrl+X). From the repository root:

```sh
.tools/native-tts/bin/python scripts/pwm_board_audio.py
```

Add `--loop` to repeat, or `--port /dev/ttyACM0` to select the UART explicitly.
Ctrl+C stops playback and resumes the standalone automatic show. Keep PC UART
connected through the existing head-to-four-receivers chain; SWIO is not needed
for playback. The launcher refuses a port already used by another process.
Audio is synthesized/cached before the UART is opened, with no waveform time
stretching. The head needs the audio-phase update; existing PWM receivers work
unchanged. Music and speech come from the PC speakers.

The PortAudio DAC presentation clock determines the 0..959 animation tick at
25 ticks/second. UART `k TICK` selects automatic scene geometry at that absolute
tick, holds native advancement, and replies `OK tick TICK` after all four
receivers CRC-acknowledge the phase. The host skips elapsed ticks rather than
queuing delayed frames. This prevents accumulated clock drift; bus, serial,
scan and operating-system latency remain. No optical timing measurement is
claimed. Logs: `build/pwm-show/audio/board-{uart.log,playback.json}`.


Final physical audio run passed: all 960 ticks acknowledged; no audio warnings,
UART errors unchanged at 2 and drops at 0. Phase ACK mean 16.06 ms,
max 24.22 ms. User confirmed scene alignment. Tiles returned
to standalone automatic show; serial released. Evidence:
`build/board-readback/pwm-audio-20261016/summary.json`.


## General firmware R3 — verified five-board chain (2026-10-17)

`v3-general` provides binary UART routing, RAM/flash loading, timed text/bitmap/
brightness tracks, scheduled RAM segment replacement, queued raw frames and PC
audio synchronization. I2C carries the shared clock. All five role images have
matching physical readbacks and preserved backups/options. All five passed
3008-byte saved-show restart/readback checks. The chain now runs the228-byte
looping demo from safe A/B flash at brightness100; the serial port is released.
Normal content updates use UART without reflashing or moving SWIO.

The user resoldered the intermittent head S5 connection and reported it appears
okay. Final38.4-second narrated PWM streaming passed at230400/18fps with0late/
skipped frames,0added UART errors/drops and0audio warnings;15ACK timeouts were
recovered. Initial reconnect timeout and unsuccessful faster runs remain in the
evidence.460800 failed qualification;921600 remains unqualified. Runtime stack
high-water, rails/current/waveforms and optical timing skew remain unmeasured.

Build `make general-images STACK_USAGE=1`; test `make general-test`; preview
`make general-preview`. Current `make test` passed, including43 general Python
tests and native clock/display/flash register checks. Usage/launch commands:
`firmware/general/README.txt`. Protocol: `docs/general-firmware-protocol.txt`.
Review: `docs/general-firmware-review-20261017.txt`. Physical results/limitations:
`docs/general-firmware-hardware-20261017.txt`. Summary/backups:
`build/board-readback/general-20261017/summary.json` and `revision3/`.

Frozen images/source hashes/memory: `build/general/review-candidate/manifest.json`.
Head13272 and receivers13284 image bytes;2036/2048 RAM includes256 stack, with
compiler combined-path assessment236/256. Every role reports1472 safe-program
bytes or3008 capacity-program bytes. Default/archived variants remain available;
builds do not program boards.

The user superseded the earlier manual model-switch gate by requesting automatic
Astra review/completion. Scoped Astra reviews approved the corrected native R3
and host changes before final qualification. Standing UUID, matching full backups,
programmed readback, option-byte and programmer-power safeguards still apply.

## V3.2 accepted main CAD version — 2026-10-17

The separate [v3.2 project](../hw/ledkiv3.2/README.md) introduces
CH32V006E8R6, directional west-to-east/south-to-north UART and shared I2C
on a49.6mm square tile. The user accepted the routed 1,490-segment board after
manual edits and trace cleanup as [the main milestone](../docs/milestones/v3_2-main-20261017.txt).
All 76 nets are connected; native DRC retains one existing `/ADDR0` warning,
with zero errors, opens or parity findings. The first robot route and original
unrouted study are preserved separately.
[Design study](../docs/v3_2-study.txt) and [custom downloader research](../docs/v3_2-network-update.txt).
The loader is proposed, not implemented or tested. V3.1 and active firmware
remain preserved. The [five-board fabrication derivative](../docs/v3_2-fabrication-20261017.txt)
removes the dangling stub, restores Q3/R25 feed widths and selects the six
generic passive MPNs; fresh ERC/DRC/opens/parity/ignored are zero. Current
exports are in `hw/ledkiv3.2/exports/fabrication-20261017-r2/`. The silk-correctedr2upload and reference preview are complete. The user chose
JLCONE defaults for this prototype; physical qualification remains pending.
