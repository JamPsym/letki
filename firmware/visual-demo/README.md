# Standalone 8×8 radial wave

This separate v3 application boots into a continuous wave spreading outward
from the centre between the four middle pixels. All 64 LEDs have independent
gamma 2.2 PWM levels. It keeps running after disconnecting the PC/probe data
connection, provided the board remains powered.

```sh
make VARIANT=v3-visual-demo -j4
make compdb VARIANT=v3-visual-demo
python3 scripts/preview_wave.py
```

Outputs: `build/v3-visual-demo/letki.bin` and
`build/preview/radial-wave.gif`. Builds never flash. The active scrolling text
application remains `make VARIANT=v3`, producing `build/v3/letki.bin`.
This project shares the v3 SDK, startup, linker, transport and display driver;
it does not have a separate MounRiver IDE project.

SWIO controls use the existing terminal wrapper. UART is 115200 8N1 and requires
Enter for each command. All reports use CRLF. Supported controls:

| Command | Action |
| --- | --- |
| `b 50` + Enter | Set global perceptual brightness, 0–100 |
| `v 80` + Enter | Set animation step interval, 10–500 ms |
| `+` / `-` | Faster / slower in 5 ms steps |
| `p` / `r` | Pause / resume |
| `0` | Restart wave, 45 ms steps, 100% brightness |
| `s` / `status` | Status including UART errors/drops |
| `h` / `help` | Help |
| `ping TOKEN` | Exact UART echo |

Brightness can change while paused. Invalid/incomplete edits preserve state;
Esc cancels a draft. UART help/status/ping cannot interfere with a SWIO edit.
The text/frame/arm controls and full text TUI are for the text application;
this standalone demo does not implement them. Opening SWIO restarts the board.

The wave generator uses a 64-byte radius map and 32-byte cosine table in flash,
with no floating-point arithmetic, square roots or heap allocation on the MCU.
Two fixed 64-pixel, 16-bit PWM buffers use 256 RAM bytes; a foreground scratch
frame adds 64 bytes. Gamma conversion and global scaling run in the foreground.
The scan ISR only selects precomputed duties and swaps at a complete frame
boundary. `DISPLAY_LEVELS` selects this path; normal text builds retain their
original two eight-byte frame buffers. Global brightness is sampled when a
level frame is queued, and the application requeues after brightness changes.

Timing: nominal 10 kHz PWM with 1,200 steps; 100 µs GPIO-low blank; 2 kHz
column scan / 250 Hz full frames. Only nonzero row outputs return to timer AF.
The default 32-phase animation takes 1.44 seconds per cycle.

The final image uses 11,856 flash bytes and 1,492 RAM section bytes including
the unchanged 256-byte stack, leaving 556 RAM bytes outside allocated sections.
The assessed foreground path is 152 stack bytes; adding all three ISR paths
(36 + 8 + 12) totals a conservative 208 bytes. Runtime stack high-water and
external waveforms/current/optical appearance have not been measured.

Host tests cover radial symmetry, phase periodicity, bounds, per-pixel gamma,
frame boundary swaps, GPIO-low blanking, brightness while paused, invalid
commands and UART/SWIO draft isolation. All variants build; clangd checks pass.
Final flash and all image bytes were readback verified on the authorized v3
UUID `d7-73-ab-cd-41-3f-bd-ff`. UART brightness/speed/pause/resume and 20 exact
pings passed with zero errors/drops. Pre-demo text flash was backed up twice at
`build/board-readback/visual-20261012T130346Z/working-full-{1,2}.bin`.
Final programming evidence is in `build/board-readback/visual-20261012T130609Z/`.
