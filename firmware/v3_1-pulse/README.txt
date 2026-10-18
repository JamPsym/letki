STUDY C — HARDWARE ONE-PULSE TRANSISTOR CANDIDATE

make VARIANT=v3_1-pulse -j4
Default optimization for this variant only: -Os, WCH RV32E ABI unchanged.
Integrated tile: hw/ledkiv3.1/ledkiv3_1.kicad_pro
Electrical reference: archive/hw/ledkiv3.1-studies-20261015/pulse-study/ledkiv3_1_pulse.kicad_sch
Not for original v3. No flashing or physical qualification in this session.

Two retained v3 ICs; 8 AO3415A sources + 8 DMN2056U-7 sinks; reversed LEDs.
Each row uses ONE purchased33R1%0805 resistor (E12 nominal value).
Never run the earlier repetitive v3_1-mosfet driver with this population.
The prototype starts at brightness0 after reset. A deliberate b command enables
light; command0 deliberately selects100% and restores the sample/speed.
UART hw reports FW LETKI_V3_1_PULSE expects=33R/3V3. This identifies the
firmware profile, not the physically fitted resistor values or supply voltage.

LED datasheet: 20mA continuous, 80mA pulse ONLY at <=100us and <=10% duty,
at 25C. Both are stress ceilings. Initial operating illustration is ~35mA,
not 80mA. Actual LED Vf/current, temperature and optics require measurements.

SysTick 8kHz: 125us column slots, eight columns, 1kHz full frames.
Main's millisecond clock counts eight scan ticks. Timing constants are in the
local display.h; active v3 main.c/display.c remain unchanged.
TIM1/2: nominal 12MHz counters, 110us window (ARR=1319), PWM2, OPM=1.
Gamma 2.2 maps 0..100% to 0..960 ticks (80us). Minimum compare is 360:
30us initial blank. Counter rollover returns CNT to zero and clears CEN;
PWM2 then stays LOW even if the next scan ISR never arrives. There is no
software timer-unblank IRQ. Inactive rows remain GPIO LOW. Complementary
outputs remain disabled; SWIO/UART/I2C/buttons are preserved.

GPIO LOW before address changes retains the v3 anti-ghosting principle.
New gate/drain delays, actual interval/duty, startup/restart and scan execution
time must be checked on the transistor circuit. A timer gate pulse is not a
measurement of LED conduction; 80us leaves room below the 100us condition.
The nominal 15us tail gap depends on setup latency; no measured gap is claimed.
Shortest gamma pulses may be lost in the 1k/gate network. Keep that visible.

Host tests compile the real driver and follow WCH PWM2/OPM behavior in a
peripheral model, including all channels/brightness values, frame/brightness
latches, blank-before-address and continued OFF after skipped scan/timer IRQs.
They establish software/register intent, not silicon/electrical safety.
Separate schematic ERC and independent pin/net checks pass. The integrated
PCB is developed separately; check its README for current routing/release state.

First provision: R49 MUST be DNP, R38 fitted. A factory MCU may have PD7
configured as NRST, and the fitted R49/R38 network can hold it in reset.
Program/readback this image; separately authorize/set/readback PD7 GPIO
(RST_MODE11), power OFF, then fit R49. Do not perform option-byte or power
operations merely by building. See docs/v3_1-assembly-test.txt.

Before powered breakpoint debugging verify that TIM1/2 keep running on halt.
Timer freeze can hold a row gate HIGH. Qualify measured LED-current width
AND duty together: <=100us AND <=10%, with temperature derating. Delayed
interrupt service can compress pulse recurrence; nominal8% is not a measured
worst-case guarantee. Host tests cannot establish gate tails or optical output.

The normal text app is reused; this is not yet five-tile text-chain management.
Use make v3_1-interface-demos for communication-only UART/I2C images
that hold every row gate LOW. See firmware/v3_1-interface/README.txt.
Original-v3 interface images remain incompatible with the33R tile.
Five-tile future head targets 3.3V/3A with a reviewed transient envelope. Existing
Chinese converter modules are a temporary user-owned option, not qualified
by their printed rating. This session does not connect or power them.
ESP-12F and the custom power head are user-deferred until tile verification.
