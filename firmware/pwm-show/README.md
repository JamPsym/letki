# Five-tile PWM light show candidate

Preview first:

```sh
make renderer-pwm
python3 scripts/demo_pwm_show.py --scene daisy
python3 scripts/demo_pwm_show.py --record
```

The native 40x8 window has six scenes: Silk ribbon, Ripple garden, Ember
trails, Five lanterns, Light ladder and Daisy chain. Each pixel has an independent
0–100 level. The automatic show lasts 38.4 seconds, with 960 ms crossfades
and 40 ms steps. Space pauses, N selects the next scene, A restores automatic
mode, +/- changes brightness, R restarts and Q closes. Recordings use a separate
headless instance. MP4/GIF and a six-scene contact sheet are in `build/pwm-show/`.

`host/pwm-show/pwm_show.c` is the shared integer-only animation core: a 64-byte
flash sine table, no float, heap or frame synthesis in interrupts. The renderer
models gamma-2.2 PWM duty quantized to 1,200 ticks, then converts light intensity
for the screen. A real panel's optics and perceived low levels require a physical
comparison. The preview does not claim to measure PWM waveforms or bus timing.

## MCU builds and resource check

```sh
make pwm-show-images -j4
make VARIANT=v3-pwm-show ROLE=head STACK_USAGE=1
```

Outputs are separate `build/v3-pwm-show-{head,tile1,tile2,tile3,tile4}/` images.
The default text firmware and every previously verified readback are preserved.
No programming, option-byte or power operation occurs during builds/previews.
These PWM images have **not been flashed or physically qualified**.

| Role | Flash / 16,384 bytes | RAM / 2,048 bytes, including stack | RAM left |
| --- | ---: | ---: | ---: |
| Head | 11,116 | 1,620 | 428 |
| Each receiver | 7,712 | 1,164 | 884 |

The 256-byte stack reservation is retained. WCH GCC stack reports/disassembly
show the longest assessed foreground path is I2C recovery: main 20 + bus poll 16
+ bus init 40 + I2C init 40 + clock lookup 12 = 128 bytes. Pixel synthesis uses
main 20 + tile synthesis 56 + pixel 48 = 124 bytes. Division helpers use no software
stack; memcpy's bounded four-byte path does not exceed these maxima. Current
fast ISR software stack reports are zero; retaining the previous conservative
combined 48-byte ISR allowance gives **176 / 256 bytes**. Runtime high-water
and real-time frame throughput remain unmeasured.

Exact sizes/hashes and validation evidence: `build/pwm-show/resources.json`.

## Phase transport

The head sends one 14-byte CRC-protected phase packet to each receiver at
0x32..0x35. The eight-byte payload holds a 32-bit animation tick, scene selector
and reserved bytes; brightness, pause and sequence have their own fields.
Each tile generates only its own 64 levels locally. This avoids a 320-pixel
head buffer and transmitting full grayscale bitmaps. The head advances after
all four CRC replies; receivers publish sequentially, without synchronized
scan clocks or a global rollback. Link failure preserves the last valid frame.

The transport reuses the addressed foreground I2C state machine, but uses new
magic `0xb6`, rejecting the active text protocol's `0xa6`. All five positions
would need matching PWM-show firmware in a later physical session; mixing text
receivers with the new head is unsupported. The UART reply chain remains
PC -> head -> four transparent relays -> PC. The candidate keeps nominal
250 Hz display frames, 10 kHz row PWM, GPIO-low blanking and SWIO/UART/I2C pins.

Head UART commands require Enter:

```text
m auto
m silk
m ripples
m comets
m lanterns
m ladder
m daisy
b 70
v 40
p
r
0
status
ping TOKEN
```

SWIO supports b/v edits, n next scene, a automatic, p/r/0/s/h and +/- speed.
UART control edits preserve a pending SWIO edit. All state is volatile. Status
reports speed, pause, uptime, requested brightness and UART diagnostics, not
pixel readback. Receivers start blank until a valid phase arrives. The separate
text firmware remains available for custom messages and its TUI.

## Validation

Host tests cover actual head/receiver publication, phase batches, six-scene
selection, brightness, failed-transfer retry, in-flight command changes,
display backpressure and every single-bit CRC corruption. Pattern tests cover
level bounds, low-end steps, movement, tile geometry, crossfades, exact show
periodicity and tick wrap. All eight native renderer tests, existing firmware
host tests, all firmware variants and the head clangd check passed. No new
physical firmware validation is claimed.

## PC music and narration

```sh
.tools/native-tts/bin/python scripts/pwm_show_audio.py
.tools/native-tts/bin/python scripts/pwm_show_audio.py --loop
```

The PC preview plays an original minor-key bell ostinato, soft backing tones,
stereo chimes and six original spoken scene introductions. Speech is local
CPU Supertonic M1 at native speed 0.95; there is no waveform stretching. Source
settings/text are in `config/pwm-show-audio.json`; generated audio/caches remain
under ignored `build/pwm-show/audio/`. The earlier speech-demo config and ROCm
environment are unchanged.

The PortAudio DAC presentation clock drives absolute `pwm seek MS` updates;
the renderer's independent clock is stopped during playback. Space pauses both
sound and light; +/- still changes visual brightness. Scene/time shortcuts are
held during audio playback to preserve narration alignment. At the end of one
pass, the window resumes its silent automatic show. `--loop` repeats; Ctrl+C
stops playback. Synchronization is to animation frames plus desktop/audio
scheduling, not measured optical timing. This path opens no serial port or probe.

`build/pwm-show/pwm-show-narrated.mp4` is a standalone 38.4-second recording.
One live pass completed with no reported audio warnings; all six scenes and 38
sample-clock/tick checks were logged in `build/pwm-show/audio/playback.json`.
The resource figures above apply to the separate unflashed MCU candidate;
PC music/voice do not consume MCU RAM/flash. Physical board audio synchronization
has not been tested.


### Head-only physical update (2026-10-16)

Position 1 UUID d7-50-ab-cd-41-1c-bd-ff was programmed on explicit request.
All 11,116 bytes matched readback after two matching full 16 KiB backups;
options/power preserved, SWIO startup/status passed. Positions 2..5 still run
text receivers and reject the PWM protocol, so the show cannot advance yet.
Evidence: `build/board-readback/pwm-show-20261016/summary.json`.
No complete physical PWM or board/audio synchronization pass is claimed.


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
