# UART and two-board I2C demos

Prepared for the v3/v3.1 pin map. The firmware lives in `firmware/interface-demo/`, with its own copied WCH SDK and IDE project `letki_interfaces`. It is independent of the working text-animation firmware in `firmware/v3/`. No hardware was flashed while preparing these demos.

## Current order of work

The user will verify USART to the PC on v3, then I2C across two v3 boards,
before ordering v4. Keep the working text project separate from these test
images. Build commands prepare images; programming is a separate operation.
Record the tested board UUIDs/revisions, actual VCC, adapter model/logic levels,
firmware hashes and complete test output. A host/mock pass does not fill a
physical result. V4's new UART buffers and 3.3 V logic supply require their own
later tests even after the v3 baseline passes.

Use [interface-qualification.csv](interface-qualification.csv) as a blank
recording template. Keep raw measured runs separately; blank rows are untested.

## Build now

```sh
make interface-demos -j4
make test
make compdb VARIANT=interface-demo
```

| Image | Default mode after reset |
| --- | --- |
| `build/interface-demo/letki.bin` | UART only; I2C pins remain inputs |
| `build/interface-demo-controller/letki.bin` | I2C controller/master; automatically sends a counter every second |
| `build/interface-demo-target/letki.bin` | I2C target at 7-bit address `0x32` |

Individual builds use `make VARIANT=interface-demo ROLE=uart`, `ROLE=controller`, or `ROLE=target`. Each role has a separate output directory. All images retain the UART command interface and SWIO terminal. Selecting `mode` at runtime is temporary; reset returns to the image's default mode. IDE builds default to UART unless `INTERFACE_BOOT_MODE` is configured explicitly.

Current images (2026-10-14): UART uses 12,364 flash section bytes and 1,244 RAM
bytes; controller uses 12,412 flash and 1,236 RAM; target uses 12,396 flash and
1,240 RAM. RAM includes the retained 384-byte stack. The demo reserves more
stack than the text firmware because commands nest through peripheral
initialization. Compiler stack-usage reports were inspected; runtime stack
high-water usage remains unmeasured. Fast WCH interrupts, RV32E ABI, 16 KiB
flash and 2 KiB RAM limits are retained.

## First: PC to USART

Use a USB-UART adapter whose TX/RX logic levels are compatible with the board's actual VCC. The board has no UART level shifter. An adapter's selectable power-output voltage does not necessarily change its signal levels; check the adapter specification. Use the board's existing power supply for this test and leave an additional adapter VCC disconnected. When the same WCH-LinkE already supplies the board, retain that existing supply connection and do not add another source or change its power-output settings.

| Adapter | Board |
| --- | --- |
| TX | J3 pin 5, URX / PD6 |
| RX | J1 pin 5, UTX / PD5 |
| GND | J1 or J3 pin 6 or 7 |

Flash the UART demo only when the hardware and intended board are available. Preserve a readback first and verify the connected chip identity. The existing standing flash permission applies only to the already identified v3 board; a new second board needs its own task authorization and identity check. Builds and PC scripts never flash automatically.

```sh
python3 scripts/uart_demo.py --list
python3 scripts/uart_demo.py --port /dev/serial/by-id/YOUR_ADAPTER
python3 scripts/uart_demo.py --port /dev/serial/by-id/YOUR_ADAPTER --command status
```

The script uses Linux termios directly, with no additional Python packages. It sets 115200 baud, 8 data bits, no parity, one stop bit, and no flow control. It sends 20 distinct random ping tokens, checks exact echoes, then verifies that the firmware reported no UART receive errors or dropped output. A successful physical run prints `PASS`. Missing or incorrect replies fail rather than reporting success.

Commands are printable ASCII lines, at most 79 characters, terminated by Enter/LF; CRLF also works:

| Command | Response/action |
| --- | --- |
| `ping hello` | `PONG hello` |
| `status` | Mode, successful/failed I2C transactions, last accepted counter and UART error/drop counters |
| `help` | Command summary |
| `mode uart` | Disable I2C; leave SDA/SCL as inputs |
| `mode controller` | Initialize I2C controller |
| `mode target` | Initialize I2C target at `0x32` |
| `send 42` | In controller mode, queue an I2C transaction; later emit its result |
| `auto on` / `auto off` | Enable/disable automatic one-second counter attempts in controller mode |

The controller image boots with automatic sending enabled, starting at counter
1 after one second. Each attempt advances the counter, including failed attempts;
the displayed counter changes only on success. BUSY defers the next attempt.
`mode controller` selects manual operation and resets success/error counts;
`auto on` resumes at the last successful counter plus one. Mode changes preserve
the last counter. UART and target images boot with automatic sending disabled.
Reset restores the image's boot role and automatic setting. Status adds `auto=0/1`.

The same line commands work in `python3 scripts/swio_terminal.py`. Opening that terminal restarts the board, so runtime role changes are lost. USART and SWIO have separate bounded line parsers; replies are mirrored to both transports. Logging never waits for a host. Overlong/non-ASCII lines and receive errors reject the whole command.

## Second: board to board over I2C

Update 2026-10-14: the second assembled v3 is identified as
`d7-6e-ab-cd-41-3a-bd-ff`. The row/column/pixel scan image was programmed and
all 5,228 bytes verified by readback after two matching full-flash backups.
The user separately authorized and the agent verified PD7 GPIO configuration,
preserving all other option bytes. Live SWIO startup, pause/resume and the
three scan phases passed; after assembly corrections the user confirmed all
LEDs and the complete display work. Board-edge soldering is the next step.
Two-board I2C remains untested. Evidence:
`build/board-readback/second-v3-scan-20261013T220549Z/` (UTC timestamp).

**Assembly update 2026-10-14: the user confirms that neither physical v3
has I2C pull-up resistors fitted.** R11 is 4.7 kΩ from SCL to VCC; R12 is
4.7 kΩ from SDA to VCC. Fit at least one pair on the shared bus before testing.
Do not assume the schematic's resistors are physically installed. Edge
connections are still to be soldered. This does not invalidate the LED scan pass.

Only one WCH-LinkE is needed. Program the boards sequentially, identifying and
backing up each device before writing. Suggested assignments:

| Board UUID | Image/role |
| --- | --- |
| `d7-73-ab-cd-41-3f-bd-ff` (original board) | controller/master |
| `d7-6e-ab-cd-41-3a-bd-ff` (second board) | target at `0x32` |

Program the target first, then the controller; the target runs independently
without a debug connection. During the test retain SWIO on the controller.
Both boards must be powered with compatible rails and common GND; establish
the supply arrangement before connecting them. A single connected programmer
does not automatically power a disconnected target. Firmware preparation does
not authorize flashing the second board with this new image or changing
programmer power settings. See the concise [Polish test procedure](i2c-v3-test.md).

Solder and check the second board first. If it uses the original v3 layout, apply the C1–C3 ground jumper to that board too. Check solder continuity and power rails before the communication test.

Use one controller image and one target image. Connect only these bus signals, using short wires and compatible board supply voltages:

| Controller | Target |
| --- | --- |
| J1 or J3 pin 3, SDA | J1 or J3 pin 3, SDA |
| J1 or J3 pin 4, SCL | J1 or J3 pin 4, SCL |
| J1 or J3 pin 6/7, GND | J1 or J3 pin 6/7, GND |

The design provides 4.7 kΩ pull-ups to each board's VCC, but both pairs are
currently absent. One installed pair gives 4.7 kΩ per line; two installed pairs
give 2.35 kΩ in parallel with a common supply voltage. Actual signal levels and
rise times remain to be checked. Power both boards before bus traffic; do not
connect SDA/SCL to an unpowered board. Decide on the power arrangement explicitly
rather than joining independently powered VCC rails.

For the automatic visual test no UART adapter or command is required: the
controller starts sending at boot. With the target running, compare the bottom
two rows on both displays. Optional controller logs are available through
`python3 scripts/swio_terminal.py` using the one WCH-LinkE. Opening that terminal
restarts only the attached controller and restores automatic sending.

For a manually driven PC test, keep the UART adapter connected to the controller
as above. The helper selects `mode controller`, which disables automatic sending.
With the target running, execute:

```sh
python3 scripts/uart_demo.py --port /dev/serial/by-id/YOUR_ADAPTER --i2c --count 20
```

At 100 kHz, the controller writes a four-byte packet: marker `0xA5`, counter low byte, counter high byte, then CRC-8 (polynomial `0x07`, initial zero). The target validates the packet at STOP and updates its displayed counter. The controller then reads one byte containing the target's computed CRC and checks it against the sent packet. Both boards report `I2C OK counter=N` on successful transactions; failures report NACK, timeout, bus error or incorrect CRC. CRC confirmation is a simple demonstration check, not a full production protocol.

The LED matrix keeps refreshing at 125 Hz. The top-left pixel is a ready
indicator; the next column shows one top pixel for controller mode and two for
target mode. In the first column, row three lights after a success and row four
lights after any failure since boot/mode reset. Error indication remains lit
even after recovery. The bottom two rows show bits 0–7 and 8–15 of the last
successfully confirmed/received counter, left to right. Matching changing
counters on both boards provide a visible result; a target success alone is
not proof that the controller received a valid reply.

I2C work is polled in the foreground, with a 100 ms transaction deadline and no infinite peripheral waits. A failed transaction resets the peripheral and leaves the command interface responsive. The demo does not implement clock-pulse recovery for a physically stuck bus; fix the wiring/device condition before retrying. The one-byte receive sequence disables ACK before clearing ADDR and generates STOP before reading RXNE. Peripheral setup follows the [WCH I2C example](https://github.com/openwch/ch32v003/blob/main/EVT/EXAM/I2C/I2C_7bit_Mode/User/main.c); pin assignments follow the [WCH USART configuration](https://github.com/openwch/arduino_core_ch32/blob/main/variants/CH32V00x/CH32V003F4/variant_CH32V003F4.h).

## Verification limits and return to the text demo

All seven build configurations passed: active text firmware, three interface roles and three archived variants. The new project compiled without warnings; archived v2 retains its two unused-helper warnings. Host tests cover UART framing and fragmented serial replies through a pseudo-terminal, exact-token rejection, timeouts, all 65,536 counter values with single-bit corruption, and simulated I2C register transitions for success, wrong CRC, NACK and timeout. Mock register tests exercise software control flow; they do not prove real peripheral timing or electrical behavior. Clangd checks of the demo entry point and bus driver passed.

During initial preparation there was no USB-UART adapter or second board available. The physical UART run below establishes communication on one v3 board; independent baud/waveform measurements, I2C waveforms, target behavior and physical counter confirmation remain unverified.

## Physical USART-to-PC run: 2026-10-12

The original v3 board identified as CH32V003 UUID `d7-73-ab-cd-41-3f-bd-ff`, with 16 KiB flash and read protection disabled. Its existing WCH-LinkE (firmware 2.16, USB serial `02858F0687B7`) supplied the board from its **3V3 pin**, as confirmed by the user. The actual rail and signal voltages were not measured. RX/TX were connected to MCU UTX/URX with the existing common ground; no programmer power or option-byte commands were used.

The v3 schematic has direct PD5/PD6 UART connections. WCH's standard CH32V305F-based LinkE schematic connects UART TX/RX through 270 Ω resistors to PB10/PB11 at a 3.3 V I/O supply; PB11 is an FT input. This supports the reported 3.3 V connection. The LinkE hardware revision was not independently inspected. Sources: [WCH Link schematic](https://www.wch.cn/downloads/WCH-LinkSCH_PDF.html), [WCH CH32V003 datasheet](https://www.wch.cn/downloads/CH32V003DS0_PDF.html), and [WCH CH32V30x datasheet](https://www.wch.cn/downloads/CH32V20x_30xDS0_PDF.html). A mirrored copy of the manufacturer's schematic was retained with the raw evidence because the current download endpoint failed.

Two independent full-flash backups matched each other and the prior verified `ch32v003-live-frames.bin`. The UART image's 11,856 bytes matched physical readback. The successful run returned 20 distinct exact ping echoes at 115200 8N1, with this status both before and after traffic:

```text
STATUS mode=uart ok=0 fail=0 counter=0 uart_errors=0 tx_dropped=0
```

Earlier attempts rejected the first command. One subsequent run echoed all 20 tokens but retained three receive errors from the initial exchange, so it failed acceptance. Initializing the LinkE serial channel before starting the UART image avoided this behavior in the successful run. The exact adapter startup mechanism remains undetermined; this is a pass for the recorded sequence, not a cold-open qualification.

For the successful sequence, the serial channel was configured at 115200 and sent one LF while the **text firmware was still running and did not process USART input**. The port was then closed while retaining the baud settings, before any probe operation. The UART image was programmed, read back and restarted; opening the serial port afterward and waiting 300 ms before sending produced the zero-error run. The preparation used the existing host helper:

```sh
PORT=/dev/serial/by-id/usb-wch.cn_WCH-Link_02858F0687B7-if01
python3 - "$PORT" <<'PY'
import os, sys, time
sys.path.insert(0, "scripts")
from uart_demo import SerialLink
link = SerialLink(sys.argv[1])
link.send("")  # LF only; active text firmware ignores USART.
time.sleep(0.3)
os.close(link.fd)  # Retain 115200 settings for the following UART test.
PY
```

This preparation does not flash. Keep all serial/SWIO sessions closed during probe operations. The previous host serial settings were restored after testing. Firmware error counters were never cleared to obtain a pass.

Afterward, all 16,384 restored flash bytes matched the working backup. The restored text banner and SWIO status were verified (`speed_ms=75 paused=0`); no new optical inspection was performed. All ten recorded v4 CAD source hashes stayed unchanged. Two-board I2C remains untested.

Local raw evidence, including unsuccessful runs, is in `build/board-readback/uart-pc-20261011T224020Z/`; `attempt-3/traffic.log` and `attempt-3/result.json` record the successful run. SHA-256 hashes:

| Artifact | SHA-256 |
| --- | --- |
| Full working flash backup | `a8128461188f490018715a84153c45615afec4732fa999cb71debe1c3262d357` |
| UART image | `297db3610647af712f14061b4889524e88c9e55392fdfa4f1aeb0b1a9b8c7c4b` |

To return to the existing text/TTS workflow, build `make VARIANT=v3`, select `make compdb VARIANT=v3`, and explicitly flash the verified text firmware when appropriate. The prepared interface images do not replace the firmware currently running on the board.

USART controls were subsequently added to the active text firmware and flashed/readback verified on the same board. Use [the active USART controls](../README.md#usart-text-controls) and `scripts/uart_text.py` for that application. The separate demo images, command protocol and `uart_demo.py` remain unchanged. The working pre-USART text readback and both tested integrated images are preserved in `build/board-readback/text-usart-20261011T230140Z/`; the board now runs the integrated text application.

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
