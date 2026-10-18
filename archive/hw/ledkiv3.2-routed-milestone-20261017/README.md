# Letki v3.2 — routed CAD prototype

Open `ledkiv3_2.kicad_pro`. CH32V006E8R6/QSOP24, 49.6 mm square, 6.2 mm pixels;
west-to-east USART1, south-to-north USART2, shared I²C and separate LED blanking.
All 159 original component placements and padstacks are preserved.

Native ERC/DRC/opens/parity/ignored: **all zero**. Independent continuity confirms
all 76 nets; manufacturing, exact pin/net and assembly-label checks pass.
Power uses In2 VCC plus stitched front reinforcement; In1 has seven explicitly
reviewed signal segments on two nets. See [routing and limits](ROUTING.txt).

The full unrouted checkpoint for human routing is
`../../archive/hw/ledkiv3.2-unrouted-20261017/` from the repository root;
copy its complete folder before editing. v3.1 remains preserved.

Checked exports belong in `exports/prototype/`. This is CAD for a prototype;
physical electrical/mechanical tests and fabricator process confirmation remain.
The existing v3/v3.1 firmware is incompatible; the new application and custom
loader have not been implemented or flashed. The older diffuser does not fit.
No stock reservation or purchase is implied.
