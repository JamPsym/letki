# Standard two-board text firmware candidate

These separate left/right images replace the diagnostic animation with one
coordinated 16x8 text display. Default is **LETKI DZIAŁA**, in the compact Polish
font, moving back and forth with a short hold at either end (75 ms per column,
brightness 100). Continuous leftward scrolling and top-to-bottom falling lines are also available. All use
fixed buffers, integer animation and the active gamma/PWM display driver.

```sh
make strip-text-images -j4
make renderer-text
python3 scripts/demo_strip_text.py --tour
python3 scripts/demo_strip_text.py --record
```

Images: `build/v3-strip-text-left/letki.bin` and
`build/v3-strip-text-right/letki.bin`. Each role is compiled with `-Os`; old
single-board text (`make`) and diagnostic commands stay available. Build alone
never flashes. Frozen candidate images/hashes are in `build/strip-text-prepared/`.
Both images were flashed/readback verified on their known boards on 2026-10-14,
with two matching full backups each and unchanged option bytes/programmer power.
The new pair passed 20 exact UART echoes through the right relay, live controls
and 1839 head-observed I2C frame CRC acknowledgements with zero failures.
Evidence: `build/board-readback/strip-text-20261014/summary.json`.
Final physical state is default LETKI DZIAŁA in bounce, 75 ms and brightness 100.


The native renderer compiles the exact scene/UTF-8 parser/font/packet code,
showing both tiles as one strip. Its `demo text` selects this scene, and
`uart COMMAND` executes the actual firmware command parser. Recordings use an
independent headless native C instance; they do not interrupt the open window.
GIF files are `build/strip-text-preview/bounce.gif` and `scroll.gif`. The tour
shows bounce, then scrolling, and returns to the default bounce mode.

## Wiring and roles

Left/original UUID: `d7-73-ab-cd-41-3f-bd-ff`; right/second UUID:
`d7-6e-ab-cd-41-3a-bd-ff`. Keep existing power/GND and repaired v3 grounds.
PC adapter TX connects to left RX/PD6; left TX/PD5 goes to right RX/PD6;
right TX/PD5 returns to adapter RX. UART is 115200, 8N1, no flow control.
The right board transparently forwards the left's ASCII replies; it never
interprets those replies as commands or adds boot/status logs to UART.

I2C SDA/PC1 and SCL/PC2 carry the right tile's **actual pixels and brightness**,
with a sequence and CRC-8. The left is controller, right is address 0x32,
configured bus rate 100 kHz. Retain the existing single left-board 4.7k pull-up
pair. The head commits its corresponding local frame/animation advance after
the reply CRC matches; failed exchanges freeze advancement and retry. In-flight
snapshots cannot overwrite a newer UART command. The receiver keeps the last
valid frame on malformed packets/transport loss. There is no independently
running text clock on the right.

The frame driver is derived from the previously tested foreground I2C state
machine, with separate 14-byte frame buffers and API. The original four-byte
diagnostic transport is unchanged. This new payload/firmware combination passed the physical tests summarized
above; waveform/optical qualification remains pending. Matching logical frames do not phase-lock the
two independent scan clocks or establish optical/electrical timing.

When programming is requested after preview, load the **right receiver first**,
then the left head. Verify each connected identity, preserve two matching full
working backups, verify complete image readback and retain option bytes and
programmer power settings. Use the existing standing authorization for these
two known boards. Do not flash during preview or as part of a build.

## UART commands (press Enter)

| Command | Action |
| --- | --- |
| `t YOUR TEXT` | Atomic UTF-8 text update, max 64 characters, Polish uppercase supported |
| `m bounce` / `m scroll` / `m fall` | Change animation and restart at its beginning |
| `v 75` | Speed, 10–500 ms per column |
| `b 25` | Brightness ceiling, 0–100, propagated to both tiles |
| `e pulse` / `e off` | Pulse brightness / restore steady brightness |
| `p` / `r` | Pause/resume movement; pixel exchanges continue |
| `+` / `-` | Adjust speed by 5 ms within bounds |
| `0` | Resume/reset current text with bounce, 75 ms and brightness 100 |
| `a` | Hold current text at its beginning until resumed |
| `f` plus 16 hex digits | Manual left-tile frame; right is blank |
| `g` plus 32 hex digits | Manual complete 16-column frame; optional space after g |
| `status` / `s` | Standard speed/pause/uptime/UART diagnostic/brightness response |
| `ping TOKEN` | Exact `PONG TOKEN` response through the UART reply chain |
| `help` / `h` | Commands |

Only prefixed text updates change the message. Invalid/damaged/overlong input
preserves it. All replies use CRLF; UART accepts Enter/CRLF, and cancelled drafts
preserve state. SWIO edits remain separate from UART line staging; a UART update
is rejected while a SWIO edit is pending. All controls are volatile.

The compact font supplies Latin/Polish uppercase letters; spaces use two columns,
letters four including spacing. Unsupported glyphs are blank. In bounce mode,
text shorter than the display stays still; scrolling mode repeats it. Brightness
changes preserve host frames. `t` or `0` returns from host frames to animation.
This variant's arm control holds at the beginning; it does not implement the old
speech demo's single-cycle playback contract.

The existing UART helper and TUI's standard controls can be used on the head;
select modes via an explicit UART command. The SWIO wrapper recognizes the head's
text banner and safely prefixes ordinary input with `t `. Standard SWIO text,
speed, brightness, frame and single-key controls work there. `m` and `g` are
complete-line UART extensions. On the receiver, SWIO `s` reports sequence,
accepted/failed frames, link freshness and UART diagnostics; `h` explains its role.

## Checks and limits

Host tests exercise the actual command/scene code (both trajectories, speed
bounds, UTF-8 and 64-character limits, invalid-input preservation, SWIO draft
isolation, pause/brightness/manual frames), real app paths for both roles
(snapshot/ack handling, display backpressure, in-flight edits, exact right-side
UART relay) and the real 14-byte driver with mocked registers (address/STOP/
single-byte ACK receive, packet bytes/CRC, NACK, timeout/recovery and clock wrap).
Every single-bit packet corruption is rejected without changing decoded frames.
The native process is tested through its public agent socket using the same
firmware parser. Existing tests, all firmware variants and clangd checks pass.

Static/compiler/disassembly assessment, image sizes/hashes and frozen source
hashes are in `build/strip-text-prepared/manifest.json`; build/test logs use
`build/strip-text-*.log`. The 256-byte stack reservation and WCH fast IRQ attributes
are retained. Physical UART/I2C logical operation passed; rail/current/waveforms, optical
quality, right final cumulative diagnostics and runtime stack high-water remain
to be measured.
All previous verified readbacks are preserved. Both were updated with two
matching full backups each and unchanged option bytes/power.


## Falling lines and brightness pulse (2026-10-16 candidate)

`m fall` wraps the current message into centered lines and moves each line
from above the top row down through the bottom, then repeats the message.
Whole words stay together when they fit; longer words split at the display
width. This is a vertical crawl on an eight-row matrix, without perspective
scaling. Each line takes 16 animation steps; `v 75` sets 75 ms per vertical
pixel. Polish marks use the existing compact font.

Selecting `m fall` enables a triangle brightness envelope from 5% to 100%
of the requested `b` level over 64 animation steps. Existing gamma correction
still applies in the display driver. `e off` restores steady brightness;
`e pulse` can enable modulation in bounce or scroll as well. Selecting bounce
or scroll disables the effect; `0` also clears it. Pause and transport failure
hold both movement and pulse phase. Manual frames use the requested brightness
without modulation. Status keeps reporting the requested ceiling.
The head sends the effective brightness with the exact pixel snapshot, and
publishes the same value locally after acknowledgement.

Five-board geometry can be previewed with the exact same scene code:

```sh
make renderer
python3 scripts/demo_strip_text.py --boards 5 --mode fall --text 'LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM'
python3 scripts/demo_strip_text.py --boards 5 --record --text 'LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM'
```

`build/strip-text-preview/fall.gif` is the recorded five-board preview.
The original `strip-text-images` command retains its two-board topology.
The separate five-board candidate below implements four addressed receivers.
Both new candidates are built and host-tested, not flashed. The older frozen `build/strip-text-prepared/` images and physical
readbacks remain intact. New candidate images/evidence are separate in
`build/strip-text-fall-prepared/`.


## Prepared five-board images

```sh
make strip-five-images -j4
```

From left to right, load these distinct images only after identifying each
physical board and saving two matching full working flash backups:

| Position | Build role | I2C address | Image |
| --- | --- | --- | --- |
| 1, head | `head` | Controller | `build/v3-strip-five-head/letki.bin` |
| 2 | `tile1` | 0x32 | `build/v3-strip-five-tile1/letki.bin` |
| 3 | `tile2` | 0x33 | `build/v3-strip-five-tile2/letki.bin` |
| 4 | `tile3` | 0x34 | `build/v3-strip-five-tile3/letki.bin` |
| 5 | `tile4` | 0x35 | `build/v3-strip-five-tile4/letki.bin` |

No UUID-to-position assignment is assumed from assembly order. All v3 ground
repairs and a common ground/supply are still required. Retain the one existing
I2C pull-up pair, with SDA and SCL carried across all boards. UART continues
PC TX -> head RX, each TX -> next RX, last TX -> PC RX, at 115200 8N1.
Each receiver transparently relays UART replies; commands are parsed by the
head. Configure all receivers before the head when a physical programming/test
session is requested. Preserve option bytes and programmer power settings.
Builds and previews never open the programmer.

Head geometry is now 40x8 for all three modes. Every animation step snapshots
one scene and sends the four tile frames with the same sequence and effective
brightness. The head advances/commits only after all four CRC replies match.
Failure retries the entire next scene; new commands invalidate older in-flight
snapshots. Receivers publish on arrival, so partial/failed batches can briefly
leave different scenes on different tiles; there is no synchronized latch or
rollback across boards. Hardware frame scan clocks remain independent.
The renderer illustrates geometry and logic, not five-board physical timing.

The original `g` command remains a manual 16-column frame; remaining tiles are
blank. `f` remains an eight-column frame. Animated text uses the complete width.
The default remains bounce, **LETKI DZIAŁA**, 75 ms, steady brightness 100.
Example after physical qualification:

```text
t LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM
m fall
v 100
b 70
e off
e pulse
```

New images/hashes and static assessment: `build/strip-text-fall-prepared/manifest.json`.
The five-board I2C/UART chain and new optical effect require physical validation.
No boards were flashed during this preparation.


### Physical five-board state and stronger pulse

All five boards are programmed and user-confirmed working (see the current
state record for physical UUID order). The head alone was then updated with
a wider 5–100% envelope over 64 steps after the user found the first pulse
subtle. This four-line period gives fully visible successive lines different
brightness levels; at 100 ms it lasts 6.4 s. At ceiling 70 the requested driver
percentage spans approximately 4–70. Receiver images are unchanged.
Newest head image: `build/strip-text-pulse-prepared/letki.bin`; new backup/
readback/live evidence: `build/board-readback/strip-five-pulse-20261016/`.
Preserve earlier frozen candidates and all per-board backups. The new pulse
uses the same retained gamma/scan driver and 256-byte stack.
