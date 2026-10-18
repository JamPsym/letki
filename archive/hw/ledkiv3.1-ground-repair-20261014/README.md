# Letki v3.1 hardware

V3.1 preserves the v3 circuit, placement and board outline, and incorporates the demonstrated repair of the disconnected C1/C3 ground network. The original v3 remains in `archive/hw/ledkiv3/`.

Open `ledkiv3_1.kicad_pro` in KiCad. The schematic and PCB use the matching `ledkiv3_1` project name. The existing diffuser was copied unchanged, including the user's earlier model modifications. Active `firmware/v3/` still uses the same pin map.

The repair adds a through GND via at (45.076, 78.000) mm, with 0.5 mm copper and a 0.3 mm drill, plus a 0.25 mm front-layer trace to the existing ground via at (45.711, 67.356) mm. The trace takes the demonstrated conservative route around existing copper toward the left edge.

DRC after refilling zones finds zero unconnected items and no added violation types compared with the demonstrated repair. Existing footprint/library, isolated-copper, board-edge and silkscreen findings remain unresolved. This revision is saved for further development and review, not released for fabrication. Reports are local artifacts under `build/hardware/v3-ground-audit/`; fabrication exports belong in `exports/` when requested.

## I2C and USART design verification

Checked on 2026-10-09 against the exported schematic netlist, PCB track/via connectivity and the TSSOP20 pin definitions in the [WCH CH32V003 datasheet, version 1.8](https://www.jc-net.co.jp/pdf/CH32V003DS0-EN.pdf). These are the default peripheral assignments, with no pin remapping required.

| Signal | MCU U1 pin | External connection | Other component |
| --- | --- | --- | --- |
| SDA | 11, PC1 | J1 pin 3 and J3 pin 3 | R12: 4.7 kΩ pull-up to VCC |
| SCL | 12, PC2 | J1 pin 4 and J3 pin 4 | R11: 4.7 kΩ pull-up to VCC |
| USART TX | 2, PD5 | J1 pin 5 (right connector) | None |
| USART RX | 3, PD6 | J3 pin 5 (left connector) | None |

All listed endpoints match between schematic and PCB, and each signal's pads are joined by actual tracks/vias. SDA and SCL are not swapped; TX and RX match the MCU's transmit/receive directions. Both connectors expose VCC on pins 1/2 and GND on pins 6/7. Pull-ups are to board VCC, not to a separately regulated interface voltage. Use compatible peripheral and UART-adapter logic levels, and connect adapter TX to board RX and adapter RX to board TX with a common ground. Each additional board adds its own I2C pull-ups in parallel.

ERC reported three library/link findings and no interface wiring errors. DRC with zones refilled reported zero unconnected items; schematic-parity checks reported 95 field/extra/duplicate-footprint findings, with no net-conflict finding. These broader findings remain unresolved. Local reports and the exported netlist are in `build/hardware/v3.1-interfaces/`.

Active display firmware preserves PC1/PC2 and PD5/PD6, but does not initialize I2C or USART. Design verification does not establish physical solder continuity, bus timing or successful communication. A physical USART test needs a compatible USB-UART adapter or TX/RX loopback; a physical I2C test needs a known slave and appropriate test firmware. Neither interface has been physically tested in this session.
