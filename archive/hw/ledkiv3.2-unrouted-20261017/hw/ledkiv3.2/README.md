# Letki v3.2 — unrouted QSOP24 study

Open `ledkiv3_2.kicad_pro`. This is a new revision; v3.1 is preserved.
CH32V006E8R6/QSOP24 supplies eight row PWM outputs, west-to-east USART1,
south-to-north USART2, common I2C service and independent decoder blanking.

The board is 49.6 × 49.6 mm with 6.2 mm pixel spacing across both seams.
All tiles stay upright. J3 receives from west, J1 transmits east; J5 receives
from south, J4 transmits north. Opposite contacts share geometric pad order.
J2 retains local SWIO; TP1/TP2/TP3 provide RESET/SWCLK/spare access.
Four M2 holes occupy gaps between LEDs. Mechanical fit remains untested.

Native KiCad 10.0.7 checks: ERC0, physical DRC0, parity0, ignored0;
**307 unconnected items**. 159 footprints, four layers, no tracks/vias/zones.
This is a placement study for review, not a fabrication package. Routing,
firmware implementation and physical qualification remain.

See `../../docs/v3_2-study.txt`, `../../docs/v3_2-network-update.txt` and
`../../config/v3_2-study.json` for pin assignments, architecture and evidence.
The existing v3/v3.1 firmware is incompatible with this wiring. Do not flash it.

Custom symbols and footprints are local; 3D models use local dependencies
plus the installed standard KiCad 10 model library. Standard model dependencies
were checked on this workstation; models do not qualify assembly fit.
The new QSOP24 V006 is a proposed purchase, not the stocked V006/TSSOP20.
No purchase or stock reservation is implied.
