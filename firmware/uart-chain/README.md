# Identical v3 UART-chain test firmware

Build with `make VARIANT=v3-uart-chain -j4`. Every board uses the same
`build/v3-uart-chain/letki.bin`; no controller/target build selection or stored
board address. This is a separate connection-test app. The default v3 text,
I2C interface demos and wave/scan sources retain their separate build commands.

The PC originates requests. Every board receives on PD6/left URX, checks a
complete packet, increments its hop count, updates the counter display and
forwards a new checksummed packet on PD5/right UTX. The final UTX connects to
PC RX. Unsolicited boot/status/help logs stay on SWIO; they never become UART
traffic or commands at the next board. No firmware runs on the PC adapter.

The transport uses the active ISR-backed 64-entry RX FIFO and 128-byte TX queue.
Only foreground code parses/formats/forwards. A fixed pending output is retained
until the TX queue has space. Excess valid packets arriving while that output is
pending are counted as drops and leave the previous output/display state intact.
PC sends one request and waits for its return before the next. Damaged, incomplete,
oversized or bad-CRC frames leave the display intact and produce no reply. A new
`@` resynchronizes input. Local error/drop counts accumulate into subsequent
valid packets; the PC rejects a nonzero cumulative diagnostic count.

Wire format: `@`, 28 hexadecimal digits, CRLF (LF input also accepted). The
14 decoded bytes are:

| Offset | Field |
| --- | --- |
| 0 | Protocol version 1 |
| 1 | Hop count, initially 0 |
| 2–3 | Display counter, uint16 little endian |
| 4–7 | PC token, uint32 little endian |
| 8–11 | Cumulative diagnostics, uint32 little endian; saturating addition |
| 12–13 | CRC-16/CCITT-FALSE over bytes 0–11, little endian; initial 0xffff |

At each board the hop count increments and CRC is recomputed. Hop 255 is the
encoding limit; a further hop is rejected. This is not a qualified maximum chain
length. A missing reply is a failed/incomplete test, not a successful echo.

Display: top-left ready pixel, second row shows the discovered position in binary
(bit 0 at the left), bottom two rows show the last valid counter (bits 0–7 then
8–15). Counter bits should agree on both boards; position should differ (1, 2).
SWIO `s` reports position/counter/accepted/rejected/drop/UART diagnostics; `h`
shows help. Opening the SWIO terminal restarts its attached board and clears that
board's volatile counters; record failures before restarting.

The shared binary driver preserves gamma brightness 100, 250 Hz full frames,
nominal 10 kHz PWM, 100 us GPIO-low blanking, both frame buffers and PD1 SWIO.
PC1/PC2 I2C pins remain unused; I2C pull-ups are not required for this UART test.
Both boards must already have PD7 GPIO option configuration. No build changes
option bytes or flashes a device. The app retains a 256-byte stack.

Current build: 10,136 image bytes and 976 RAM section bytes including stack.
Compiler reports plus leaf division-helper disassembly give a conservative
148-byte foreground path plus 48 bytes for all three ISR paths, total 196.
The deeper UART initialization path is 172 bytes and occurs before scan IRQs.
Evidence, common-image snapshot and hashes are in `build/uart-chain/`.

Host/register/PTTY tests and compilation establish preparation only. The physical
two-board UART chain subsequently passed 20 checked two-hop replies with zero
cumulative diagnostics on 2026-10-14; see the wiring guide for evidence.
Waveforms and runtime stack high-water remain unmeasured.
Read [the wiring and PC test guide](../../docs/uart-chain.md) before connecting.
