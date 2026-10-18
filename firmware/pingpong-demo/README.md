# Two-board I2C ping-pong demo

The two v3 boards form one 16×8 display. A single ball bounces diagonally across
the seam and outer edges. The left controller sends every phase over the existing
100 kHz I2C transport; it advances only after the receiver's reply CRC matches.
The right board renders received phases without running its own animation clock.
Corner indicators change every four successful exchanges. A transport failure
or 1.5 seconds without a valid exchange freezes the last ball and lights the
corner indicator steadily. Pausing keeps exchanges running with a paused phase.

Build both images with `make pingpong-demos -j4`, or one with
`make VARIANT=v3-pingpong-demo ROLE=left` / `ROLE=right`.
Outputs are `build/v3-pingpong-demo-left/letki.bin` and
`build/v3-pingpong-demo-right/letki.bin`. Unlike the UART-chain test, these are
different images: left is controller, right is target at address `0x32`.
The default build remains text v3. Builds never flash.

Use the existing common supply/GND, SDA/SCL edge bridge, and one 4.7 kΩ pull-up
pair. Both identified v3 boards have standing firmware/test authorization; verify
identity and retain backups/readbacks before programming. Do not change option
bytes or programmer power. Existing 51 Ω direct-drive limitations remain.

SWIO commands: `s` status and `h` help on either board. On the left only,
`p` pauses, `r` resumes, `0` restarts the trajectory, `+` speeds up and `-` slows
down (50–500 ms per step; default 100 ms). All settings are volatile. UART is
unused; existing UART wiring can remain connected. This is an animation that
demonstrates communication, not a playable Pong game or packet delivery guarantee.

The application reuses the active binary display driver, SDK/startup/linker,
gamma brightness 100, 2 kHz scan/250 Hz frames, 100 µs GPIO-low blanking and
TIM2 unblank IRQ. I2C/protocol sources are shared with the physically checked
interface demo. Application/transport/logging remain foreground and nonblocking;
logs may drop when no probe drains the fixed queue. No heap or floating point.
Left and right buffer swaps use independent scan clocks; this does not establish
phase-locked optical refresh across the seam.

Preview the actual renderer with `python3 scripts/preview_pong.py`:
`build/preview/pingpong.gif`. Host tests exercise all 210 phases, seam/edge
continuity, acknowledgement-dependent progression, retries, pause/resume, reset,
millisecond wrap, invalid packets, stale/fault indication and display backpressure.
Host tests do not establish physical timing, optical quality, rail/current or
runtime stack usage. Current board results are recorded separately in
`docs/current-state.md` and `build/board-readback/`.

Build assessment (2026-10-14): left image 10,988 bytes, 672 RAM section bytes
including 256-byte stack; right 10,448 image bytes and 664 RAM section bytes.
The conservative I2C recovery foreground path is 204 bytes; adding both used
ISR paths gives 240 bytes. Compiler reports and division-helper disassembly are
saved in `build/pingpong-validation.json` and `build/pingpong-disassembly.txt`.
Runtime stack high-water is unmeasured. `make test`, all variants and clangd
checks passed; only the archive's existing two unused-helper warnings remained.
Both final images were flashed and readback verified on their identified boards,
with two matching full backups each and unchanged option bytes/programmer power.
The left passed 20 consecutive CRC phase updates and pause/continued exchange/
resume against the preceding interface receiver. With both final images running,
the right then received 32 consecutive phases with zero failures, covering a full
horizontal round trip. Both boards are left running at 100 ms per step.
Evidence: `build/board-readback/pingpong-20261014/`. Optical seam quality and
physical disconnect behaviour have not been independently checked.
