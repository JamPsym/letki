V3.1 COMMUNICATION TEST — LED ROWS ALWAYS OFF

Build: make v3_1-interface-demos -j4
UART only: build/v3_1-interface/letki.{elf,hex,bin}
I2C controller: build/v3_1-interface-controller/letki.{elf,hex,bin}
I2C target: build/v3_1-interface-target/letki.{elf,hex,bin}
These are for the new 33-ohm MOSFET tile, not the original v3 LED wiring.
No command enables LEDs. display_present discards every status frame;
initialization stops TIM1/2 and drives all row gates LOW. SysTick only counts
milliseconds and clears row gates. Reserved interface/SWIO/button pins stay free.

UART1152008N1, Enter required. Startup and hw return exactly:
FW LETKI_V3_1_INTERFACE_LED_OFF expects=33R/3V3
Protocol: ping [TOKEN], status, mode uart/controller/target, send 0..65535,
auto on/off. Commands with arguments need a space, e.g. send 42.
The controller image starts counter exchanges every second; target address
is0x32. Both modes may be selected at runtime; mode changes stop automation.
The unchanged bus driver/protocol and further operator instructions are in
firmware/interface-demo/ and docs/interface-demo.md. Use THESE v3.1 binaries
in place of the original demo's images. Readback/identity/power/PD7 procedures
remain those in docs/v3_1-assembly-test.txt; building never programs hardware.

Use only ONE controller and ONE target for the two-tile CRC test. For five-tile
rise-time/loading checks leave the other three in UART mode (BUS_OFF); multiple
targets at the same0x32 address would acknowledge together and are not a
five-address network test. This does not implement ESP/head or tile addressing.
Restore/readback the matching v3_1-pulse image after qualification; it boots dark.

The shared SDK reserves384bytes of stack. The optimized controller has
7200bytes flash sections and1224bytes RAM including that stack. Static review
includes callbacks, reinitialization and SysTick; runtime high-water and actual
bus waveforms remain unmeasured. Host tests exercise the real driver with
all-on frame attempts, ensure no row-HIGH writes, preserve reserved pins and
run the real command/auto/CRC application paths. No physical test occurred here.
