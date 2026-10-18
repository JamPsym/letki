# Letki Studio and display service

Native GTK4/libadwaita Studio is a client of `letkid`, the small display broker.
The broker coordinates UART ownership. The GUI, command-line client and other local apps use
its versioned Unix-socket API. There is no Qt, browser engine, Python playback
runtime or MCU update in this application.

```sh
make control
make control-run
make control-test
```

Dependencies on Arch: `base-devel pkgconf gtk4 libadwaita json-c`.
Python is used only by integration tests. The broker itself links GLib and
JSON-C; it does not load GTK, audio or video libraries.

## Studio

- **Compose**: Polish text, three fonts, scroll/bounce/fall/still, speed,
  peak/minimum brightness, Breathe/Blink and pulse count. Preview uses the actual
  C firmware interpreter. Edits stay local until Apply, including after loading
  a preset. Ctrl+Enter applies the selected editor.
- **Pixel canvas**: paint a single 40×8 picture across the five tiles with a
  0–100% brush. Clear/invert and saved pictures support quick experiments.
  Apply stores a standalone 368-byte LEVEL8 bitmap in RAM.
- **Library**: named text and pixel presets, editable locally before sending.
  Drafts and library live in ignored `build/control/studio-library.json`;
  first launch migrates the earlier `draft.ini` without altering that file.
- **Diagnostics**: real board IDs, per-tile RAM, receive/drop/late counters,
  connection status, service messages, streaming owner, UART baud, frame rate
  and transfer timing/retries. Diagnostics expose
  no physical framebuffer or arbitrary text readback.
- **Demo**: the original six PWM scenes and a continuous showcase, with local
  preview, speed/brightness controls and Play/Stop. Display playback uses LEVEL8
  to preserve fine Light ladder levels;160 spare RAM bytes are required.
  Leaving this tab or closing Studio stops its visual stream and holds the last
  frame. Resume returns to the loaded show. Display frames are rendered for
  their future presentation time to match the live PC preview.
- **Music + video** in Demo: five catalog-driven shows, including
  Tubular Bells, My Cyganie, Adagio, L’Amour Toujours and Laskowski × 2Pac.
  Play opens the existing native player with PC video above the simulator.
  The broker hands UART to the player and reconnects when it exits. PC-only
  playback is explicit. Stop music or Escape ends it; music can continue after
  Studio closes. Local recordings and `make player` are required. Physical
  playback needs160 spare RAM bytes. Video never supplies LED pixels.
- **Playback**: Pause, Resume, Restart and Blank. Pause freezes the text/PWM
  timeline. Resume restores global brightness; Blank is also an emergency way
  to end another client's stream.

Preview and painting never write to a board. All uploads explicitly use RAM,
validate capacity before mutation and read back every byte on all five nodes.
Long cycles split into tracks of at most60s. Up to16 tracks share one bitmap;
RAM capacity remains the practical limit. Applied text/pictures run standalone
when Studio closes. Power cycling restores the existing flash show.

```sh
build/control/letki-control --simulate
build/control/letki-control --no-connect
build/control/letki-control --demo          # open Demo; nothing plays automatically
build/control/letki-control --socket /path/to/private/display.sock
```

The first GUI client starts a missing broker. Closing a GUI leaves the broker
running for other apps. Existing broker settings are not silently changed.
Simulation is explicit and cannot apply through an existing hardware session.
A second client never opens another serial connection.

## Broker and command line

```sh
build/control/letkid --simulate --socket /tmp/my-private-directory/display.sock
build/control/letkictl status
build/control/letkictl text 'CZEŚĆ ŁÓDŹ' --font large --motion bounce \
  --brightness 100 --minimum 5 --modulation breathe --pulses 2
build/control/letkictl pause
build/control/letkictl resume
build/control/letkictl blank
```

`letkictl --socket PATH …` selects a broker; `--start` may start a missing one.
CLI replies are JSON. Accepted mutations run on one background worker; poll
`status` until `busy:false`, then inspect `last_error` for completion. An
accepted request is not yet a successful physical upload.

The socket defaults to `$XDG_RUNTIME_DIR/letki/display.sock`, with a private
`/tmp/letki-UID/` fallback. Its parent must be owned by the current user with
mode0700; socket mode is0600. The service listens only on a Unix socket, with no
TCP port or LAN exposure. A lock prevents duplicate brokers from replacing a
live socket. Requests/replies, connection count and queues are bounded.

To install desktop integration and a persistent user service:

```sh
make control-desktop
make control-service-install
systemctl --user enable --now letkid.service
journalctl --user -u letkid.service -f
```

These explicit install targets write generated paths to the user's XDG desktop
and systemd directories. Normal builds do not install or start hardware services.
Re-run installation after moving the checkout. No administrator service or root
privileges are needed at runtime; existing serial-device permissions still apply.

Before running the existing direct music player or picocom, release UART:

```sh
build/control/letkictl disconnect
# run the direct player / picocom, then close it
build/control/letkictl connect
```

Explicit Disconnect disables automatic retries until Connect. The service never
kills another program using the port. Read-only automatic reconnects preserve
board content. The current music player retains its direct high-rate transport;
it has not been silently converted to the broker.

## API for other applications

See [the v1 API](API.md) and [standard-library Python example](examples/display.py).
Send one UTF-8 JSON object followed by a newline and read one response, using a
new connection for each request. Example:

```json
{"v":1,"op":"text","draft":{"text":"HELLO","motion":"scroll","font":"large","brightness":80}}
```

Static pixels retain exact0–100 levels. Real-time streaming uses the existing
firmware's GRAY4 (default,16 levels) or LEVEL8 (exact0–100) queues, common display-clock deadlines and a short
exclusive lease. Other apps receive a clear owner/busy reply while a stream
owns the display. Queue backpressure returns busy before overflowing; retry or
slow the producer. Lease expiry and normal release hold the last displayed
frame. No saved show or flash program is overwritten by a streaming session.

Streaming requires at least96 spare bytes for two GRAY4 queues, or160 for LEVEL8. Apply a shorter
message first if the loaded RAM program uses too much space. A normal stream
end drains scheduled frames before releasing ownership. Blank stops immediately.
Streams use the previously qualified230400baud, then return to115200 on release.
The GUI keeps fresh frames under backpressure rather than accumulating a delay.
Five-tile LEVEL8 streaming measured15.5fps in a nine-second broker test and
14.4fps through the GTK Demo tab, versus4.6fps before this repair. Fresh counters
on all five boards showed no added UART errors, drops or late frames. Clean
release restored115200baud and kept the102-byte RAM program on each tile.
These are measured runs, not a guaranteed maximum or optical timing measurement.
Evidence: `build/control/lag-fast-first.json`, `lag-gui-physical.json` and
`lag-gui-after.json`; simulated regressions and GUI smoke results are in
`lag-tests.log` and `lag-gui-test.log` in the same directory.

## Verification and limits

`make control-test` runs the real-C simulator suite and isolated service/CLI
integration tests: fonts/Polish UTF-8, PWM extrema, multi-minute programs,
capacity rejection before mutations, exact RAM readback, streaming/presentation,
lease conflicts/expiry, concurrent clients, malformed/bounded input and clean
socket cleanup. It never discovers physical UART. Unix sockets must be permitted
by the test environment.

`make control-gui-test` opens a short GTK smoke test with an isolated simulated
broker and test library. It needs an active desktop. `make -f
host/control/Makefile sanitize` runs the core under ASan/UBSan. Earlier Qt-only
UI/tests were removed; the firmware font tables and C interpreter remain shared.

Connection handshakes/status are read-only. A multi-board upload is not atomic:
a failed Apply can leave some boards paused or with newer RAM content. The
service reports failure and retains local drafts; reconnect and retry Apply.
This rework does not change firmware, flash, option bytes, power or CAD. Host
simulation tests do not establish electrical or optical behavior.

Music rows, descriptions, availability and playback IDs come from the service's
`music_catalog` response. Studio refreshes the list every five seconds; adding a
catalog entry no longer requires a separate hard-coded GUI button. Unchanged
catalog metadata preserves the widgets and keyboard focus during polling.
