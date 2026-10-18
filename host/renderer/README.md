# Native Letki test renderer

A C Wayland client for Arch/Hyprland, drawn with Cairo into Wayland shared-memory
buffers. It compiles the real `pong.c` geometry/state renderer and `protocol.c`
CRC parser. It starts with two 8×8 tiles; board count is a parameter, with keyboard
presets for 1–5. Storage is allocated per tile. The current packet format reserves
one of its 16 phase bits for pause, so the configurable range is 1–256 boards.
Each complete trajectory fits the remaining phase bits. Tile zero is leftmost;
column byte bit zero is the top row. The ball spans the entire horizontal strip.

From the repository root:

```sh
make renderer
make renderer-run BOARDS=5
make renderer-test
```

Arch dependencies: `base-devel`, `pkgconf`, `wayland`, `wayland-protocols`, `cairo`;
tests use `python`. These are already installed on the development machine.
The executable is `build/renderer/letki-renderer`. No browser, XWayland or Python
GUI runtime is needed. `--headless` runs the same renderer/control server without
a desktop connection; `--manual` disables elapsed wall time for deterministic tests.
Both modes can export PNGs.

Window keys are physical number-row **1–5** to change the board count, **Space**
to pause/resume the ball while exchanges continue, **Enter** to stop/start the
test clock, **Right** to stop the clock and step once, **R** to reset, **L** to
break/restore the last board's incoming link, and **Esc/Q** to close.

## Direct agent control

The window and the agent share one running model. A local Unix stream socket
accepts one newline-terminated command per connection and returns one JSON state
object. The executable's `ctl` subcommand is the agent client; no extra MCP server,
agent API key, network service or desktop keystrokes are required.

```sh
build/renderer/letki-renderer ctl stop
build/renderer/letki-renderer ctl boards 5
build/renderer/letki-renderer ctl step 40
build/renderer/letki-renderer ctl status
build/renderer/letki-renderer ctl link 2 down
build/renderer/letki-renderer ctl advance 1500
build/renderer/letki-renderer ctl snapshot build/renderer/failure.png
build/renderer/letki-renderer ctl link 2 up
build/renderer/letki-renderer ctl run
```

JSON exposes virtual time, run/pause mode, trajectory period and each tile's
phase, accepted/failed counts, liveness, link state and eight actual column bytes
as 16 hex digits. A command failure returns `ok:false`, preserves model state,
and makes `ctl` exit nonzero. `status` is read-only. The agent can assert pixels
directly and inspect the same Cairo output with `snapshot PATH`, including paths
with spaces. PNG export includes the visible test scene and its status labels.

Commands:

| Command | Meaning |
| --- | --- |
| `boards N` | Reallocate/reset a 1–256-tile strip; preserve clock and input mode |
| `stop` / `run` | Stop/start wall-clock advancement |
| `step [N]` | Advance N intervals, 1–10,000, respecting pause and input mode |
| `advance MS` | Advance virtual time, 0–3,600,000 ms, including timeout checks |
| `pause` / `resume` | Hold/release communicated ball phase; traffic continues |
| `speed MS` | Change exchange interval, 50–500 ms |
| `reset` | Clear phases/counters, restore links, unpause; preserve count/speed/mode/clock setting |
| `link INDEX up/down` | Control incoming simulated link; zero disconnects the controller |
| `corrupt INDEX` | Damage the next simulated packet CRC for that board |
| `mode simulation/external` | Clear tile state and select simulated exchanges or injected input |
| `receive INDEX PHASE` | Apply a phase already validated by a log-reading agent; optional pause bit 32768 |
| `packet INDEX HEX8` | Validate/apply an actual four-byte firmware packet with CRC |
| `frame INDEX HEX16` | Render an arbitrary eight-column frame verbatim on one tile |
| `snapshot PATH` | Save the scene as PNG |
| `status` / `quit` | Read state / close this renderer |

Indices are zero-based. In external mode, animation is driven only by injected
phases/frames; advancing time still evaluates the firmware's 1.5-second timeout.
For example, an agent observing validated `PONG RX phase=19 CRC` can send
`receive 1 19`. This reconstructs a frame from the logged phase; it does not read
the board's framebuffer or establish its optical output. Connect to a probe
separately using the established SWIO tooling when explicitly testing hardware.
The desktop program itself never opens a programmer, powers or flashes a board.

Simulation models a linear packet/acknowledgement chain using the firmware CRC
and render state. The controller advances only after all configured tiles accept
the phase; a failed link freezes progression and downstream receivers expire.
This is a logical test topology, not an implementation of multi-address I2C
discovery or a claim that the current two-board firmware supports 256 devices.
Raw `frame` input stays visible until a successful phase replaces it; it has no
inferred protocol heartbeat.

Default socket: `build/renderer/control.sock`. Launch additional independent
instances with `--socket build/renderer/another.sock` and pass that same option
before `ctl`. Socket access is restricted to the current UID, clients have bounded
command sizes and timeouts, and an existing socket is never replaced. Clean exit
removes the owned socket. After a forced kill, check that the old process is gone
before removing a stale socket, or use another path. A restricted agent sandbox
may require approval to access local sockets/Wayland; ordinary builds need none.

## Validation

`make renderer-test` tests the running C process through the public agent API:
complete trajectories/seams/wraps for every 1–5-tile preset; pause with continued
traffic; failed links, timeouts, retry recovery; CRC corruption/rejection;
external packets/raw frames; malformed command state preservation; a 256-tile
allocation; PNG export; stalled clients; instance collision; and client CLI output.
All existing firmware tests and all variants also pass after generalizing geometry.
The firmware's original two-board API is retained and its existing tests pass.

The native window was identified with `xwayland:false` and inspected on Hyprland;
targeted keyboard 1/5 input was verified through socket readback. Evidence is in
`build/renderer/`: integration/build logs, `hyprland-validation.json`, window
capture and scene snapshots. Tests establish host behavior, not electrical
timing, physical communication or display optics. The boards continue running
the preceding, preserved ping-pong image; the generalized sources were built
but have not been flashed as part of this desktop task.


## Standard text firmware preview

`make renderer-text` selects two boards and the shared standard text scene.
`python3 scripts/demo_strip_text.py --tour` demonstrates bounce then scroll;
`--record` saves complete-cycle GIFs through an independent native C instance.
The open renderer accepts `demo text` / `demo pong`. In text mode,
`uart t YOUR TEXT`, `uart m bounce`, `uart m scroll`, `uart v 75`, `uart b 25`,
`uart p`, `uart r` and other commands execute the actual firmware parser.
JSON adds `demo`, `text_mode`, `text_columns`, `text_offset`, `brightness_pct` and
`uart_reply`. UART status/ping responses use the same parser and CRLF as the
candidate firmware. This is local simulation; no serial/programmer is opened.
The text scene remains configurable to other tile counts; the prepared physical
images currently implement exactly two roles. See
[the candidate guide](../../firmware/strip-text/README.md).


## Six-scene five-tile PWM show

`make renderer-pwm` opens the separate **Letki PWM show** window. The 38.4-second
loop blends ribbon, ripples, comet trails, tile lanterns, a low-end brightness
ladder and a Daisy chain pulse. Every pixel has its own 0–100 level. Space
pauses; N chooses the next scene; A returns to auto; +/- adjusts brightness.
Use `python3 scripts/demo_pwm_show.py --scene daisy` to select that scene.
`--record` exports an independent complete-loop GIF and scene sheet; a compact
MP4 is also saved in `build/pwm-show/`.

The public socket is `build/pwm-show/control.sock`. New commands are `demo pwm`,
`pwm scene auto|silk|ripples|comets|lanterns|ladder|daisy` and
`pwm brightness 0..100`. JSON adds pwm_scene/auto/tick/brightness and each
tile's row-major 64-byte `levels` as 128 hexadecimal digits. These are simulation
levels, not board readback. UART and probe access are never opened. In this
preview, link/CRC fault injection belongs to the older packet simulations;
it does not alter directly generated PWM levels.

The exact integer core also compiles into the separate unflashed MCU candidate.
[Memory, phase transport and validation](../../firmware/pwm-show/README.md).


The PC soundtrack and narration run with
`.tools/native-tts/bin/python scripts/pwm_show_audio.py` (`--loop` repeats).
The audio DAC sample clock drives the native simulator via `pwm seek MS`;
`pwm audio on/off` marks audio master mode. Space pauses sound and light
together. See the PWM-show guide for source settings, offline preparation and
the 38.4-second narrated recording. No serial/probe connection is opened.
