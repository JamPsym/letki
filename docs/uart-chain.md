# V3 UART chain with one identical flash image

Prepared 2026-10-14 for the two assembled v3 boards. The chain is a serial
sequence with the PC as request source. There are no firmware master/slave roles.

```text
PC adapter TX
    → leftmost board J3.5 / URX / PD6
      leftmost board J1.5 / UTX / PD5
    → next board J3.5 / URX / PD6
      next board J1.5 / UTX / PD5
    → PC adapter RX
```

J3 is the left edge and J1 the right edge when viewed from the LED/front side
in KiCad. Adjacent right/left pin-5 edge pads connect upstream TX to downstream
RX. Do not tie multiple board TX outputs together or connect PC RX to a board RX.
All nodes and the PC adapter share GND. Both boards must be powered at compatible
voltages before traffic; establish one intended supply arrangement and retain
the original v3 C1–C3 ground repairs. The v3 UART pins are direct MCU connections,
without v4's buffers. Use the existing compatible adapter logic levels and short
edge links. The absent R11/R12 I2C pull-ups do not prevent this UART test.

Build the common image:

```sh
make VARIANT=v3-uart-chain -j4
```

Use **the same `build/v3-uart-chain/letki.bin` on both UUIDs**:

- Original: `d7-73-ab-cd-41-3f-bd-ff`.
- Second: `d7-6e-ab-cd-41-3a-bd-ff`.

One WCH-LinkE programs them sequentially. Verify identity, preserve two matching
full-flash backups and option bytes for each before programming, then verify the
image by readback. Preparing this firmware does not flash either board. The user extended standing firmware-update/test authorization to both identified
v3 boards on 2026-10-14; do not request it again for each test image. Both boards already have PD7 configured as GPIO;
preserve those option bytes and existing programmer power settings.

At 115200 8N1 each node validates, counts and forwards a packet, adding one hop.
All payloads carry a random PC token and CRC. Each downstream board performs the
same operation; the PC checks the final counter, token, checksum, hop count and
accumulated diagnostics. Each board discovers its volatile position from the hop
count. No UART boot/status chatter is emitted; SWIO is the local debug channel.

```sh
python3 scripts/uart_chain.py --list
python3 scripts/uart_chain.py --port /dev/serial/by-id/YOUR_ADAPTER --boards 2 --count 20 --report build/uart-chain/live-result.json
```

Close other programs reading the selected serial port. Send one packet and wait
for the full-chain return. The helper restores host tty settings on close,
including failure paths; it does not send restart, erase, option or power commands.
`uart_text.py`, `uart_demo.py` and the text TUI use other protocols and should not
be used to control this diagnostic image.

On the LED side, the first row has the ready pixel; the second row encodes board
position; the bottom two rows encode the last valid counter with bit 0 at the
left. The counters should match, positions should be 1 and 2. Source-side display
changes alone do not establish a return path: require the PC's checked replies.

Acceptance: 20 distinct checked requests returning with `hops=2`, matching token
and counter, valid CRC and zero cumulative diagnostics. Confirm matching counter
patterns on both matrices. Preserve raw output and the JSON report, firmware
hash, UUIDs, wiring and supply arrangement. CRC rejection, RX damage or overflow
preserves the last accepted counter; missing packets/timeouts fail the test.
Read SWIO `s` on an identified board to locate errors. Opening SWIO restarts only
the attached board, so save diagnostic evidence first.

The preparation tests cover multiple real C relay contexts, input corruption,
loss markers after queued prefixes, output backpressure, protocol limits and
host PTY framing/cleanup/error rejection. They do not prove physical chain
operation, signal levels, optical behavior or runtime stack high-water.

## Physical two-board UART-chain result (2026-10-14)

Both assembled v3 boards passed the complete PC TX -> left RX -> left TX ->
right RX -> right TX -> PC RX chain using the same 10136-byte image.
Left UUID: `d7-73-ab-cd-41-3f-bd-ff`; right UUID: `d7-6e-ab-cd-41-3a-bd-ff`.
Each board had two matching 16 KiB backups and complete image readback
verification; option bytes and programmer power settings were preserved.
User confirmed existing WCH-LinkE 3V3/GND power through the soldered bridge
and the LinkE TX/RX connection. The host serial device is
`/dev/serial/by-id/usb-wch.cn_WCH-Link_02858F0687B7-if01` (`/dev/ttyACM0`).

At configured 115200 8N1, all 20 distinct checked requests returned with two
hops, matching random tokens/counters and valid CRCs. Every accumulated
diagnostic count was zero. Right SWIO, held open during UART traffic, confirmed
`CHAIN position=2 counter=46665 ok=20 bad=0 drop=0 uart=0 txdrop=0`.
The original pre-initialization host tty settings were restored and verified.
Both boards retain UART-chain firmware; last accepted counter is 46665.
Matrix appearance was not independently inspected. Actual rail/baud/waveforms
and runtime stack high-water were not measured in this run. This confirms
physical two-board UART transport; two-board I2C remains untested, and it does
not qualify v4 buffers or resolve the measured v3 decoder-loading limitation.

Evidence: `build/board-readback/uart-chain-20261014/live-result.json`,
`uart-traffic.log`, `right/swio-live-test.log`, both board summaries/backups
and readbacks. Image SHA256:
`4b805c9b432766bb231e833b73fc7d17c398d1f9079c053c73f776992821f547`.
