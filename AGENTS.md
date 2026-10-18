# Working on Letki

Start with `README.md` and `docs/README.md` for navigation. Dated development
records are retained; use `docs/current-state.md` and the latest applicable entry
when historical status paragraphs conflict. The media/TV host is the last planned
system component, not the end of development.

JLCONE access preference (user-confirmed 2026-10-17): prefer the temporary
loopback-only debugging/CDP method in `docs/jlcone-shipping.md` over desktop
clicking/screenshots for supplier quotes, coupons and cart inspection. Reuse
an appropriate active session, avoid logging credentials/session tokens/personal
addresses, and end debugging access when finished. This does not authorize
paid orders or messages to suppliers.

Reusable PCB creation/routing guidance and assessed tool outcomes are global in
`/home/pies/.local/share/electronics/skills/pcb-workflow/SKILL.md`. Shared shelf
accounting is in the adjacent `shelf-inventory/SKILL.md`, with canonical data at
`/home/pies/.local/share/electronics/inventory/`. Letki's stock/incoming/storage
and order-provenance config paths link there. Keep the current v3 assembly reservation and
the separately recorded v4.1 shelf planning allocations distinct. The global
workflow does not replace the board-specific checks, rules or permissions below.

Read `README.md` for the active v3 project and `docs/arch-setup.md` for toolchain setup. `docs/tts-demo.md` covers the current native-rate speech demo and selected synchronization points. The board has an onboard CH32V003 and 74HC138 decoder. Run commands from the repository root.

Read `docs/current-state.md` before procurement or hardware handoff work. It
records the selected five-board v4.1 batch, placed TME order, saved JLCPCB cart,
actual assembly substitutions and archive locations. Historical draft shopping
lists and old status paragraphs do not supersede these current records.

## Attachment architecture context (2026-10-17)

The user's 2026-10-18 prototype sequence is in
`docs/x035-bringup-plan-20261018.txt`: LinkE/USB setup, USB-UART proxy,
I2C logging/gyro animation, fast ESP SPI, then PD voltage tests. Hardware is
not prepared yet; this is a plan. ESP SPI supersedes the earlier UART link.
PC USB powers the initial WeAct prototype; integrated PD/PC VBUS stay separate.

When the user mentions the converter, dongle, X035 or Wi-Fi attachment, read
`docs/attachments-study-20261017.txt` for the agreed architecture and open
questions. Develop two boards independently: a custom CH32V007 buck (converter
design is required learning for classes, with multiple iterations expected),
and a CH32X035 communication dongle with an ESP-12F/ESP8266 Wi-Fi peripheral.
X035 acts as a generic display host, USB-PD negotiator and I2C supervisor of
V007; PC USB can expose converter settings/telemetry for testing. V007 owns
local regulation and protection. Use X035, not X033, for integrated PD.

Focus on v3.2. Its firmware is developed independently and speaks generic
UART/I2C protocols; it must not depend on the host being X035. Preserve existing
VCC/GND edge connections: one buck powers the continuous 3.3 V rail, optionally
through multiple feed points from that same output. Do not assume independent
converter outputs can be paralleled. The buck starts autonomously from initial
USB-C 5 V, powers X035/ESP/display at 3.3 V, then maintains 3.3 V through higher
PD input negotiation. V007 startup bias and limited startup load need design.
PC USB is for data, not array power. A roughly 60–65 W PD charger is a provisional
input budget, not a selected purchase or qualified converter/output rating.
Topology, final limits, pin mapping and I2C bus ownership remain open.

Initial SWIO wiring/programming is handled manually by the user. Subsequent
updates follow Wi-Fi -> ESP -> SPI -> X035 -> I2C -> tile loader; updating is
a maintenance feature, not the main objective. The loader remains a proposal.
Existing v3 streaming passed at 230400 baud; 115200 is recovery/default,
460800 failed its qualification and 921600 is unqualified. Do not impose these
as v3.2 speed limits or claim X035 throughput has been tested. This architecture
record authorizes no new flashing, purchases or CAD changes by itself.

## Commands

```sh
make doctor
make -j4
make test
make all-variants -j4
make compdb
clangd --check=firmware/v3/User/main.c --tweaks=
python3 scripts/preview_text.py
```

V3 is the default. Outputs go to `build/v3/`. For a missing compiler, run `python3 scripts/setup_toolchain.py` or configure `CROSS_COMPILE` in ignored `config/local.mk`. Clean affected variants when changing compiler or flags. Preview generation requires Pillow.

`firmware/interface-demo/` is a separate UART/I2C test project with its own SDK and IDE name `letki_interfaces`; read `docs/interface-demo.md`. `make interface-demos` builds UART, controller and target roles into separate `build/interface-demo*` directories. `make all-variants` includes all three roles and all archives. The demo reserves a 384-byte stack; active text firmware retains 256 bytes. Never flash interface firmware as part of a build or claim physical validation from host mocks. Physical UART passed on the identified v3 with WCH-LinkE at nominal 3.3 V after serial initialization: 20 exact echoes at 115200 8N1, zero receive errors/drops. First-command startup failures and the successful preparation sequence are recorded in `docs/interface-demo.md`; actual rail/baud measurements remain pending. The full working firmware was restored and verified, with text SWIO status checked. Two-board I2C passed 20 physical CRC-confirmed exchanges on 2026-10-14; see the latest verification section. All v3 boards have standing firmware-update/test authorization as of 2026-10-16; identify each connected board and preserve readbacks before updates. See the current authorization below.

## Firmware changes

- Active application code belongs in `firmware/v3/User/`. `main.c` owns the sample and scroll interval; `display.c` owns board wiring and refresh; `font.c` and `text.c` own glyphs and frames; `brightness.c` stages bounded 0–100% brightness commands; `swio.c` owns the nonblocking minichlink transport; `message.c` owns UTF-8 input and bounded message buffers.
- `uart.c` owns active USART1 at 115200 8N1 on PD5 TX/PD6 RX. Its WCH fast RX ISR only queues bytes/error flags into a 64-entry fixed FIFO; parsing, replies and TX polling stay in the foreground. `uart_line.c` stages complete UTF-8 lines separately from SWIO. Require Enter for USART controls and explicit `t TEXT`; never pass unprefixed text as raw keys. UART commands must not corrupt a pending SWIO edit. Reject damaged/overlong lines and preserve active text. Overflow markers follow the queued prefix; do not move them ahead of older terminators. TX uses a 128-byte nonblocking queue and may drop whole replies. Status adds UART error/drop counters without providing message/framebuffer readback. Use `scripts/uart_text.py` for text firmware and retain `uart_demo.py` for the separate interface images.
- The active USART/text firmware was flashed and readback verified on UUID `d7-73-ab-cd-41-3f-bd-ff`; original working flash was backed up twice. Polish text, 64-character bounds, invalid input, speed/pause/arm/frame controls and 20 exact pings during fast scrolling passed with zero UART errors/drops. SWIO controls and the PC UTF-8 helper also passed; the original sample was left scrolling at 75 ms. Evidence is in `build/board-readback/text-usart-20261011T230140Z/`. Nominal 3.3 V comes from the existing LinkE 3V3 connection; rail voltage, optical behavior and runtime stack high-water were not newly measured. Keep the 256-byte stack reservation: current sections use 13,764 bytes flash and 1,744 bytes RAM including stack; the assessed foreground plus both ISR paths sum to 228 bytes.
- Preserve vendor notices, WCH fast interrupt attributes, RV32E ABI, startup code and linker limits unless specifically changing them. The target has 16 KiB flash, 2 KiB RAM and a reserved 256-byte stack. Include ISR call depth when assessing stack usage.
- The PCB decoder selects cathode columns S1–S8, left to right. Its A0/A1/A2 inputs are PC7/PC6/PC5. Anode rows D8–D1 run top to bottom: PD7, PC0, PD3, PD4, PC4, PC3, PA1, PD2. Font bit 0 is the top pixel. Preserve PD1 for SWIO.
- Active text firmware scans at 2 kHz / 250 Hz full frames, independently of animation, with nominal 10 kHz hardware row PWM. SysTick keeps milliseconds by counting pairs of scan ticks. Rows are driven-low GPIOs before column changes; TIM2 update ends a 100 µs blank without busy waiting, returning only lit rows to AF/PWM. Preserve PD1, PD5/PD6, PC1/PC2 and button pins. Fixed double buffers and requested brightness latch at full-scan boundaries. `display_tick` runs only in SysTick; `display_unblank` runs only in TIM2 IRQ. Keep all commands/logging foreground. The separate interface demo retains its 1 kHz/125 Hz GPIO scan.
- Use `make test` for scrolling and simulated GPIO sequencing. The GPIO test compiles the real driver against a register mock; it does not establish electrical behavior. For changes in shared build logic, also build all archived variants with `make all-variants`.
- Regenerate `compile_commands.json` for the selected variant. Clangd uses approximate RV32I settings for indexing; WCH GCC is authoritative. Use `--tweaks=` for CLI checks because clangd 23.1.1 has refactoring test failures on the archived register macros.
- Keep `.cproject`, `.project`, `.wvproj`, `.launch` and `.template` consistent when changing IDE metadata. The active IDE project is `letki_v3_text`.
- Build and inspect the preview for font or animation changes. Report hardware validation limits honestly. The user confirmed text rendering works. The SWIO update has been flashed and readback verified; live commands and logs were tested. The custom-text update was flashed and readback verified; Polish messages and overlength rejection were tested. All prior working readbacks are preserved.

- Keep SWIO polling, command handling and logging in the foreground. Preserve nonblocking behavior with no terminal connected. Logs may drop whole messages when the 128-byte queue is full. Close the terminal before other probe operations. Live speed/pause/text changes are volatile, not flash settings. Custom text has a 64-character limit; incomplete or invalid input must preserve the active message. Use `scripts/swio_terminal.py` for Polish input: it builds minichlink with unsigned character handling without modifying downloaded sources.
- The interactive SWIO wrapper displays and edits UTF-8 commands locally, and sends them only after Enter (including single-key commands). It echoes submitted commands with `> `, preserves drafts across incoming logs, and gives the probe a private PTY. Esc/Ctrl+U clears the local unsent draft; Ctrl+C exits and restores terminal settings. This changes only the host wrapper; automated `SwioLink` still uses the firmware's immediate byte commands. Visible Polish input and text/status replies were tested on the identified board without flashing.
- After identifying the text-firmware banner, the wrapper prefixes ordinary text with `t ` while retaining explicit controls; interface-demo line commands are sent unchanged. Do not forward unprefixed text as raw byte commands: the `a` in a sentence arms/pauses the native scroll. A reported frozen first letter was captured in RAM as `paused=1`, with the original message intact, and traced to unprefixed input. The wrapper announces paused/armed status and `r` resumes.
- `make tui` opens `scripts/letki_tui.py` with SWIO by default; `make tui PORT=/dev/ttyACM2` or `--port`/`--tty` selects the same TUI over USART. `make tui-demo` is an offline preview. Read `docs/tui.md` for Vim bindings and feature coverage. `uart_link.py` supplies the acknowledged 115200 8N1 connection and restores tty settings on close. UART verifies status and a random ping, not chip UUID, and does not send a restart command. Close other apps reading the selected serial port (picocom was observed consuming replies during an initial live connection attempt). All edits stay local until applied; a background worker serializes acknowledged commands. Show host-frame mode explicitly, and do not claim current-text/framebuffer readback: firmware status exposes speed, pause, uptime and UART diagnostics. Quit releases the selected connection but preserves the board's last state. The TUI targets active text firmware, not interface-demo firmware.
- The TUI's live UART session passed for Polish text, speed, pause/resume, arm, frames and reset after picocom was closed; user tty settings were restored, the original sample was left at 75 ms and UART errors/drops stayed zero. Host PTY tests cover serial cleanup, disconnects, acknowledgements, frame retries and worker serialization. Evidence is in `build/tui/tty-live-result.json` and its referenced log. This host change did not reflash firmware or modify CAD.

- Active speech demo: `.tools/native-tts/bin/python scripts/tts_native.py`, configured by `config/native-demo.json`. Supertonic runs on CPU with native duration control. Do not apply waveform time stretching: the user rejected its sound. The SDK floor extension to 0.6 is local to this script; its normal supported floor is 0.7.
- `f` followed by 16 hexadecimal digits and Enter publishes an eight-column frame. Invalid frames preserve the current display. Host frames suspend the native scroll; `t` or `0` returns to it. Preserve the paired buffers and scan ISR.
- Keep the earlier ROCm environment intact; never replace its Triton with a CUDA variant when installing alignment tools. Current alignment uses CPU Whisper. Keep generated audio, caches and alignment metadata ignored.
- Synthesize complete natural phrases before opening the probe. Use a fixed caption interval and pause audio only at configured synchronization points; do not re-synthesize separate words. The user rejected word-by-word and fast continuous demos. Current settings are native speed 0.65, captions 55 ms/pixel, anchors after ADAŚ/JEST/BABY. Keep the text continuous, using the compact font with two-pixel spaces. Restore the original message after playback.

## Archives

`archive/firmware/` contains `v2`, `v3-strip-test` and `v3-pwm-experiment`. They retain their source and metadata as historical snapshots. `archive/hw/` contains earlier board designs. Do not port new application changes into these archives or enable old PWM experiments as incidental cleanup. Archived variants build with `make VARIANT=<name>` into `build/archive/<name>/`.

## Hardware changes

- Cost minimization is a primary project requirement, explicitly confirmed by the user. Keep the inexpensive CH32V003 and low-cost supporting components as the baseline. Solderable/castellated board-edge connections avoid purchased connectors; alternatives may be considered only with a total-cost comparison. Verify any special castellated fabrication charges rather than assuming all half-hole processes are free. Four layers are intentional because JLCPCB prices compact boards favourably at this size; do not assume a two-layer redesign saves money. Compare BOM, fabrication options and assembly charges before adding dedicated drivers, protection ICs or pricier packages. Meet electrical limits through the least costly adequate design; low cost does not justify violating ratings. Exact sourcing and prices must be verified before release.
- The user permits Astra subagents for demanding work but wants delegation minimized to cut cost. Use narrowly scoped reviews when they resolve a substantial uncertainty; avoid routine delegation, broad parallel work or unnecessary full-history forks. Three narrowly scoped read-only Astra electrical reviews covered the initial circuit, supply/UART and HCT current budget. One later bounded routing task resolved difficult signal escapes in an isolated copy; root completed ground and manufacturing corrections.
- V4 is in `hw/ledkiv4/`; read its README and `docs/v4-design.md`. It is now a fully routed prototype candidate with zero ERC/DRC/open-net/schematic-parity findings, not a production release. Orange LEDs are XL-2012UOC/C965813. The decoder is Nexperia 74HCT238PW,118/C547472, with TI HCT244 buffering, MOSFET sinks, 1.2k row resistors, 3.3 V regulator, buffered UART, head-only 2.2k I2C pulls and optional USB-C/TPS2553 head (33k limit resistor, regulated 5 V 1 A). Dimensions are 40.64 × 49.27 mm; USB lands/edge were checked against the manufacturer drawing. Ground regions are joined by traces/vias, with no open ground nets. All PCB checks and ERC footprint/electrical checks are enabled; no exclusions. Three standard ERC style/unused-simulation defaults are documented in the design brief and package manifest. The exporter rejects unexplained ignored checks. Local footprints and `.kicad_dru` retain fabrication rules. Do not replay creation/placement/routing-seed helpers on the routed source. `v4_bom.py` and `v4_cost.py` generate prototype quantities/costs; user defaults to five boards and wants a twenty-board comparison. The 2026-10-12 snapshot has stock for all selected parts; recheck at checkout. Physical, optical, power, mechanical and production-process qualification remain; do not call this production ready or the prototype worksheet a final release list. Preserve all v3/v3.1 sources and user CAD changes.
- The former ground-repair-only v3.1 is archived in `archive/hw/ledkiv3.1-ground-repair-20261014/` and will not be produced. The user reassigned v3.1 to a new rework using v3 parts and selected v4 features. Its independent design session is in `build/sessions/v3.1-design/`, with candidate CAD under its `hw/ledkiv3.1/`; the main-project path is reserved for a reviewed handoff. V3 remains archived in `archive/hw/ledkiv3/`; physical v3 boards require the documented C1/C3 GND repair. Preserve archived CAD and the v3 firmware baseline. The new rework is not released for fabrication; the seed retains unresolved DRC findings. Edit KiCad source files and `.FCStd` diffuser models only when the task involves the hardware. Avoid rewriting CAD files during firmware or documentation work.
- Preserve user changes in binary CAD files. Never replace a modified model with a Git version merely to make status clean.
- `hw/ledkiv3-ground-demo/` is a working repair demonstration copied from the archive, not a successor revision or fabrication release. `scripts/pcb_ground_demo.py` edits only that open project through the official IPC API and groups the repair into one undo operation. Keep the archive intact. Local bindings are in `.tools/kicad-api/`; the API server is enabled in KiCad preferences. Other existing DRC findings remain unresolved.
- Fabrication exports belong in `hw/<board>/exports/`, and diffuser exports beside their models. They are ignored. Use `build/hardware/` for temporary checks. Archived hardware follows the same source-only tracking policy.
- Run applicable ERC or DRC for design changes, distinguishing existing violations from new ones. Exporting a board only verifies it loads.
- Obtain explicit task authorization before flashing boards outside the standing authorization below, separate erase operations, changing option bytes, powering hardware through a programmer, or ordering boards. Ordinary builds must not program a device. Preserve original and verified readbacks in `build/board-readback/` when testing new firmware.
- On 2026-10-16 the user explicitly extended standing authorization to ALL v3 boards: prepare and execute v3 test procedures, flash application/diagnostic firmware and restart boards without asking for permission again, including newly assembled v3 boards. This supersedes the earlier two-UUID restriction. Identify the connected board, preserve matching full working flash backups before updates, and verify programmed-image readback. Known UUIDs: original/left `d7-73-ab-cd-41-3f-bd-ff`, second/right `d7-6e-ab-cd-41-3a-bd-ff`, third `d7-69-ab-cd-41-35-bd-ff`. Third-board PD7 GPIO configuration was separately authorized and verified on 2026-10-16. The blanket flash/test permission does not extend to new option-byte changes, programmer power changes, separate erase operations, purchases or other PCB revisions. Ordinary builds still do not flash. A CAD/planning-only session remains scoped to its task.

- V4 mechanical sources are in `hw/ledkiv4/mechanics/`; the initial optical-only model is preserved in `archive/hw/ledkiv4-optical-initial/`. The board has two 2.2 mm M2 NPTH holes, an optional vertical Molex 53047-0310/C122442 with bare SWIO pads in parallel, and a removable grid/face/bezel/carrier prototype. `config/v4-mechanics.json` records nominal dimensions; `scripts/v4_mechanics.py` generates print-oriented meshes and checks nominal/STEP interference. The 0.6 mm SWIO PTH holes are a fabrication-tolerance adaptation requiring real fit, pin protrusion and hole-fill qualification. Local connector STEP models are conservative body envelopes. Physical print/optical/retention tests remain pending. Do not replay `v4_mechanical_eco.py` or connector footprint revision helpers as routine regeneration on reviewed source; package exports must not mutate CAD.
- Hardware sequence: physically verify USART to PC and two-board I2C on v3 before ordering v4. The user confirmed no v4 PCBs are ordered yet. Keep the working text application and separate interface test images accessible through stable existing commands. V3 tests establish a baseline and do not qualify v4's new UART buffers, 3.3 V logic supply or complete chain. Builds do not flash; identify boards and preserve readbacks for explicitly requested physical programming/tests.
- User shelf stock is in `config/parts-stock.csv`, with receipt provenance/consumption assumptions in `config/parts-stock-source.json`. One v3 board is deducted; uncertain debugging losses allow conservative 47 MCUs and 936 orange LEDs. Use `v4_cost.py --inventory config/parts-stock.csv` for separate stock-adjusted five/twenty-board lists. Only exact LCSC/MPN matches are credited automatically; switch/capacitor or logic-family substitutions need review. Counts are estimates, not a physical stocktake. Reserve parts for the planned second v3 board explicitly before final buying.
- Purchasing preference: magazine filling is soft; optimize total spend, price breaks and reusable stock. The user favours 1,000 common resistors for roughly $1.50 even with tight packing. `config/smd-storage.json` records Printables model 580643, confirmed capacities and editable draft stocking heuristics; these are not hard budgets. XL-2012UOC fits 500 per magazine tightly in flexible plastic tape; paper tape is harder to pack and other capacities await checks. `v4_cost.py --magazines config/smd-storage.json` compares all tiers without enforcing magazine multiples, shows minimum-cash alternatives/extra spend and suggests inexpensive resistor stock. Never infer capacity from package size alone.

## Repository care

Check `git status` before work and preserve unrelated changes. `.local/` contains old Windows builds, IDE state and CAD backups; `.tools/` contains downloaded third-party tools. Do not inspect or rewrite them as project source, delete them as routine cleanup, or commit them.

Deleted reference PDFs and the modified v3 diffuser predated the migration. Do not restore or discard them without task context. Avoid committing generated firmware, previews, compiler databases, CAD backups or machine-specific paths. Keep documentation current when changing layout, build commands, variant status or hardware test results. Do not commit or push unless requested.


## PWM/brightness verification (2026-10-12)

The user explicitly requested pin checks, a flashed PWM experiment and then a
brightness-capable text firmware upgrade. `firmware/pwm-demo/User/` is a separate
sparse experiment reusing v3 SDK/startup/linker files; build with
`make VARIANT=v3-pwm-demo`. Never revive or edit the historical PWM archive for it.
The default WCH TIM1/TIM2 channel mappings cover all eight v3 row pins. PD7's
existing option byte already selects GPIO; SWIO PD1 and complementary outputs
were preserved, with no power/option-byte changes.

All eight digital pad observations passed at 0/25/50/75/100% on the identified
board. The row sweep exercised all 64 LED positions. The user reported previous-row
pixels leaking into the next column; GPIO-low blanking and selectively returning
lit rows to AF/PWM resolved the reported ghosting. The upgraded scrolling text
was then confirmed visually correct by the user. External waveform/current/rail
and runtime stack high-water measurements were not performed.

Active firmware was flashed and all 15,556 image bytes matched readback; original
working flash has two identical 16 KiB backups. UART valid/invalid/cancelled
brightness input, pause/resume, Polish 64-character text, frames and 20 exact
pings under fast scrolling passed with zero UART errors/drops. The UART TUI
worker and SWIO brightness controls passed; no new interactive curses session
is claimed. `b 0..100` requires Enter, preserves state on invalid/incomplete input,
and is volatile; `0` restores brightness 100 and speed 75. TUI `b`/
`:brightness` covers the feature. PC parsers accept CRLF and legacy LFCR status
replies; a fast-following acknowledgement timeout was traced to a leading CR
from the former LFCR format and has a regression test.

Final state is the original sample at 75 ms/pixel, unpaused, brightness 100.
Evidence/backups: `build/board-readback/pwm-20261012T111419Z/summary.json` and
referenced logs/readbacks. RAM sections use 1,764 bytes including the retained
256-byte stack; conservative foreground plus all three ISR paths totals 224.
All v4 CAD/source hashes remain unchanged. WCH manual v1.9/datasheet v1.3 vendor
copies are saved in `docs/reference/wch/`, recovered from repository history;
the direct download attempt did not return PDFs. Do not claim latest revisions.


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


## Gamma brightness (2026-10-12)

Active `display.c` maps requested 0–100 brightness through a flash-only
101-entry gamma 2.2 table to 0–1200 PWM ticks, clamping nonzero settings to
at least one tick. Timer prescalers now use nominal 12 MHz, ARR 1199; 10 kHz
PWM, 100 µs GPIO-low blanking and 250 Hz frame scanning are preserved. Status
reports the requested percentage. Only the active driver is gamma corrected;
the sparse diagnostic experiment intentionally remains linear. Host tests cover
all settings on all eight channels, monotonicity, zero/full duty and mid-scan
updates. Driver ISR stack sizes remain unchanged. `make` and `make test` passed.

The image was flashed on the identified authorized v3 and all 15,792 bytes
matched readback, after two identical full backups. Live USART brightness
0/1/5/10/25/50/75/100 and 20 exact pings passed with zero errors/drops.
Evidence: `build/board-readback/gamma-20261012T125521Z/summary.json`.
Final state: original text at 75 ms/pixel, unpaused, brightness 100. New optical
linearity/waveform measurements have not been performed. No CAD changes.


## Standalone visual demo (2026-10-12)

`firmware/visual-demo/User/` contains a separate RAM-conscious radial-wave app.
Build with `make VARIANT=v3-visual-demo`; default remains text v3. Shared
`display.c` uses `DISPLAY_LEVELS` only for this variant: two fixed uint16_t
64-pixel buffers, foreground gamma/global scaling and scan-boundary swaps.
Text builds retain binary buffers and their current behaviour. Keep synthesis
in foreground, 100 µs GPIO-low blanking and SWIO/UART pins preserved.
`wave.c` has fixed flash radius/cosine tables; no float or dynamic allocation.
Read `firmware/visual-demo/README.md` for controls and validation limits.
Preview via `scripts/preview_wave.py`; host tests include actual command paths
and UART-help isolation during a SWIO brightness edit.

The final standalone demo was flashed/readback verified on the authorized v3
UUID, with 11,856 image bytes and 1,492 RAM bytes including the 256-byte stack.
Conservative foreground plus all ISR stack paths totals 208 bytes; runtime
high-water remains unmeasured. Full pre-demo text backups are in
`build/board-readback/visual-20261012T130346Z/`; final evidence is in
`build/board-readback/visual-20261012T130609Z/`. All variants and host tests
passed; the text image hash is unchanged. The board is left running the wave
at 45 ms per step, brightness 100, unpaused. No CAD changes.


## V4 symmetric wire contacts (2026-10-12)

The previous offset-hole revision is preserved in
`archive/hw/ledkiv4-offset-wire-20261012/`; earlier flat pads are preserved in
`archive/hw/ledkiv4-flat-pads-20261012/`. Active v4 uses the shared
`EdgeWire_1x07_P5.08mm_D0.8mm` single-PTH footprint. Seven Y positions
7.62/12.70/17.78/22.86/27.94/33.02/38.10 mm lie between actual LED rows;
left/right X are 1.27/39.37 mm. Every staple span is 2.54 mm on abutting boards.
Drill 0.8 mm, wire 0.5 mm. Native FRONT_INNER_BACK padstack: rear oval
2.04×1.6 mm, front/inner round 1.4 mm, no paste. Keep that per-layer geometry
and solid ground-plane attachments. No half-hole/edge-plating process.

J1/J3, TP8 (3.3,39.4), JP1 (36.2,3.2), JP2 (36.2,5.74) moved; all other
130 placements and 351 nonconnector pad nets/sizes were preserved. Ten new
0.6/0.3 ordinary through vias are tented. Uniform mirrored contact legends
and full LED body silk are intentional. Keep the 2 mm front VCC bus and
1.2 mm rear rails/contact feeds; the native geometry checker binds them.
Ten numeric rear TP labels remain unique and PCB_ONLY, excluded from purchases,
placement and paste. Their maps/positions are in `config/v4-mechanics.json`.

Closed solder hoods are necessary on optical separator centre-lines:
0.8 mm cavity radius/depth, 0.4 mm opaque walls/roof. Front protrusion ≤0.5 mm;
solder envelope radius 0.75 mm/height 0.6 mm. One/four-tile models verify
nominal clearances only. Physical solder/print/probe/optics still need trials.

The cost script credits conservative stock after reserving a second v3 board.
The package includes stock-adjusted BUY-5/BUY-20 import CSVs, separate optional
probe cable lists, quote snapshots, wire-staples/testpoints and mechanical
configuration. No orders or flashing happen during exports. V3 USART passed;
its planned two-board I2C remains the pre-order gate.

## KiCadRoutingTools workflow

Read `docs/kicad-routing.md`. `make pcb-tools` installs pinned v0.23.0 under
ignored `.tools/`; `make pcb-doctor`, `make pcb-check`, `make pcb-preview` use
`scripts/kicad_routing.py`. It is CLI integration, with no MCP or external AI
client. Use it for supplementary checks/previews and difficult scoped signal
routes in isolated `build/hardware/` copies. No automatic source promotion.
Exact net names only; preserve input copper, ordinary vias, power widths,
In1 plane, existing rules/severities and immutable source hashes. Inspect
all logs and run official ERC/DRC/parity, circuit/geometry and placement audit
before promoting any route. Never route the whole reviewed source as cleanup.

First use found two UART cap-overlap joins; root repaired exact centre-line
connections. Supplementary redundant-copper findings, multi-loop courtyard
aggregation and native per-layer padstack approximations are documented;
`pcb-check` currently exits nonzero for these extra findings despite a clean
KiCad/native geometry result. Keep them visible, do not suppress or claim all
upstream instruments passed. This tool does not establish physical qualification.

Visual follow-up removed the unnecessary SCL hairpin at J1.4: eleven rear
segments (7.39 mm) became two 0.2 mm segments (1.57 mm), joining the existing
via at (38.2,21.9). All other tracks/vias/pads/placements were preserved.
Strict DRC/open nets/parity/geometry passed and the handoff was regenerated.
Before/source audit evidence is in `build/hardware/v4-scl-cleanup/`.

V4 hand-assembly labels: all 30 R and seven C reference fields are visible on
B.Silkscreen, mirrored for rear reading, 1.0 mm size / 0.15 mm stroke. R23,
R24, R27, R28 and R32 are vertical. R12 has a two-segment rear silk pointer;
keep it associated with R12 when moving that part. The geometry checker
requires rear passive references; DRC checks their pad/silk clearances.
No pads, component placements or copper were changed. Before/audit evidence
is in `build/hardware/v4-passive-labels/`; use the regenerated Gerbers.


V4 purchase preparation now records HASL with lead (`HAL SnPb`), following the
user's choice in `docs/jlcone-shipping.md`. Source finish and exporter assertion
agree. Keep ordinary through vias tented; do not request plugging/filling/capping
or change electrical geometry as a purchase-side adjustment. Reupload the current
labelled Gerbers rather than reusing the older quote's file. Prepare carts/quotes
for review; do not submit paid orders or support messages without authorization.

The user explicitly accepts the current Samsung/TI/Nexperia parts for the small
prototype batch, but wants cheaper alternatives and circuit simplification
considered afterward, following v3's cost intent. The current brands are a test
baseline, not permanent production requirements. Prioritize C8/C9, the three
per-tile logic ICs, and whether measurements justify removing supporting parts.
Read the cost-reduction follow-up in `docs/v4-parts-research.md`. Keep the current
prototype CAD/CSV unchanged for these experiments; use a separate candidate and
compare exact MPN, package/pins, thresholds, drive/input current, effective
capacitance, BOM/fabrication/assembly totals and physical results before promotion.

Three-TI sourcing follow-up is in `docs/v4-parts-research.md`: JSMSEMI
74HCT244PW,118-JSM/C53114424 is a pin/package-compatible U3 candidate;
TI TPS2553DDBVR/C521201 matches U5's pin map and 33k limit calculation.
Both remain physically unqualified, with originals retained for the baseline.
TECH PUBLIC 74LVC2G17GW/C19829576 is a cheap UART-function candidate requiring
six-pin SOT363 footprint/routing changes and Schmitt-level/temperature review;
never substitute it in the current U4 eight-pin assembly list. Separate sample
CSVs/evidence are in `build/hardware/v4-ti-alternatives/`; no cart/order changes.

The user confirmed retaining the current original-parts shopping cart. Cheaper
TI alternatives are saved for later experiments, not substitutions in this
purchase. The user manually increased LCSC quantities to amortize shipping;
preserve those quantities instead of replacing them with generated minimums.
Agent has not submitted paid orders. Current quote comparison is in
`build/purchase-v4/shipping-comparison.json`; joint shipping was not priced as
a final consolidated delivery and must not be promised cheaper.

Next-revision TME research is in `docs/tme-next-revision.md`, with the candidate
table in `docs/tme-next-revision-parts.csv` and price/quantity assumptions in
`config/tme-next-revision.json`. TME-only means new purchases; the user explicitly
retains stocked CH32V003F4P6 and XL-2012UOC, so do not migrate to STM32 merely
for sourcing. The research originally reserved one v3 board; the user now plans
four remaining v3 boards. The updated ledger reserves 256 LEDs and four MCUs,
leaving a conservative 43 MCUs/680 LEDs; twenty v4.1 tiles need 600 more LEDs.
These are preliminary future-revision
parts, not substitutions in current v4 CAD/cart. Price snapshots use both PLN
and USD; never sum them without an explicit conversion or present them as a
live checkout quote. In actual v4, R15–R22 pull down row-buffer inputs, not
MOSFET gates; replacing eight MOSFETs with ULN2803 does not remove those pulls.

The v4 iteration goal started on 2026-10-12 was completed with a checked v4.1
purchase package and TME buying list; physical qualification remains after
delivery. Prototype iterations need not minimize every cost, but retain cost
awareness. CH32V003 and orange LEDs remain stocked exceptions. Work in
`hw/ledkiv4.1/ledkiv4_1.kicad_pro`; the original v4 remains in place and in
`archive/hw/ledkiv4-pre-tme-20261012/`. The source corresponding to the saved
JLCPCB cart is frozen in `archive/hw/ledkiv4.1-purchase-20261013/`, with 40
file hashes. Original source/handoff/Gerber ZIPs remain in ignored
`build/hardware/v4_1/purchase-snapshot-20261013/`. Never replay old creation,
placement or routing ECO helpers against reviewed source or archives.

The v4.1 TME schematic uses HCT238D SO16, retained HCT244, DMG2302UK sinks,
MIC5504 SOT23-5 (VIN1/GND2/EN3 tied to VIN/NC4/OUT5), ALPS SKRPABE010 and
GCT USB4105-GF-A. Final UART selection is Nexperia 74LVC2G34GW,125 with BOTH
R26/R27 = 220 ohms and retained 100k idle pulls. Its VIH/VIL guarantees cover
2.7–3.6 V, but input transitions must still meet 10 ns/V; initial qualification
uses short staple links and a fast 3.3 V TTL adapter. TI SN74LVC2G17DCKR is a
reviewed same-footprint alternative, excluded from the buying list because TME
delivery is unconfirmed. Preserve exact MPNs and do not restore old LCSC codes
to substituted components. Config/procurement quantities derive from schematic
refs; default TME buys include 20% spares, plus minimum-cash comparison.

KiCadRoutingTools runs with In1 as an obstacle. The reviewed manual v4.1 In1
exception adds 41 segments totaling 127.022 mm across eight signal nets and
one VCC route. Do not widen this exception or loosen authored rules. Official
ERC/DRC/open-net/parity and independent pin/net/geometry checks passed; no
physical v4.1 qualification is claimed. The pinned KiCad SVG Extras report has
nine interactive panels, cross-layer net selection and recorded failed trials;
its Firefox rendering/click check passed. Keep engine scores separate from
KiCad findings and do not invent wall time for older runs.

## Current procurement and inventory

The user chose a small TME order after reporting USD 20 shipping and USD 20
tariff for LCSC. Those are user checkout figures, not independently verified
tax calculations. Twenty-board LCSC and bulk-stock drafts are deferred and
archived under `archive/purchase/20261013-drafts/`; ICs will not be stored in
the user's tape magazines. Only 500 orange LEDs per magazine is confirmed,
tightly packed. Other capacities and paper-tape fit remain unconfirmed.

TME order 35700057 contains 20 lines / 883 parts, all awaiting delivery in
the supplied export. Use `config/parts-incoming.csv` and
`config/orders/TME-35700057-source.json`; supplier warehouse allocation is not
on-hand stock. Record receipt only after the user confirms/counts delivery.
Do not merge pending TME parts into the old LCSC-only `parts-stock.csv` schema
or change its four-v3 reservation. MCU/LED shelf estimates remain 43/680.
Actual ordered quantities are in `config/purchase/TME-35700057-ordered.csv`;
do not reimport that record as a new order. The generator's old CAD worksheet
is not the user's final purchased list and does not deduct pending TME stock.

The purchased assembly overlay is
`config/purchase/v4.1-assembly-substitutions.json`: R30/R31 use Yageo
RC0603FR-075K1L, and head-only U5 uses Diodes AP22653W6-7 with R32 retained
at 33k 1%. Same pin mapping/lands were reviewed. Manufacturer best-fit current
limits are about 758mA typical / 654–871mA with a 3% resistor allowance;
startup/foldback/fault/thermal behavior remains to be qualified. Native CAD
and the uploaded Gerbers deliberately retain the previous MPNs. Do not
silently replace the frozen CAD or regenerate an order package to hide this
procurement distinction. The AP22653A latch-off variant is not selected.

SWIO cable purchases are five MX-51021-0300 housings and twenty MX-50079-8000
contacts. Use 28AWG wire and two contacts per probe lead; J2 pins 2/3 are
SWIO/GND, pin 1 is an unused REF3.3V for this WCH-Link setup. Board power is
from USB; programmer power outputs remain disconnected. The user pictured a
LionRage open-barrel crimper with exchangeable dies and apparent 0.08mm²
minimum. Model and PicoBlade fit are unconfirmed; try a sample crimp first.
No new crimper purchase is confirmed. IWISS IWS-2820M and ENGINEER PA-09 were
researched; archived prices must be refreshed for another purchase.

Gerber SHA-256 is
`31de94b8df6cec8883f9bfa811c942c091c43b7e7b3588ef1af4935bc057a927`.
It was uploaded and saved to JLCPCB cart `ledkiv4_1-gerbers_Y8`, prototype
`Y8-10656422A`: five boards, four layers, 1.6mm, green/white, leaded HASL,
outer1oz/inner0.5oz, Plugged with solder holes/USB slots/NPTH kept open.
Optional production-file confirmation is off. Cart estimate was USD 2 PCB
+ USD 1.50 Global Standard Direct Line delivery; checkout taxes/fees remain
unconfirmed. The user took over checkout; do not infer payment/order completion
from a saved cart. No agent order/payment was submitted. Gerber uploads have
standing authorization, but purchases/payments do not follow from that.

Current documentation is newer than the immutable exported-package manifest.
When auditing it, distinguish doc-only changes from native electrical/CAD
changes. Keep the saved Gerber bytes and source snapshot intact; a new circuit
or geometry change needs new checks, a new package identity and an upload.

## Second v3 and shelf accounting (2026-10-14)

Second v3 UUID is `d7-6e-ab-cd-41-3a-bd-ff`. The scan demo's 5228 bytes and
explicitly authorized PD7 GPIO option setting were readback verified. The user
confirmed all LEDs work after assembly corrections; edge soldering and physical
two-board I2C remain pending. I2C controller/target images are prepared, with
automatic one-second counter attempts on controller boot; no I2C image was
flashed during preparation. One WCH-LinkE suffices for sequential programming.
Read `docs/i2c-v3-test.md` for roles, displays and test acceptance.

At the user's request shelf-inventory recorded second-board consumption in
the shared canonical ledger: one MCU, one HC138 decoder, 64 LEDs, eight 51-ohm
resistors and five capacitors. Only those eight resistors and five capacitors
are fitted; second-board switches and four 10k resistors are absent. R11/R12
I2C pull-ups are absent on BOTH assembled boards. The previous assumed use
of two 4.7k resistors was corrected to zero. Live reservations now cover three
unassembled v3 boards plus missing parts of assembled boards; historical
four-board maps in provenance are not additional holds. V4.1 planning and TME
incoming records remain separate and unchanged. Conservative shelf counts are
46 MCUs / 872 LEDs; after v3 holds 43/680, after v4.1 planning 38/360. Preserve
the uncertain first-board 51/68 split and prior debugging-loss bounds. Evidence:
`build/inventory/second-v3-20261014/`. These current entries supersede older
statements that the live reservation still represents four unassembled boards.

## Identical USART chain preparation (2026-10-14)

`make VARIANT=v3-uart-chain` builds the separate counter/CRC diagnostic in
`firmware/uart-chain/User/`. Every board uses the same image; PC TX enters
leftmost J3.5/PD6 RX, each J1.5/PD5 TX joins the next RX, and far-right TX
returns to PC RX. The PC originates requests; hop counts give volatile positions.
Only checksummed protocol frames use UART. Keep local status/help/boot logs on
SWIO so they cannot be interpreted or multiplied downstream. Foreground relays
retain one pending output until `uart_tx_free()` shows space; RX ISR behavior
and ordered gap markers remain unchanged. CRC failures and damaged/overflowed
packets must preserve the last accepted counter/display. PC uses stop-and-wait
through `scripts/uart_chain.py`; text TUI/uart_text use a different protocol.
I2C pulls are unnecessary for this UART test, and their recorded absence stands.

Current image is 10136 bytes; RAM sections total 976 including the 256-byte
stack. Assessed foreground plus all three ISR paths totals 196; runtime high-water
is unmeasured. Host tests cover actual C relay contexts, C/Python packet exchange,
CRC/data damage, backpressure, stale/wrong-hop/error replies and PTY cleanup.
All variants and clangd passed. Evidence: `build/uart-chain/`. No board was
flashed during preparation; physical two-board UART remains untested. Both
identified boards already have PD7 GPIO configured; preserve option bytes and
power settings. Read `docs/uart-chain.md` for wiring and acceptance.

## Datasheet pad audit and shared archive (2026-10-14)

Read `docs/v4-pad-audit.md` before a v4/v4.1 hardware handoff. The audit found
no reviewed pin swap or pitch mismatch; 135 footprints and 361 numbered pads
per board match local libraries and exported schematic nets. V4.1 native DRC
remains zero, but the corrected geometry checker exits 1: GCT USB4105's true
manufacturer edge is local y+3.675, not the text-label anchor y+3.1. Actual
PCB y49.27 is 0.575 mm inward from the reference y49.845. Slots remain inside
the PCB; engineering acceptance/physical fit remains unresolved. Package
regeneration is blocked by this finding. Do not silently change frozen CAD,
purchase files or the checker to accept it. Generic IC lands differ from
manufacturer examples; ME6206 M3's generic Fab body is too narrow. Fresh v4
absolute-path DRC reruns crashed KiCad; independent pad parity passed. Raw
evidence is in `build/hardware/pad-audit-20261014/`; CAD hashes were unchanged.

29 manufacturer PDFs are archived with MPN/revision/provenance/SHA-256 in
`/home/pies/.local/share/electronics/datasheets/`, linked as
`/home/pies/electronics/datasheets/`. Reuse the catalog and immutable copies;
retain old revisions and label distributor mirrors/family references. Stock
and incoming ledgers were not changed. Project acceptance belongs in Letki,
not in the shared document catalog.


## Two-board v3 transport verification (2026-10-14)

Both identified v3 boards passed 20 physical UART-chain replies with two hops,
matching tokens/counters/CRCs and zero cumulative diagnostics. Then physical
I2C passed 20 consecutive requested-counter reply-CRC confirmations at configured
100kHz: left/original controller, right/second target 0x32, one left 4.7k pull-up
pair, user-confirmed existing WCH-LinkE 3V3/GND. Both firmware roles were
readback verified with two full backups each, unchanged options/power.
Controller I2C fail/UART/drop counters were zero; target final diagnostics and
optical matching counter patterns were not independently inspected. Frequency,
waveforms and runtime stack remain unmeasured. Evidence in
build/board-readback/uart-chain-20261014/ and i2c-two-v3-20261014/.
Current boards run I2C controller/target with automatic counting enabled.
Earlier pending two-board transport status paragraphs are superseded; v4/v4.1
new electrical circuitry and production process remain unqualified.
Standing firmware-update/test authorization now applies to all v3 boards (2026-10-16);
identity checks/readbacks still required. No per-image permission question.


## Native strip renderer

Read `host/renderer/README.md`. `make renderer-run BOARDS=5` opens the C
Wayland/Cairo app; `make renderer-test` checks its local Unix-socket agent API.
Use `build/renderer/letki-renderer ctl status/stop/run/step` or documented
commands to control the existing window. Configurable 1-256 tiles share firmware
pong geometry/CRC code; keyboard presets are 1-5. Headless/manual modes and
PNG/JSON output support deterministic agent tests. Local sockets and desktop
access may need sandbox escalation; builds do not. Simulation is not physical
qualification or multi-address I2C firmware. Generalized firmware builds passed
all variants/tests but were not flashed during the desktop task. Preserve the
preceding verified board images/readbacks. GUI and model sources are in
`host/renderer/`; no browser, external agent service or hardware connection.


## Two-board standard text candidate

Read `firmware/strip-text/README.md`. `make strip-text-images` builds left/right
-Os text candidates; `make renderer-text` previews their shared scene and UART
parser in the native window. Socket `demo text` / `uart COMMAND` and
`scripts/demo_strip_text.py --tour/--record` provide testing/previews. Candidates
are frozen in `build/strip-text-prepared/` and have NOT been flashed. Keep the
verified preceding physical ping-pong images/readbacks. Head parses PC UART,
I2C carries right pixels/brightness in a new 14-byte CRC frame; receiver relays
UART replies without adding logs. New frame driver is separate from diagnostics.
The new payload/firmware pairing needs physical tests after preview/programming.
Use right-first programming order, existing identity/backups/readback and
option/power rules. Host tests, all variants (serial retry after a temporary
archived-source assembler crash), native socket tests, sanitizers and clangd
passed. Left RAM 1932 including stack, conservative stack 244/256; runtime
high-water remains unmeasured. No active v3/archived application changes or CAD.


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


## V3.1 handoff promoted (2026-10-15)

The completed rework is now active in hw/ledkiv3.1/, with v3_1-pulse
and LED-off v3_1-interface firmware, config/v3_1-*, scripts/*v3_1* and docs/v3_1-*.
This supersedes earlier seed/unresolved-routing/session-only status paragraphs.
Read docs/v3_1-handoff.txt before work. build/sessions/v3.1-design/ is retained
history, not an edit target. Do not replay generation/placement/routing helpers
on the reviewed board. Frozen exports remain byte-identical to the session
package; their source manifest identifies the old source-ZIP context, not every
current main-tree file. Manufacturing remains HOLD_PROCESS (JLCONE Plugged vs
Tented intent), all 15 physical qualification rows pending. No v3.1 order exists.
ESP-12F/head are deferred. Original v3 firmware is incompatible with this tile.


## Single shared v3.1 project (2026-10-15)

The user explicitly requested one mixed human/agent project. Canonical edit
target is hw/ledkiv3.1/ledkiv3_1.kicad_pro for schematic AND PCB. Read
its README and docs/v3_1-shared-workflow.txt. The33R E12/1% simplification
is now promoted, with R58-R65 and JP1/JP2 removed. Previous34R CAD/exports
are archived in archive/hw/ledkiv3.1-checked-34R-20261015/; old build/session
candidate paths are historical only. Do not create a parallel authored project.
Check editor identity/unsaved human state before edits; prefer grouped native
IPC for an open board. External rewrites require saving/closing/reopening the
relevant editor and checking latest disk changes. Refresh alone is not reload.
No new fabrication package, physical qualification or programming is implied.


## V3.1 schematic-only edit (2026-10-15)

Latest schematic removes SW1/SW2, R9/R10/R13/R14 and C2/C5; MCU PD0/PA2
are NC. All16MOSFET stages are native groups with physically wired resistor
networks; the saved human SEL1-SEL8 decoder net names were preserved.
R15-R38 and R42-R57 (40gate/bias resistors) use local0603 hand-solder
footprints and100mW Royalohm catalogue parts. R1-R8 remain33R/0805.
This task intentionally did not mutate the open PCB or firmware. PCB update
from schematic and fresh footprint/placement/copper/label/DRC/parity checks
are pending. Previous zero-DRC reports apply to the older paired revision.
Current schematic ERC and retained pin/net-name audit pass. See
build/hardware/v3_1-schematic-layout/ and config/v3_1-source-handoff.json.

## V3.1 Astra findings repaired (2026-10-15)

R39.1-to-VCC and the D9-D16 cathode-bus-to-L2/R2 connections are repaired
in the shared schematic. Fresh ERC0/ignored0 and the independent146-component
schematic audit pass. scripts/check_v3_1_integrated.py now accounts explicitly
for approved button/RC removal and40gate/bias0603; --schematic-only leaves
PCB unqualified. Its default full PCB/pad/rule checks remain strict and reject
the currently unsynchronized PCB. Five positive/fault-injection cases pass,
including both original disconnects, a wrong gate footprint and stale PCB.
Native PCB geometry/open findings remain0, parity90 is pending the existing
PCB update. Only one schematic wire was added and one shortened to exact
pin/label endpoints; all other schematic objects and PCB/project rules were
preserved. Assembly figures now match33R:36.36mA nominal, conditional58.26mA
upper model and69.54mW shared-resistor average at64%duty. Evidence:
build/hardware/v3_1-astra-fixes/; historical review and repair status are in
docs/v3_1-astra-review-20261015.txt. No firmware, hardware, stock or orders changed.

## Fresh v3.1 placement, no routing (2026-10-15)

The user requested a new PCB placement in the same shared project and explicitly
no routing. Current146footprints match the repaired schematic. Agreed64LEDs,
J1/J2/J3 and H1/H2 retain exact poses and padstacks;69fixed footprints are locked.
The77movable parts are all rear-mounted: eight PMOS stages along the top,
eight NMOS stages with their resistors down the right, logic at centre-left.
R4 is now rear-mounted; its obsolete optical hood and button access entries
are omitted from mechanical config. Full details: docs/v3_1-placement.txt.
Source of record remains hw/ledkiv3.1/; the latest routed predecessor is preserved
in archive/hw/ledkiv3.1-routed-before-placement-20261015/ with hashes/libraries.
No tracks,vias or copper zones exist. ERC0/placementDRC0/parity0/ignored0;
280open connections are expected, not a routed-board pass. The full integrated
pin/pad audit and new check_v3_1_placement.py pass. One/four-tile populated
STEP nominal fits pass; physical qualification remains pending. Current labels
are77rear1mm/0.15mm assembly fields, with resistor numbers and the R=# legend.
config/v3_1-placement.json is a dated snapshot, not a second edit source.
Old routed manufacturing checks/exporter need revision after new routing; do
not replay placement/creation helpers or treat old exports as the new source.
Initial placement evidence: build/hardware/v3_1-placement-20261015/.
The user then explicitly requested one Astra placement revision before trying
human placement. That iteration is now applied through live IPC in the same
PCB as one undo operation; no routing. Current evidence/checkpoints/proxies:
build/hardware/v3_1-astra-placement-20261015/ and docs/v3_1-placement-comparison.txt.
NMOS orientation now faces gates inward/drains outward; row-bank pitch4mm,
PMOS gate/bias groups shortened, C1/C3 orientation/position improved. The
geometric local-gate MST improves29.44%; no routed-speed/length claim follows.
Final shared-source ERC0/placementDRC0/parity0/ignored0/opens280; native and
independent checks pass. The current placement/config label snapshots match.
Human placement is next, in this same project; save before another agent edit.
Installed kicad-python0.8.0 BeginCommit fails with both editors open. Saving,
temporarily closing the paired schematic and reopening it after the transaction
worked. The one-shot IPC helper preserves model items dropped by its rotation
setter and uses exact integer right-angle transforms, without editing installed
bindings. Failed candidate silk/script/API trials remain visible in the evidence.
No firmware, hardware, stock or orders changed.

## Current v3.1 human/Astra routing completion (2026-10-15)

Canonical hw/ledkiv3.1/ now contains the completed human placement with Astra
power/ground/routing/silk completion:146footprints,974tracks,131ordinaryvias.
All component poses/models/pad geometry and authored schematic/rules were
preserved. NativeERC/DRC/open/parity/ignored0 and independent manufacturing/
multilayerpower checks pass. GND has3In1regions joined by two explicit rear
bridges; do not require one polygon when actual four-layer connectivity passes.
Exact84In1segments and413power/columntracks are reviewed and bound in the
project/config manifests. Routed checks use the routing-env Python (Shapely).
The placement-only checker is historical and rejects any copper by design.
Do not replay old placement, creation, routing-seed or Q10 repair helpers.
Read docs/v3_1-completion-20261015.txt; source and intermediate evidence is in
build/hardware/v3_1-astra-completion-20261015T200432Z/. Current checked prototype
exports belong in hw/ledkiv3.1/exports/prototype/ with a source/check manifest.
Physical pulse/current/rail/thermal/interface/optical/fit qualification and
fabricator process confirmation remain pending; no new order or flash occurred.


## V3 assembly sequence and standing authorization (2026-10-16)

Three v3 boards are assembled. Third UUID `d7-69-ab-cd-41-35-bd-ff` passed
flash readback, live SWIO controls and a complete row/column/pixel scan; the
user confirmed all LEDs and patterns look correct. It remains on the automatic
scan demo at brightness 100, unpaused, with PD7 configured as GPIO. Backups and
evidence: `build/board-readback/third-v3-20261016/summary.json`. No USART test
was performed on this board.

Next the user will solder the remaining two v3 boards; only afterward will
they connect all five. Do not treat the five-board chain as already connected
or tested. Individual assembly checks precede the full-chain test. The user
explicitly permits preparing/executing v3 test procedures and flashing any v3
board at any time without another permission question; use the identity,
backup and readback requirements above. Assembly stock consumption has not
been reconciled from this test; do not silently change shared inventory.


## Fourth v3 scan test (2026-10-16)

Fourth UUID `d7-50-ab-cd-41-1c-bd-ff`: two matching full flash backups,
5,228 scan-demo image bytes matched readback, SWIO controls and complete scan
cycle passed. User separately authorized its PD7 GPIO option change
(USER 0x17 to 0x1f plus inverse; all other option bytes preserved).
Left running automatic scan at brightness 100, unpaused; user confirmed all rows, columns and 64 pixels look correct,
without missing LEDs or ghosting. Evidence: `build/board-readback/fourth-v3-20261016/summary.json`.
No new option-byte authorization applies to other boards. No programmer power,
CAD or inventory changes; USART/chain and electrical measurements not tested.


## Fifth v3 scan test (2026-10-16)

Fifth UUID `d7-56-ab-cd-41-22-bd-ff`: two matching full flash backups,
5,228 scan-image bytes matched readback, SWIO controls and full scan cycle
passed. User explicitly requested its PD7 reset-to-GPIO configuration
(USER 0x17 to 0x1f plus inverse; all other option bytes preserved).
User confirmed all rows/columns/64 pixels look correct without missing LEDs
or ghosting. Left running automatic scan, brightness 100, unpaused.
Evidence: `build/board-readback/fifth-v3-20261016/summary.json`.
No programmer power, CAD or inventory changes; five-board chain remains
untested. Reset-pin authorization here is specific to the fifth board.


## Prepared five-tile text / fall mode (2026-10-16)

`make strip-five-images` builds `v3-strip-five` head/tile1/tile2/tile3/tile4
from shared strip-text sources with 40-column geometry; separate output dirs.
Receivers use I2C 0x32..0x35, one per position. Do not load identical receiver
images at all positions or infer physical position from assembly order. UART
replies relay through all four. Head advances after all CRC replies, but
receivers update sequentially; no synchronized latch/rollback is claimed.
`m fall` adds wrapped downward lines plus pulse; `e pulse/off` controls effect,
`b` is ceiling, pause freezes effect, host frames stay steady. Old two-tile
build commands and frozen verified images are retained. Candidate not flashed.
Tests/all variants/renderer/clangd passed. Head 13,572 flash / 1,952 RAM incl
256 stack; conservative foreground+ISR stack sum 252, runtime unmeasured.
Evidence: `build/strip-text-fall-prepared/manifest.json`.


## Five-board live text state (2026-10-16)

All five images flashed/readback verified with two matching full working
backups each and preserved option bytes/programmer power. Left-to-right
UUIDs: head d7-50-ab-cd-41-1c-bd-ff; 0x32 d7-56-ab-cd-41-22-bd-ff;
0x33 d7-69-ab-cd-41-35-bd-ff; 0x34 d7-73-ab-cd-41-3f-bd-ff;
0x35 d7-6e-ab-cd-41-3a-bd-ff. User confirmed power/UART/SDA/SCL and
one existing pull-up pair. Whole UART reply chain passed 20 exact pings
and controls. Head snapshot: 4,466 CRC replies, zero I2C failures.
RAM inspection coincided with a head restart; preserve failed diagnostics
and do not claim non-resetting resume. Mode restored via UART; final
serial-only controls/20 pings and 5 s clock-progress passed, no extra reset.
Initial UART open had invalid line/errors 2, unchanged through first run;
final post-diagnostic run had zero errors/drops. Preserve both records.
Left running falling Polish text, 100 ms/row, ceiling 70, pulse on, unpaused.
Optical confirmation pending. Evidence/backups: build/board-readback/strip-five-20261016/summary.json.
No waveform/rail/current/runtime stack or receiver final cumulative diagnostics
claimed. SWIO remains on leftmost head; no terminal or serial helper left open.


## Current stronger pulse (2026-10-16)

User confirmed all five working, initial pulse too subtle. Head only updated
to 5..100% of requested brightness ceiling over 64 steps (6.4 s at 100 ms);
successive fully visible lines now differ in brightness. Active head image
is 13,580 bytes, two full working backups matched and readback verified,
options/power preserved. Receivers unchanged. Test/renderer checks pass.
Current state: falling Polish text, 100 ms, ceiling 70, pulse on, unpaused;
stronger-pulse optical feedback pending. Serial 20 exact pings/clock progress
passed; startup UART error 1 retained, no additional errors/drops (drops 0).
No RAM diagnostic reads in this update. Previous diagnostic restart preserved
in original five-board evidence. New authoritative head evidence:
`build/board-readback/strip-five-pulse-20261016/summary.json`.


## PWM show simulation/candidate and PC audio (2026-10-16)

User wants simulation first; do not infer a new flash request from preview
work. `make renderer-pwm` / scripts/demo_pwm_show.py previews six scenes,
including Daisy chain, independent per-pixel levels, 38.4 s auto loop. Shared
integer core host/pwm-show/pwm_show.c also compiles in separate v3-pwm-show
head/tile1..tile4 images (`make pwm-show-images`), not flashed. Small 14-byte
phase packets use new 0xb6 magic; never mix with existing text receivers.
WCH measured head 11,116 flash/1,620 RAM incl 256 stack, each receiver 7,712/1,164.
Foreground 128 + conservative ISR 48 = 176/256; runtime stack unmeasured.
Evidence build/pwm-show/resources.json; tests/all variants/clangd pass.
PC-only original bell score plus Supertonic M1 narration uses
`.tools/native-tts/bin/python scripts/pwm_show_audio.py` (optional --loop),
config/pwm-show-audio.json. DAC presentation clock drives simulator PWM seek;
Space pauses audio/light. One 38.4 s pass had no audio warnings; 38 sync checks
logged in build/pwm-show/audio/playback.json. Narrated recording:
build/pwm-show/pwm-show-narrated.mp4. No waveform stretching, no ROCm or earlier
TTS config changes; no serial/probe/hardware operations in this task.


## Current mixed chain after head-only PWM flash (2026-10-16)

User explicitly requested the head flash. Position 1 d7-50-ab-cd-41-1c-bd-ff
now runs the 11,116-byte PWM-show head: two matching full backups, complete
readback and SWIO startup/status passed, all options and power preserved.
Positions 2..5 still run text receivers 0xa6, incompatible with PWM 0xb6.
The new head cannot advance the batch until those receivers are updated;
do not claim the old full-chain text state or a physical PWM pass.
Evidence/backups: build/board-readback/pwm-show-20261016/summary.json.
PC audio still drives the simulator only. SWIO remains on leftmost head.


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


## Physical PWM audio synchronization (2026-10-16)

User requested music and narration on the physical chain and connected SWIO
to the head, with the UART free. Head UUID d7-50-ab-cd-41-1c-bd-ff received
an application-only update after two matching full 16 KiB backups. All 11,372
image bytes matched readback; options/power preserved; SWIO startup/status
passed. Four PWM receivers remain unchanged. RAM is 1,620 bytes including the
256-byte stack, conservative maximum stack remains 176 bytes. Host tests pass,
including absolute tick parsing/rejection, four-receiver acknowledgements and
transfer retry. No scan/PWM driver or CAD changes.

Launch from the repository root, after closing picocom:
`.tools/native-tts/bin/python scripts/pwm_board_audio.py` (add `--loop` to repeat).
UART auto-detects the WCH-Link serial port; `--port` overrides it. Ctrl+C returns
to the standalone automatic show and restores tty settings. PC DAC presentation
time drives UART `k 0..959`; the head acknowledges only after all four receivers
CRC-acknowledge. Late host frames are skipped, preventing accumulated clock
drift. PC speakers provide the score and complete-phrase narration.

User confirmed spoken scenes match all five physical tiles ("yep"). First
cycle: no audio warnings, UART errors stayed at baseline 2, drops 0; phase ACK
mean 16.05 ms, max 24.68 ms. Audio backend completion arrived before final DAC
samples, so the launcher now continues to the final presentation tick; final
cycle result is recorded in `build/board-readback/pwm-audio-20261016/summary.json`.
This supersedes simulator-only audio status. Bus/scan/OS latency is present;
no instrumented optical timing or PWM waveform measurement is claimed.


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


Milestone baseline (2026-10-17): `docs/milestones/v3-general-r3-20261017.txt`
and its adjacent JSON identify the tested working-tree R3 snapshot, five image
hashes, recovery archive, evidence and limits. Use this baseline for future v3
firmware/driver work. Historical Git HEAD does not contain this implementation;
do not tag that old commit as the milestone. Content experiments normally use
UART and do not require another application flash. Existing hardware permissions
and backup/readback requirements are unchanged.

Native PC music engine (2026-10-17): `host/player/` is C++17 with PortAudio,
libsndfile, SDL2, json-c and FFmpeg libraries. `make player`, `make player-test`,
`make player-sanitize`; playback auto-detects one WCH-Link serial adapter,
verifies five nodes, and falls back to simulation only when no adapter is found.
`--simulate` forces PC-only playback, `--port` overrides selection; ambiguity or
a busy/incompatible adapter is an error. `--check`/`--analyze` bypass discovery
entirely. Missing startup UART replies get one cancellable10.5s idle-baud recovery
wait and retry. `--inspect` auto-detects without driving pixels or opening audio.
Default local show is `my-cyganie-full.json`, LEVEL8/12fps: original silk
ribbon/ripple geometry with bass-hit motion and PWM attack/release;
video plays in a full-color PC panel beside the simulator and never affects
LED pixels. Keep LED concepts clear; repeated shapes are allowed when useful.
The user particularly likes the original silk ribbon and ripple garden;
`music-ribbon`/`music-ripple` retain their geometry with FFT-driven PWM.
All animation content streams over UART and preserves saved
programs. No new MCU image is required. Guide: `host/player/README.txt`;
verified evidence/limits: `docs/native-player-20261017.txt`.

Offline wording tools are in `scripts/player_words.py`, with CPU Whisper reusing
`.tools/tts-venv` or `.tools/align-venv`; keep the ROCm/Triton environment intact.
Transcripts record exact source SHA256, source-relative timestamps, confidence
and review flags. Instrument announcements/lyrics can be misrecognized over
music; do not silently treat candidate text as verified lyrics. Cue conversion
checks recording identity and supports held compact-font captions. Workflow:
`docs/player-word-tools.txt`. Generated media/transcripts/reports stay ignored.


Complete music demos (2026-10-17): `docs/music-demos.md` and
`config/player/demos.json` identify the full My Cyganie, Tubular Bells and Adagio
shows. Default native player is `my-cyganie-full.json`; previous presets remain.
`make demos-check` and `make demos-prepare` stay fully offline and silent: real
five-node C firmware checks, native frame exports, contact sheets and optional
silent full-length MP4 previews. They must not open PortAudio, physical UART or
live windows. `make demo-my-cyganie`, `make demo-tubular-bells`, `make demo-adagio`
are later playback commands; they now auto-detect the chain and PORT overrides
selection. Use --simulate to force PC-only playback. During this
preparation the user requested no music playback and no physical display driving.
Effect cues support bounded level/speed/sustain/variant, PC-only labels and
smooth transitions. Video remains PC-only. Announcement/refrain placement is an
editorial draft, not a verified score or lyric transcript. New offline evidence
is under `build/player/complete-demos/`; do not present it as a live optical test.


## Current v3.2 routed CAD prototype (2026-10-17)

User-requested routing is complete in hw/ledkiv3.2/. Read its README and
docs/v3_2-routing.txt before changes/handoff. Native ERC/DRC/opens/parity/ignored0;
independent76nets connected,159placements/padstacks preserved. Exact reviewed
In1 and power contracts are enforced by scripts/check_v3_2_integrated.py;
scripts/v3_2_package.py creates fresh checked exports without editing CAD.
The full unrouted human checkpoint is archive/hw/ledkiv3.2-unrouted-20261017/.
Keep that checkpoint and accepted v3.1 unchanged. This is CAD only: new V006
firmware/custom loader, mechanics and physical qualification remain pending.
Old V003 images are incompatible; no new hardware/order/stock authorization.


## V3.2 milestone and human editing ownership (2026-10-17)

The user accepted the routed CAD as milestone v3_2-routed-20261017. See
docs/milestones/v3_2-routed-20261017.txt and hw/ledkiv3.2/baseline.json. Frozen
source/dependencies/exports are in archive/hw/ledkiv3.2-routed-milestone-20261017/.
The single main editable project stays hw/ledkiv3.2/ledkiv3_2.kicad_pro. The
user is taking over manual component/placement/routing changes; do not reroute,
restore milestone CAD over their edits or create a competing main project
without a new request. Saved milestone check results apply to that exact source.
For later requested work capture the current human state first and review any
needed updates to baseline-specific geometry/power/In1/label contracts; retain
electrical/manufacturing rules. Keep both routed and unrouted archives unchanged.


Manual text GUI (2026-10-17): `host/control/` is a separate Qt6/C++17 app using
`host/player/link.cpp` directly, with no Python/audio runtime. Build/run/test:
`make control`, `make control-run`, `make control-test`. Root tests are offscreen
and simulated; `test-control-gui --hardware` is an explicit physical RAM-text test.
The app auto-identifies five boards, polls status read-only on a worker, previews
with the real C interpreter, and stages edits until Apply. RAM uploads/readback
and synchronized standalone PLAY support scroll/bounce/fall/still and Polish
compact glyphs. RAM-only capacity checks prohibit implicit flash fallback.
Disconnect/exit keeps applied text running; do not add music-player-style saved
show restoration here. A newer draft during Apply stays unsent. The UART worker
owns all commands; the UI thread must remain responsive. Native-C/GUI tests,
ASan/UBSan core checks and physical Apply/readback/pause/resume/disconnect passed;
no new optical measurements. Guide/evidence: `host/control/README.md`,
`build/control/`. Never infer current-text/framebuffer readback from status.

Manual GUI font/PWM extension: Compact3×7, original Large8×8 and horizontally
dilated Bold9×8 are host-compiled bitmaps; preserve Polish edge marks. Steady,
Breathe and Blink compile into LGS1 segments sharing one asset, with minimum,
peak and1–6 pulses per movement (Still uses4s). Splits include bounce turns;
no firmware changes or continuous PC brightness traffic.
Account for32bytes/segment before Apply. All modulation continues standalone;
Pause freezes its timeline. Local controls persist only in ignored
`build/control/draft.ini`; reopening must never auto-Apply. GUI tests omit this
file, and `--hardware` backs up/restores the prior identical shared RAM program.

GUI long-text repair: the firmware's60s period bound is per track, not per show.
The compiler now splits longer motion/envelope spans at60s, retaining the
16-track and RAM limits. Regression tests cover82s bounce, five-minute scroll,
clock-anchor normalization, loop boundaries and explicit RAM rejection.
`make control-desktop` explicitly installs a per-user desktop entry to register
Qt's advertised app ID; normal builds must not install outside the project.
Qt6.12 Wayland text-input focus warnings remain visible; do not disable IME or
hide unrelated warnings as a substitute for a framework fix.

## Letki Studio / local display service (2026-10-17)

This supersedes the earlier Qt GUI implementation notes. `host/control/` now
uses GTK4/libadwaita for Studio, and Qt-free C++/GLib/JSON-C for `letkid` and
`letkictl`. The broker coordinates UART ownership; the GUI must never open a serial device.
Canonical guide/API: host/control/README.md and API.md. Studio supports local
text/PWM drafts, native-C preview, pixel painting, presets and diagnostics.
Local draft.ini migration must preserve the original file. Corrupt libraries
must not be silently overwritten. The GUI uses a bounded worker; GTK calls stay
on the main thread. Inputs remain local until Apply, even after preset loading.

Normal builds/tests do not touch hardware or install outside the repository.
`make control-test` uses isolated simulated Unix sockets; `make control-gui-test`
opens an isolated desktop smoke test with a tracked simulator and private
library. `make control-desktop` and `make control-service-install` are explicit
per-user installation targets. User service unit: letkid.service. Desktop ID:
io.github.letki.Studio. No firmware/CAD/option-byte changes accompany this rework.

API v1 uses a user-private0600 Unix socket,0700 directory, one UART worker and
bounded messages/clients. Static text/pixels use verified RAM uploads only;
there is no implicit flash write/fallback. Async acceptance is distinct from
completion: clients poll busy/last_error. Streaming leases reserve one owner,
expire, and use queued GRAY4 frames with CLOCK_MONOTONIC presentation deadlines.
Respect queue backpressure; StreamEnd drains pending frames and holds the last
one. Blank is immediate. Streaming preserves the loaded RAM/flash program and
requires96spare bytes. Never restore a flash show merely because Studio closes.

Explicit Disconnect releases UART and disables reconnect retries; the existing
native music player/picocom retain direct UART access after release. Do not
claim the music player has been transparently migrated to the service. Physical
status has no framebuffer/text readback. simulation_pixels is simulator-only.

## V3.2 five-board fabrication derivative (2026-10-17)

Read docs/v3_2-fabrication-20261017.txt and hw/ledkiv3.2/ASSEMBLY.txt.
The main CAD now derives from the frozen accepted v3_2-main-20261017 milestone:
1,489segments/299fixedvias/159fixedplacements. The dangling ADDR0stub was
removed, Q3source/R25bias widths restored and six generic passive MPNs selected.
Current identity is fabrication.json; baseline.json still records the frozen
accepted parent. Native ERC/DRC/opens/parity/ignored0 and independent76nets pass.
Updated power and label contracts preserve exact checked geometry/label intent.

Current checked exports: hw/ledkiv3.2/exports/fabrication-20261017-r2/; the old
exports/prototype/ is historical. Five-board population is727SMT,one pull-up
tile plus four ordinary, with0-5optional headers. Inventory report credits only
exact usable stock after existing holds; no reservations or consumption changed.
The separate new five-v3.1 batch competes for the same free LEDs; preserve the
user's v4.1 allocation and combined-cart record in the electronics repository.
No original-semiconductor substitution from a seller's generic cart is implied.

Logged-in JLCONE parameter quote still shows2USDautomatic offer plus1.50USD
Poland shipping before checkout charges; no coupon selected. Tented is disabled
on the current pre-upload four-layer form. Source tenting does not establish
compatibility with default ink Plugged: the conservative audit finds92vias
under the published0.35mmhole-to-mask-opening spacing. Manufacturing remains
HOLD_PROCESS until supplier confirmation resolves the ink-plugging spacing.
The user explicitly approved uploading GerberZIP SHA256915158c130250e109730ec0905c34a1a0d936819fc20d1acb7cbe0643fb99088
to their JLCONE/cart.jlcpcb.com account for quote/preview; it was uploaded and
detected correctly at4layers/49.6mm square. Reuse that authorization for this
payload/destination; do not ask again. Tented tooltip says free upgrade toPlugged.
No order/payment/support message, firmware or physical validation is authorized
by the handoff. Keep all frozen milestones and unrouted checkpoint unchanged.

V3.2 vendorDFM follow-up: docs/v3_2-dfm-20261017.txt. Currentr2 shifts only
two J2 silk-marker lines to clear their bare-pad gaps; native/all-net checks
pass and copper/vias/placements stay fixed. Corrected GerberZIP hash
c25f94e4ac97441caf86c49dc6ff55ba31d15a033d6fac6600037cd6acc220df is NOT yet
approved/uploaded: automatic review rejected the changed payload. Two async
questions cover that upload and the prepared JLCPCB support question separately.
Do not resend without the corresponding answer. Earlier upload915158...remains
authorized/completed. Keep raw vendorDFM findings visible; its NPTH classifier
and ink-plugging treatment are unresolved, not a reason to weaken native gates.

V3.2 final decision supersedes the preceding pending/hold instructions:
User explicitly approved corrected GerberZIPc25f94e4ac97441caf86c49dc6ff55ba31d15a033d6fac6600037cd6acc220df
to the same JLCONE/cart.jlcpcb.com account; upload and reference preview are
complete, detected4layers/49.6mm/qty5. User answered “thats no important lets
stick with defaults” to the supplier question: retain JLCONE default fabrication
and keep the support draft unsent. Do not request those approvals again.
The checked five-board fabrication/hand-assembly package and2USD+1.50USDshipping
quote(beforecheckoutcharges) fulfill this prototype handoff scope. Physical
qualification, newV006firmware, production-file engineering and purchases remain
outside it. Keep raw vendorDFM findings and the accepted-defaults decision;
never describe nativeCADchecks as an all-pass supplierDFM or physical result.

Studio Demo tab (2026-10-17): uses original shared host/pwm-show renderer for six
PWM scenes/showcase. Preview is local; explicit Play obtains a unique owned
LEVEL8 streaming lease (format2,160spare RAM bytes), with latest-frame queuing.
Leaving Demo/closing Studio releases only that UI's lease, retaining the final
frame. Core also accepts default GRAY4format1. Keep low ladder levels exact.

The same tab exposes the three existing song/video demos. Service music_catalog,
music_start and music_stop supervise a fixed companion-player command (no shell),
release UART before hardware playback and reconnect after exit. Reject missing
media and insufficientRAM before release; prevent competing mutations during
music playback. PC-only mode always passes --simulate. Video belongs on the PC.
Music continues after Studio closes; Escape/Stop ends it. Simulated/headless/
silent companion checks are suitable for tests and must never play real audio or
open physical UART. No flashing accompanies these host features.
