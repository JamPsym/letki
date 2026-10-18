STUDY B — 16 MOSFETS, SCHEMATIC CANDIDATE ONLY

Build: make VARIANT=v3_1-mosfet
Circuit: archive/hw/ledkiv3.1-studies-20261015/tme-study/ledkiv3_1_tme.kicad_sch

Requires 8 AO3415A column sources and 8 DMN2056U-7 row sinks, reversed LEDs,
100-ohm row resistors, external address pullups and a common 3.3V +/-5% rail.
Do not flash this image on an original v3 or on the eight-PMOS Study A circuit.
This design session does not access or program boards.

The local display.c derives from active v3: row gates blank LOW, main PWM
is active HIGH, complementary outputs remain disabled. Only PC5/6/7 output
mode changes to open drain for the external 4.7k address pulls. Scan timing,
100us blank, gamma table, buffers and all other application modules are reused.
Active v3 and Study A drivers remain separate and unchanged.
The user-confirmed v3 ghosting fix is retained: force rows to GPIO LOW before
changing columns, then return only lit rows to PWM after TIM2's 100us blank.
This firmware issue is resolved on v3. New MOSFET switching must fit within
the inherited blank; no new transistor hardware has been tested here.

Host tests exercise real driver register writes, all gamma settings, all row
channels, blank-before-address sequencing and scan-boundary buffer updates.
They do not qualify MOSFET switching, optical brightness or supply behavior.
The shortest gamma pulses are 83ns; 1k gate resistors and gate charge may make
the lowest settings ineffective. Physical scope/optical checks are required
before adopting a minimum pulse or changing PWM timing.

The active startup, interrupt paths, RV32E ABI and 256-byte stack reservation
are reused. No new call path or RAM buffer is introduced by this driver copy.

For higher current see separate Study C / v3_1-pulse. Never use this
repetitive driver on the 34-ohm pulsed-current circuit.
