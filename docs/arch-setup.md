# Arch development setup

Build this firmware with a Linux WCH compiler. The existing interrupt handlers use `WCH-Interrupt-fast`, and the old MounRiver configuration uses `rv32ecxw` with `ilp32e`. Keep these settings during the migration.

## Dependencies

On a fresh Arch installation:

```sh
sudo pacman -Syu --needed base-devel git python libusb kicad freecad clang usbutils
```

KiCad, FreeCAD, Make, Python, clangd and libusb were already available on this machine. The system packages do not provide the WCH compiler used by this repo.

## Compiler installation

The local setup uses the MRS 1.90 Linux toolchain from the [ToolchainRepository mirror](https://github.com/ToolchainRepository/MRS_Toolchain_Linux_x64_V1.90), pinned to commit `90064ec81d15b9d42fcc3dc11cd6bf204774ca1c`. This is a third-party mirror of prebuilt tools. The checkout occupies about 2.6 GiB, including its GCC12 and OpenOCD bundles; the build uses its GCC8 bundle.

```sh
python3 scripts/setup_toolchain.py
make doctor
make all-variants -j4
```

The installer keeps everything under `.tools/`, checks the pinned revision, and restores executable bits missing from the mirror. It does not change system packages or shell startup files. It also works with the toolchain already installed here.

For an official distribution, use the Linux download from [MounRiver](https://www.mounriver.com/download). The older direct archive link returned HTTP 403 during this migration. After extracting a compatible WCH toolchain, copy `config/local.mk.example` to `config/local.mk` and set the complete binary prefix:

```make
CROSS_COMPILE := /your/mrs/RISC-V_Embedded_GCC/bin/riscv-none-embed-
```

`make doctor` verifies that the compiler accepts the ISA, ABI and fast interrupt attribute. A replacement compiler must also pass `make all-variants` (active v3 plus the three archives). Changing compilers or command-line flags requires cleaning the affected variants before rebuilding. The existing IDE used `-O0`; the native build retains it.

## Editor setup

```sh
make compdb VARIANT=v3
clangd --check=firmware/v3/User/main.c --tweaks=
```

The generated root `compile_commands.json` contains project and compiler include directories. It is local to this machine. Run `make compdb` again after switching variants, moving the checkout, or changing the toolchain.

`.clangd` substitutes RV32I flags for editor indexing because Clang does not support the WCH ISA extension and RV32E ABI. The firmware build still uses WCH GCC and RV32E. Editor results are useful for navigation and ordinary diagnostics; compiler output is authoritative for interrupt code and target behavior.

The empty `--tweaks=` option disables clangd's optional refactoring tests. Clangd 23.1.1 otherwise reports overlapping replacement errors when testing the register macros in v3. Parsing checks passed for all three entry points with those refactoring tests disabled.

MounRiver project files are retained. Import the `.wvproj` or `.project` from the active project (`firmware/v3/letki_v3_text.wvproj`) or selected archive into the Linux IDE and regenerate its build directory. The old Windows-generated files in `.local/legacy-firmware/` contain drive-letter paths and should remain archived.

## Programmer setup

[minichlink](https://github.com/cnlohr/ch32fun/tree/master/minichlink) supports programming the CH32V003 with a WCH-LinkE. A local copy was built at `.tools/ch32fun/minichlink/minichlink`. For a fresh checkout:

```sh
git clone --depth 1 https://github.com/cnlohr/ch32fun.git .tools/ch32fun
make -C .tools/ch32fun/minichlink
```

The provided rule grants access to a local desktop session for the WCH programmer in RISC-V mode (`1a86:8010`). It uses Arch's systemd `uaccess` support, without requiring a `plugdev` group. Install it when connecting the programmer:

```sh
sudo install -m 0644 config/70-wch-link.rules /etc/udev/rules.d/70-wch-link.rules
sudo udevadm control --reload-rules
```

Unplug and reconnect the programmer, then check `lsusb -d 1a86:8010`. Connect GND and SWIO according to the board schematic, and use the board's intended power supply. `8012` identifies ARM mode in the [upstream rules](https://github.com/cnlohr/ch32fun/blob/master/minichlink/99-minichlink.rules); the CH32V003 requires RISC-V mode.

Once the correct board and variant are selected, this explicit command writes the active v3 text firmware and resumes execution:

```sh
.tools/ch32fun/minichlink/minichlink -w build/v3/letki.bin flash -b
```

Flashing is a separate hardware operation. USB access, writing and readback verification succeeded with the connected WCH-LinkE firmware 2.16 and CH32V003 during the 100 ms strip test. The user confirmed the faster line cycling. The user confirmed the text firmware works. The subsequent SWIO update was flashed and all 5,068 image bytes matched readback. Its status logs and live controls were verified using `minichlink -C linke -T`; see the README for keys. The custom-text update was subsequently flashed and all 6,712 bytes matched readback. Polish message replacement and overlength rejection were tested on the board. Use `python3 scripts/swio_terminal.py` for UTF-8 input; it compiles a local host terminal with unsigned character handling, since the original POSIX reader sign-extends UTF-8 bytes. Opening the terminal restarts the MCU. Close it before flashing or debugging. The root Makefile has no automatic flash target.

## Verification on this machine

The active v3 text firmware and all three archived variants compile and link with WCH GCC8 on Arch. The earlier USART/text/live-frame image used 13,764 bytes of flash sections. Archived v2 uses 7,456 bytes, the old PWM experiment 2,524, and the 100 ms strip test 1,988. Flash figures are text plus initialized data. Active RAM sections occupy 1,744 bytes, including the unchanged 256-byte reserved stack. Host tests cover scrolling, Polish glyphs, GPIO blanking, frame handoff, SWIO backpressure, bounded UTF-8 message editing, exact scroll intervals and USART framing/error/overflow handling. They do not replace a physical display test.

The integrated USART image was flashed and readback verified on the identified existing v3. Live controls on both USART and SWIO passed; 20 exact UART echoes during fast scrolling of 64 Polish characters retained zero receive errors and dropped replies. Working firmware was backed up twice before programming; original and verified readbacks remain in `build/board-readback/text-usart-20261011T230140Z/`. Use `scripts/uart_text.py` for active text firmware; `scripts/uart_demo.py` remains the separate interface-test client. WCH-LinkE supplied nominal 3.3 V through its existing connection; no power or option-byte changes were made. No new optical inspection was performed.

WCH GCC stack-usage reports and leaf library disassembly give a conservative 228-byte sum for the foreground status path plus both interrupt paths, within the 256-byte reservation. The receive ISR only queues bytes; all parsing/output stays in the foreground. Runtime stack high-water usage remains unmeasured. Reports are local artifacts in `build/uart-stack/` and the programming evidence directory.

The separate [interface demo](interface-demo.md) also builds with WCH GCC8. `make interface-demos` produces UART, I2C controller and I2C target images in separate directories, and `make all-variants` includes all three roles. The demo reserves a 384-byte stack; it retains the same 16 KiB flash and 2 KiB RAM limits. Its host protocol, pseudo-terminal and simulated-register tests pass. Physical UART passed on the existing v3 using the WCH-LinkE 3V3 supply and documented serial initialization: 20 exact echoes at 115200 8N1, zero receive errors and zero dropped replies. Full working flash was backed up twice and restored byte-for-byte afterward; the restored text SWIO status passed. Actual rail/baud measurements and two-board I2C remain pending.

The SWIO terminal owns local UTF-8 line editing and runs the probe on a private PTY. Typed text remains visible, and submitted commands are printed with `> `. Press Enter for all commands; Backspace edits and Esc clears the unsent draft. The user's terminal settings are restored on exit.

For text firmware, ordinary text is automatically prefixed with `t `; explicit controls remain commands. Without that prefix in a raw terminal, letters inside a sentence can invoke commands, including `a` which holds the animation at its start. The wrapper displays pause/arm notices and suggests `r` to resume. Its text handling was tested using the user's exact sentence; the interface-demo command protocol remains unchanged.

KiCad 10.0.7 exported netlists and front, back and edge SVGs for all three board projects before archiving the older two under `archive/hw/`. This verifies that the files load; it does not replace ERC, DRC or electrical testing. CLI exports emitted internal enum assertions but completed with the explicit layer options. FreeCAD model file content was preserved during reorganization.


The PWM/brightness text build is `make` (default v3): 15,556 bytes of flash and
1,764 RAM section bytes, including the retained 256-byte stack. WCH stack-usage
analysis including SysTick, TIM2 unblank and USART ISR paths totals 224 bytes;
runtime high-water remains unmeasured. `make VARIANT=v3-pwm-demo` builds the
separate sparse experiment into `build/v3-pwm-demo/`, reusing the active SDK.
Use `make STACK_USAGE=1` to generate compiler stack reports. Status now uses
standard CRLF; PC readers also accept the older LFCR status endings.


## USART reporting repair (2026-10-12)

All active text-firmware reports now use CRLF (`\r\n`): startup, help,
acknowledgements, errors, ping replies and status. Previously only status had
been converted; the other messages still used bare LF. The TUI UART sender
also accepts CRLF or LFCR command suffixes without leaving an embedded newline.
Host PTY tests cover mixed endings, a split CRLF and all four command suffixes.
`make -j4` and `make test` passed.

The repair was flashed on UUID `d7-73-ab-cd-41-3f-bd-ff`; all 15,576 image
bytes matched readback. Two identical full working backups were saved first.
Raw UART help/status/ack/error reports and 20 exact pings passed, including
LF, CRLF and LFCR command input, with zero receive errors and dropped replies.
Final state: original text, 75 ms/pixel, unpaused, brightness 100. Evidence:
`build/board-readback/uart-crlf-20261012T124443Z/summary.json` and `traffic.json`.
This supersedes the previous flashed-image size; PWM and CAD were not changed.


## PCB routing tools

`make pcb-tools` installs the pinned KiCadRoutingTools CLI and Rust engine in
ignored `.tools/`, with local Python dependencies and access to Arch's native
KiCad bindings. Use `make pcb-doctor`, `make pcb-check` and `make pcb-preview`.
Read [the workflow guide](kicad-routing.md) for isolated routing experiments,
source preservation and the supplementary checker's geometry limits.


## Native Wayland renderer

The local C renderer uses Arch packages `base-devel`, `pkgconf`, `wayland`,
`wayland-protocols` and `cairo`; its integration tests also use `python`.
Run `make renderer`, then `make renderer-run BOARDS=5` inside Hyprland.
`make renderer-test` exercises the running native process via its local socket.
For desktop-free testing use `build/renderer/letki-renderer --headless --manual`.
See [the renderer guide](../host/renderer/README.md) for agent controls,
packet/raw-frame input and independent instance sockets. No hardware is opened.

## Native music engine

`make player` builds the C++17 PC engine and the existing C firmware simulator.
The native host dependencies on Arch are `base-devel pkgconf portaudio libsndfile
sdl2 json-c ffmpeg psmisc`; these are separate from the MCU toolchain. No Python runtime
is needed for playback. Run `make player-test` and see
[the player guide](../host/player/README.txt) for recordings, controls, serial
ownership, timing, simulation and physical validation limits.


## Manual text desktop app

`make control` builds `build/control/letki-control`; `make control-run` opens it.
Native dependencies are `gtk4 libadwaita json-c` plus the normal C++ compiler and
pkg-config. Qt is no longer used. The GTK client uses the private Unix-socket
`letkid` service; only that service opens UART. `make control-test` uses the actual
five-node C simulator and Python standard-library integration tests, without
physical UART. `make control-gui-test` needs an active desktop and uses a tracked,
isolated simulator. See [the app/service guide](../host/control/README.md).
No Python/audio runtime is used by Studio or the service. `make control-desktop`
and `make control-service-install` explicitly install per-user desktop/systemd
integration; ordinary builds write only inside the project.
