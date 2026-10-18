# Local display API v1

Connect to `$XDG_RUNTIME_DIR/letki/display.sock` with a Unix stream socket.
Without XDG_RUNTIME_DIR, use `/tmp/letki-UID/display.sock`. Send one UTF-8 JSON
object plus LF and read one JSON object plus LF. Each connection handles one
request. The socket is private to the user; no TCP/HTTP server is exposed.

Every request includes `"v":1` and `"op":"…"`. Replies include `v`, `ok` and
an `error` string on failure. Input limit64KiB, output128KiB, at most16 concurrent
clients, two-second incomplete-read limit. Strings must be valid UTF-8 without
NUL. Pixel arrays must contain exactly320 integers0–100 in global row-major
order: index=`y*40+x`. Tile=`x/8`.

| Operation | Extra request fields | Result / behavior |
| --- | --- | --- |
| `status` | none | Connection/busy state, `last_error`, node IDs/counters/RAM, lease owner, history |
| `preview` | `draft`, optional `position_ms` | Exact simulated pixels, bytes, tracks, width, duration, capacity/fits; no hardware action |
| `connect` | optional `simulate:false`, `port:""` | Read-only handshake, automatic discovery if port empty; enables reconnect |
| `disconnect` | none | Releases UART and disables reconnect; display continues |
| `text` | `draft`, optional `client` | RAM upload/readback then synchronized standalone playback |
| `pixels` | `pixels:[…]`, optional `client` | Same upload flow with exact LEVEL8 static picture |
| `pause`, `resume`, `restart`, `blank` | none | Playback controls; Blank may interrupt a stream |
| `stream_begin` | `owner`, optional `ttl_ms:3000`, `format:1` | Prepares GRAY4(1) or LEVEL8(2) queues, grants random `lease` token |
| `stream_frame` | `lease`, `pixels`, optional `deadline_ms` | Queues a synchronized frame and renews lease |
| `stream_end` | `lease` | Drains pending presentation, holds last frame, releases ownership |
| `music_catalog` | none | Three existing local song/video shows and availability |
| `music_start` | `id`, optional `simulate:false`, `wayland_display`, `display` | Hands UART to companion player, opens PC audio/video/simulator; reconnects afterward |
| `music_stop` | none | Requests graceful player exit and UART recovery |

Mutations are asynchronous. An `accepted:true` response means queued, not
completed. Poll `status` until `busy:false`, then require `last_error:""`.
`applied` increments after exact upload/readback. `streamed` counts accepted
hardware frame transfers. Busy replies require producer backpressure; do not
spin without waiting. Read-only status/preview remain available during work.
Status also reports `baud`, cumulative connection `transport_retries` /
`transport_invalid`, the last `frame_transfer_ms`, and rolling `stream_fps`.
`stream_late` counts transfers completed after their presentation deadline;
`stream_dropped` counts frames discarded before transfer when already stale.
Stream timing counters reset at stream setup; they are host measurements, not
optical presentation measurements. Node counters refresh during inspection.

A draft contains:

```json
{
  "text":"ZAŻÓŁĆ GĘŚLĄ JAŹŃ",
  "font":"large",
  "motion":"bounce",
  "speed":75,
  "brightness":100,
  "minimum":5,
  "modulation":"breathe",
  "pulses":2,
  "loop":true
}
```

Defaults: compact font, scroll,75ms/pixel, brightness75, minimum5, steady,
2pulses, loop=true. Font accepts `compact|large|bold`, motion
`scroll|bounce|fall|still`, modulation `steady|breathe|blink`. Speed10–500;
brightness/minimum0–100; pulses1–6. Minimum may not exceed peak under modulation.
Text normalizes to NFC and uppercase, including Polish glyphs. Unsupported
characters reject the draft. Still text wider than40pixels clips; other modes
pan or move the full bitmap. Text cycle length is not globally limited to60s;
each interpolation track is split at that bound, up to16 tracks and available
RAM. No operation silently falls back to flash.

Preview responses always describe the submitted draft. `fits:false` permits a
preview but prevents Apply. Status does not read back physical pixels or recover
text from arbitrary board programs. `simulation_pixels` exists only on simulated
connections and comes from the real C interpreter.

## Streaming ownership and timing

`owner` is a human-readable1–80byte name, `ttl_ms`500–10000. Keep the opaque lease
token private to the owning client. Another app may inspect status/preview, but
cannot replace text, change connections or acquire another stream until release
or expiry. Blank is an intentional emergency override.

Wait for stream setup to complete before sending frames. The loaded RAM program
must leave at least96bytes per tile for two GRAY4 slots, or160bytes for LEVEL8. A short/static program
leaves more queue space. Streaming never modifies the loaded program or flash.
When the lease expires, ownership is released and the last frame remains.
Physical streams automatically use the previously qualified230400baud and
return to115200 on release. Setup/release may take about two seconds for the
coordinated baud switch; wait for `busy:false` before the next operation.

`deadline_ms` uses the PC's absolute CLOCK_MONOTONIC epoch in milliseconds,
40–1000ms in the future; e.g. Python `int(time.monotonic()*1000)+150`.
The service translates this into each tile's synchronized clock. Omission uses
120ms lookahead. GRAY4 quantization has16levels; LEVEL8 retains exact0–100 values, using the same
existing chain driver as the music player. Actual UART/CPU/queue capacity limits
frame rate: busy means retry/pause the producer. In particular, two slots with
120ms lookahead cannot accept an unlimited burst. The broker reserves queued
presentation slots before accepting a frame and normal stream termination waits
for scheduled presentation before flushing.
For animation, render pixels for the requested presentation timestamp rather
than the send timestamp. Keep the newest frame and retry busy responses after a
short wait; do not accumulate stale animation frames on the PC.

```sh
# Feed newline-separated JSON arrays, each with320levels, until EOF/Ctrl+C.
build/control/letkictl stream my-visualizer < frames.ndjson
```

Direct UART applications must first request Disconnect. They should close UART
before asking the broker to Connect again. The current native music player
retains its direct transport. `music_start` explicitly supervises that handoff
for the three built-in shows (`tubular-bells`, `my-cyganie`, `adagio`). While a
song owns the player, other mutation requests are rejected. Music status is
reported separately as `music_active`, `music_title`, `music_state` and
`music_error`; disconnected UART during hardware playback is intentional.
Video remains on the PC. Missing media/player is rejected before UART release.
Optional `silent:true`, `headless:true`, `duration_ms` allow bounded offline
checks; tests always combine these with `simulate:true` to avoid audio/hardware.
