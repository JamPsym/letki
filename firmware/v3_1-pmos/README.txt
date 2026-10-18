V3.1 PMOS Study A firmware

Build: make VARIANT=v3_1-pmos
Hardware: archive/hw/ledkiv3.1-studies-20261015/transistor-study/ledkiv3_1_pmos.kicad_sch
Details: docs/v3_1-transistor-study.txt

INCOMPATIBLE WITH ORIGINAL V3 WIRING. Do not flash this to the assembled v3.
This separate text-app variant replaces only the display driver; it uses the
existing SDK, application, startup/linker and 256-byte stack. Default stays v3.
The LED matrix polarity must be reversed and eight PMOS column sources fitted.

Differences: rows blank HIGH and sink when lit, main timer channels invert,
PC5/6/7 addresses use open drain and need 4.7k external pulls. Complementary
outputs, SWIO, UART, I2C and button assignments remain unchanged. Gamma, frame
buffers, 250Hz frames, 10kHz PWM and nominal 100us blank remain.

The driver is intentionally separate from the active v3 source. Host tests
exercise it against mocked GPIO/timers. No physical run/flash is claimed.
No programming target is added to Makefile; builds do not program hardware.
