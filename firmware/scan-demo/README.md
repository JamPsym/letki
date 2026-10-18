# V3 assembly scan demo

Build with `make VARIANT=v3-scan-demo`. The default remains text v3.
This separate application reuses the active binary display driver, SDK,
startup and 256-byte stack. It preserves SWIO and leaves UART pins unused.
PD7 must already be configured as GPIO in option bytes; the build does not
change option bytes or program hardware.

The automatic cycle shows eight horizontal rows from top to bottom, then eight
vertical columns from left to right (600 ms each), then all 64 individual pixels
in row order (150 ms each). It repeats at brightness 100. The shared driver
retains 250 Hz frames, PWM and 100 us GPIO-low blanking.
SWIO commands: `p` pauses, `r` resumes, `s` reports the phase, `h` shows help.
Reports and controls stay in the foreground; no connection is required to run.

Readback and live SWIO can verify programming/execution. LED orientation,
missing pixels, shorts and ghosting require physical observation; host checks
do not establish electrical or optical qualification.
