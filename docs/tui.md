# Letki display TUI

Run from the repository root:

```sh
make tui
# or: python3 scripts/letki_tui.py

# The same interface over USART instead of SWIO:
make tui PORT=/dev/ttyACM2
# or: python3 scripts/letki_tui.py --port /dev/ttyACM2
# --tty is an alias for --port; /dev/serial/by-id/... also works.
```

The interface uses Python's standard-library curses; no new Python packages are needed. Use a UTF-8 terminal at least 76 columns by 24 rows. SWIO remains the default: opening it restarts the board, checks the expected UUID through `SwioLink`, and requires the active v3 text-firmware banner. Close other probe tools before opening SWIO.

With `--port`/`--tty`, the TUI uses 115200 baud, 8N1, no flow control through that serial device. It cancels any leftover UART draft, then checks the active text firmware's status format and an exact random ping reply. This confirms the command protocol; UART does not expose the MCU UUID. Opening UART sends no restart command. The header shows `UART` and the tty name. Close picocom, serial GUI terminals and other readers of the same port before connecting; competing readers can consume the TUI's replies. A missing reply fails the connection and restores serial settings.

Preview it without hardware:

```sh
make tui-demo
# or: python3 scripts/letki_tui.py --demo
```

## Navigation and editing

`1`, `2`, `3` select Text, Pixels and Logs. `gt` / `gT` or Tab / Shift+Tab cycle tabs. In the Text tab, `j` / `k` select an action and Enter activates it. `?` opens the key map and requests the firmware help. `q` exits; when help is open, `q` closes help first.

`i` opens the message editor. All typing stays on the PC until Enter applies it; letters inside a sentence cannot accidentally pause or arm the display. Polish text and character-based Backspace are supported. Text is limited to 64 characters; firmware uppercases supported Latin and Polish letters. Unsupported glyphs render blank, following the firmware font.

Editors have two Vim-style modes. In INSERT, type normally. Esc switches to NORMAL EDIT; `h` / `l` move, `w` / `b` move by words, `0` / `$` move to the ends, `x` deletes, and `i` / `a` enter insert mode. Arrow keys also move the cursor. Enter applies from either mode; Esc again or `q` in NORMAL EDIT cancels without sending anything.

## Firmware controls

| Feature | Key or command |
| --- | --- |
| Set message | `i`, edit, Enter; or `:text No zobacz Adaś` then Enter |
| Clear display text | `:clear` then Enter |
| Set exact scroll interval | `v`, edit, Enter; or `:speed 55` |
| Faster / slower | `+` / `-`, five milliseconds per pixel, clamped to 10–500 |
| Pause / resume | `p` / `r`, or Space in Text |
| Arm one scroll cycle at its start | `a`; then `r` starts it |
| Restore 75 ms, repeat mode and native scrolling | `0` or `:reset` |
| Query status | `s` in Text/Logs; `S` globally; or `:status` |
| Firmware help | `?` or `:help` |
| Send an eight-column frame | Pixels tab, `w`; or `:frame 0102040810204080` |

Reset preserves the current message, as the firmware does. Applying a new message resumes native repeated scrolling and exits host-frame mode. Resume alone does not exit host-frame mode; use reset or apply text. After a single cycle finishes, firmware pauses with a blank frame; resume can start it again.

## Pixel editor

Press `2`. Move with `hjkl`, toggle a cell with Space or `x`, clear the draft with `c`, and invert the draft with uppercase `I`. `H` opens the 16-hex-digit frame editor. `w`, `s`, Enter or `:send` publishes the draft, with firmware acknowledgement and retry if its frame buffer is busy.

The frame draft is independent of the board until sent. Bytes represent columns left to right, and bit zero is the top row. The UI shows the draft hex and last acknowledged frame. Sending a frame suspends native scrolling; the status header explicitly says **FRAME HELD** rather than RUNNING.

## State, logs and exit

The header shows board-reported scrolling speed, paused state and uptime. Display mode is inferred from acknowledged actions within this session: firmware status does not expose mode or current text. The message pane therefore shows only text confirmed during the session and does not pretend to query the startup message. The pixel grid is a draft, not live framebuffer readback. Status older than eight seconds is marked stale.

Commands are serialized in a background worker; the keyboard and rendering stay responsive during transport waits. UART sends every complete command with LF, including single-key controls, and preserves UTF-8 text. Frame commands retain acknowledgement and bounded `BUSY` retries. Failed or missing acknowledgements show an error, and do not mark a draft as applied. The UI queries status every two seconds when idle. Firmware replies and session errors appear in Logs; `j` / `k` scroll, `gg` selects the oldest retained entries, `G` follows the newest, and Ctrl+U / Ctrl+D move ten lines. The view retains up to 600 entries. Raw transport logs are saved under ignored `build/tui/`.

Quit with `q` or `:quit`. The selected connection is released and terminal settings are restored; UART also restores the serial device's settings. The board keeps the last confirmed state; closing while a host frame is active intentionally leaves that frame displayed. Live edits remain volatile and reset when the MCU restarts. Disconnects wake pending UART waits and are shown in the TUI. The TUI never flashes firmware and does not control the separate UART/I2C test firmware.

## Validation

Host tests cover local Polish text editing, input validation, Vim navigation, frame orientation, playback actions, reset observation, serialized speed steps and rendering at multiple terminal sizes. An actual curses session was exercised through a pseudo-terminal in offline mode. The live TUI was tested on the identified v3 board for text, exact speed, pause/resume, single-cycle arming, frame acknowledgement, reset and help, without flashing. The original sample was restored at 75 ms per pixel and the probe released afterward. These checks establish command/reply behavior; they do not provide optical framebuffer feedback.

The UART transport's host tests use a real pseudo-terminal to check UTF-8 lines, bootstrap status/ping validation, serialized TUI jobs, frame `BUSY` retries, failed acknowledgements, disconnects and restoration of serial settings. On 2026-10-12 an actual curses session using `make tui PORT=...` passed over the existing WCH-LinkE tty: Polish text, exact speed, pause/resume, arm, frame acknowledgement and reset. The user terminal settings were restored on exit and the original sample was left at 75 ms/pixel, unpaused, with zero UART receive errors/drops. The first attempt timed out while picocom was also reading the port; closing that session resolved it. Raw evidence is in `build/tui/20261012-012920-uart.log`, `tty-live-session.txt` and `tty-live-result.json`. Firmware and v4 CAD remained unchanged.


Brightness is available on the PWM-enabled text firmware: press `b` in normal
mode to edit a 0–100 percentage, or use `:brightness 25`. Edits stay local until
Enter. The status bar shows the reported percentage. `0` restores brightness 100
alongside the original speed/mode. Both SWIO and UART transports acknowledge
brightness; older status lines without the field remain accepted. Offline mode
simulates the control. Firmware scan is now 2 kHz / 250 Hz full frames with a
100 µs GPIO-low blank and nominal 10 kHz row PWM.

Brightness percentages use gamma 2.2 in the firmware; the displayed value is
the requested brightness, rather than the raw PWM duty.
