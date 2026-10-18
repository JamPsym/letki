Letki general firmware — 2026-10-17

STATUS: IMPLEMENTED, ASTRA-REVIEWED AND TESTED ON ALL FIVE V3 BOARDS.
R3 physical qualification and its measurement limits are recorded in
docs/general-firmware-hardware-20261017.txt. Full working backups are preserved.

BUILD AND OFFLINE USE

From the repository root:
  make general-images STACK_USAGE=1 -j4
  make general-test
  make general-preview
  python3 scripts/letki_general.py --simulate inspect

Preview GIF/contact sheet: build/general/preview.gif and preview.png.
The preview, program compiler and firmware use the same C timeline interpreter.
No build, test, preview or resource-export command programs hardware.
New variant: v3-general; default v3 and all historical/demo variants remain available.
Head/tile1..tile4 images are in build/v3-general-ROLE/.

USING THE FIVE-BOARD GENERAL FIRMWARE CHAIN

Close picocom. Build the host library with make general-host. Examples:
  python3 scripts/letki_general.py inspect
  python3 scripts/letki_general.py text 'ZAŻÓŁĆ GĘŚLĄ JAŹŃ 123!' --mode scroll
  python3 scripts/letki_general.py text 'LETKI DZIAŁA' --mode fall
  python3 scripts/letki_general.py load config/general/demo.json --play
  python3 scripts/letki_general.py load config/general/demo.json --storage flash --replace safe --play
  python3 scripts/letki_general.py load LARGE.json --storage flash --replace capacity --play
  python3 scripts/letki_general.py stream config/general/demo.json --fps auto --format gray4
  .tools/native-tts/bin/python scripts/letki_general.py audio config/general/narrated.json build/pwm-show/audio/score.wav
  .tools/native-tts/bin/python scripts/pwm_board_audio.py --general --baud 230400 --loop
  python3 scripts/letki_general.py pause
  python3 scripts/letki_general.py seek 5000

--port PATH, --simulate and --baud RATE are global options BEFORE the subcommand.
--baud supports 115200/230400/460800/921600. Use 230400 for raw streaming on this
chain: the complete narrated demo passed at22fps with no skipped/late uploads or
added UART errors. A later retained-flash run needed18fps to absorb retries
without late/skipped frames; use an explicit lower --fps when auto is too fast. 460800 failed the PC-to-head zero-error check;921600 is not
qualified. Default and recovery remain115200. Higher options remain explicit
experiments rather than recommended settings.
The driver negotiates baud, restores 115200 on close, and restores original tty settings.
An unconfirmed switch falls back after two seconds; confirmed high baud has a ten-second
idle lease renewed by addressed session traffic. Reset starts at 115200. Other serial
readers are rejected instead of being closed. Use Driver as a context manager in Python.

Normal load uses RAM if it fits, reclaiming frame slots when needed; otherwise it
selects flash-safe storage. Explicit --storage flash requests persistence.
--replace safe retains the current object until a validated replacement commits, but
requires sufficient staging space; stopped flash maintenance is blanked.
--replace capacity permits discarding the old object to maximize capacity. A power cut
in that mode can lose the show; it cannot address the application or option bytes.
Repeated play/stream operations do not write flash; identical active program uploads
are readback-compared and reused, avoiding both RAM staging failure and flash wear. Flash startup selects the newest
valid manifest. An invalid/unfinished show boots idle, never partially executed.

PROGRAMS AND MEMORY

A program is one LGS1 blob containing up to 16 simultaneous timed tracks and deduplicated
bitmap assets. Text is converted to bitmap assets by the PC, including compact Polish
uppercase glyphs, digits and common punctuation. Other glyphs/images can be supplied as
bitmaps without changing firmware. Tracks support hold, linear and triangular motion,
repeat-x, intensity interpolation, clipped drawing and fills. Finite duration and loop
are independent; positions come from absolute time, making seek deterministic.

Maximum shared RAM arena: 752 bytes/node. Default two LEVEL8-sized slots leave
592 bytes for a program. Queue configuration selects 0..16 slots, subject to actual
space, with 24/48/80 bytes per slot for MONO1/GRAY4/LEVEL8 respectively. Streaming uses
as many slots as the arena permits, retaining flash programs when all tiles have
one; otherwise it installs a minimal idle RAM program. Reconnect
reports actual capacities/credits; do not assume the simulator's nominal flash size.
The native current images use 2036/2048 RAM bytes INCLUDING the 256-byte stack.
This is deliberately tight: 12 bytes remain outside the reserved stack. Compiler stack
reports assess 188 foreground + conservative 48 ISR = 236/256 bytes. Runtime stack
high-water is NOT measured. See the frozen manifest and final review notes.

Flash pool starts at the linked image end rounded up to 64 bytes. Each node reports
its actual safe A/B and maximum-capacity sizes. Native current head: 1472-byte safe
program or 3008-byte capacity program on every current R3 role.
Both modes include program/assets in that size; metadata and executable space are
excluded. The host simulator uses a 4096-byte backing store to exercise both policies,
so its advertised flash capacities differ from the native target.

Python API: scripts/general_link.py (Driver, Serial, Simulation, TimedSimulation),
scripts/general_program.py (compile_show, text_show), scripts/general_audio.py.
Driver.load accepts either one shared blob or one blob per tile, so a PC driver can
partition assets/use different local programs. Safe RAM replacement can keep the
current program running during upload. Driver.load(next_blob, start_at=host_ms)
validates and schedules a segment switch without an intervening blank. Old+new must
fit; there is one pending segment credit, and a further safe load returns BUSY until
it has switched. Long scores can replenish segments indefinitely; they do not need
to fit the whole score in board memory. A single compiled track's motion period is
bounded to 60000 ms; holds/show durations may be much longer. Complex/large content
can use raw streaming. Its PC source assets are host-owned and are not constrained
by the target RAM/flash capacity (compiled source objects still have the u16 size
limit and the same 16-track interpreter limit). Delta/RLE and an arbitrary multi-object filesystem are not v1
features; the stable arbitrary-pixel path avoids requiring new effect firmware.

TRANSPORT, CLOCKS AND FAILURE BEHAVIOR

COBS/CRC16 binary packets travel directly along the existing UART chain. A node
consumes its addressed request and replaces it with a response; other complete valid
packets are forwarded. No string relay is used, and NUL payload bytes are preserved.
One outstanding request per node; multi-node batches pipeline. Flash maintenance is
serialized globally because a writing node may temporarily stall forwarding.
Session/request caches make bounded retransmissions idempotent, including flash writes.

I2C at 100 kHz carries only a seven-byte clock beacon every 100 ms. The head uses
address-zero general call; receivers explicitly enable ENGC (documented in WCH RM v1.9,
chapter 14). Beacon magic 0xc1 + head milliseconds + CRC16 avoids reserved general-call
command values. No I2C pixel copies or per-receiver I2C response are required.
TIME reports age since a valid clock beacon; 65535 means unavailable/regressed.
Unexpected head-clock regression is latched until a new UART session rearms it.
Standalone synchronization depends on this clock path; a stale clock path can drift.
All four receiver clock ages are checked during physical qualification. Beacon
freshness is a software diagnostic, not a measurement of optical skew. The head
bounds idle BUSY waits and resets the I2C peripheral after20ms; this does not
repair a physically held-low SDA/SCL line.

SysTick is free-running at HCLK with explicit 500-us compare scheduling for display
refresh. Foreground time accumulation handles counter rollover and continues across
blanked flash maintenance; refresh interrupts can be suspended without freezing the
show clock. Poll the 32-bit cycle counter at least once per hardware wrap (~89 seconds
at 48 MHz); ordinary bounded operations are much shorter. PWM remains hardware-driven
with the existing GPIO-low blanking. This application-specific timebase needs physical
scan/waveform validation after review.

The PC estimates clock offsets and uncertainty and sends absolute local deadlines.
A loaded audio show uses the DAC presentation epoch and refreshes clock mapping every
five seconds. No waveform time stretching. Raw streaming queues future frames with
measured upload pacing and skips obsolete independent frames. Frames stage per tile
then commit at the common deadline, with up to one scan of local latch delay. A broken
link during commit can produce partial presentation; this is not global rollback.
READY/COMMITTED replies do not claim optical visibility. STATUS includes desired and
scan-boundary PRESENTED generations for raw frames, including generation wrap.

On PC disconnect: loaded programs continue; streamed queues drain then hold the last
complete frame. PAUSE/SEEK/PLAY cancel old queued raw frames. Invalid packets/programs
cannot publish partial objects. CRC damage, overlong frames and receive-error flags
resynchronize at a delimiter. User-selected capacity replacement can intentionally
invalidate the old object. Diagnostics include UART errors, dropped TX replies, late
frames, queue credits, memory, UUID, upload/switch state and clock age.

VALIDATION AND REVIEW

See docs/general-firmware-protocol.txt for the exact v1 wire/content contract;
docs/general-firmware-review-20261017.txt for the review history and
physical qualification; build/general/review-candidate/manifest.json for frozen images,
source hashes, native capacities and stack estimates. All physical claims for the
previous PWM/audio demo are separate; current physical results have their own
record in docs/general-firmware-hardware-20261017.txt.

Validation commands:
  make test
  make all-variants -j4
  make renderer-test
  make -f host/general/Makefile sanitize
  make VARIANT=v3-general ROLE=head compdb
  clangd --check=firmware/general/User/main.c --tweaks=
  python3 scripts/general_resources.py
The last command copies already-built images and reports native limits; it never
programs a board. Protocol/request and frame IDs wrap; long-running loaded shows
periodically rebase their clock anchor to preserve phase through millisecond wrap.

The original six-scene PWM/music demo is adapted by pwm_board_audio.py --general.
Its default invocation without --general still targets the older working PWM image.
New firmware needs the flag. --baud 230400 is the measured streaming setting;
the raw player selects a nominal rate from acknowledged uploads. This keeps all
six original effects on the PC rather than adding them to the device interpreter.
Raw audio streaming refreshes the PC/DAC epoch and board clock mapping periodically
so long shows do not depend on a single startup clock-offset estimate.

Astra final review (2026-10-17) approved identified-board programming after the
two reviewed timing fixes and fresh builds. The user authorized automatic Astra
review/completion and asks only for SWIO moves. Subsequent hardware evidence is
recorded separately in build/board-readback/general-20261017/.
After independent receiver restart at a long-running head clock epoch, reconnect
and issue PLAY to re-anchor the timeline; seamless reboot/rejoin is not promised.

Raw streaming samples per-tile UART timestamps without waiting for I2C freshness.
It therefore remains usable without the shared clock bus. Samples retain beacon
age diagnostics. A significant clock-offset change flushes queued frames and
reanchors future uploads; frames already presented/queued before detection can
still be affected. Standalone PLAY and loaded audio require fresh I2C beacons.
Frame-stage retries use250ms and periodic TIME retries100ms; multiple losses or
forced excessiveFPS can exhaust lookahead. Late/skipped uploads are reported.
PC telemetry retains lifetime totals and only4096 frame/1024 audio samples, with
128 warning samples, so looping playback does not accumulate unlimited logs.

Persistent A/B updates require an existing safe-bank layout or an idle node.
A current RAM object needs an explicit stopped/discarding transition; a maximum
capacity object occupies both banks and cannot be preserved while converting to
A/B. The protocol exposes separate storage/policy fields for a custom PC driver.
Use --replace capacity when explicitly maximizing a persistent object's size.


If every tile has an active flash program, raw streaming keeps those programs
intact. Run `python3 scripts/letki_general.py play` afterwards to start the saved
show at position0. If any tile has a RAM or empty program, streaming replaces
all active programs with a minimal RAM object to maximize queue capacity; saved
flash bytes still remain available after restart. Use explicit seek/play position
when returning to a particular point in a show.


FINAL QUALIFIED CHAIN

All five R3 role images and full3008-byte saved-program restarts passed. The chain
is left running config/general/demo.json from safe A/B flash (228 bytes/node),
brightness100. Normal content/control updates use UART and need no SWIO moves.
User repaired the intermittent head S5 connection by resoldering and reported
it appears okay; electrical/optical metrology and runtime stack high-water
remain unmeasured. See docs/general-firmware-hardware-20261017.txt.

The final38.4-second narrated raw PWM run passed at18fps/230400 with0late/skipped
frames, no added UART errors/drops and no audio warnings.15ACK retries were
absorbed by lookahead; auto22fps is not guaranteed on every run. Reuse the existing
prepared score (or run pwm_board_audio.py --general once to prepare it):
  .tools/native-tts/bin/python scripts/letki_general.py --baud 230400 stream config/general/pwm-show.json --fps 18 --audio build/pwm-show/audio/score.wav
  python3 scripts/letki_general.py play
The second command restarts the retained saved show at position0 after streaming.
