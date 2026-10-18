# Letki v4 — symmetric first-build candidate

Open `ledkiv4.kicad_pro` in KiCad. This is a separate low-cost candidate; v3/v3.1 and the working firmware are preserved. The source PCB is fully routed and passes ERC, DRC, connectivity, schematic parity and independent geometry checks. It remains an unqualified prototype candidate; no v4 first article has been fabricated.

The circuit uses the CH32V003F4P6, 64 orange XINGLIGHT XL-2012UOC LEDs (LCSC C965813), eight 1.2 kΩ ±1% row resistors, an SN74HCT244PWR row buffer, a Nexperia 74HCT238PW,118 decoder (C547472) and eight ElecSuper BSS138BK column sinks. Startup pulls define buffer inputs and decoder addresses. Open solder jumpers JP1/JP2 enable 2.2 kΩ I2C pull-ups at the chain head only (100 kHz target).

The MCU, buttons, SWIO voltage reference and I2C pull-ups use a local 3.3 V ME6206A33M3G regulator. U4 buffers UART TX/RX through an SN74LVC2G125DCUR, with 2.2 kΩ series resistors and 100 kΩ idle pulls. The LED drivers retain the 5 V VCC rail.

C8/C9 use active Samsung CL21B475KAB6PNE/C16194942, 4.7 µF/25 V X7R,
replacing the previous NRND part. The existing 0805 lands match the manufacturer's
reflow range. Typical bias curves support a useful capacitance margin; physical
effective-capacitance and regulator-stability qualification remains open.

J4/U5/R30/R31/R32/C10 are an optional `HEAD_ONLY` population: a USB-C socket, independent 5.1 kΩ CC pull-downs and a TPS2553 current switch. Populate/connect one USB head per chain. The 33 kΩ ±1% resistor gives a calculated 716–867 mA steady limiting range, before resistor temperature/ageing allowances. This is for a regulated 5 V, 1 A charger; no PD negotiation or USB data. SWIO pad 1 is a 3.3 V reference, not an input for powering the board through the programmer.

Four layers and the existing GPIO mapping are retained. The active-high decoder gates MOSFETs that pull the selected LED cathodes low, preserving the existing display polarity and address order. The PCB is 40.64 × 49.27 mm with uniform 5.08 mm LED pitch across horizontal joints. PCB-only edge pads avoid purchased inter-board connectors. Routing and manufacturer USB footprint checks are complete; supply, optics, mechanical integration and physical qualification remain.

V3 USART to the PC passed. Before ordering v4, finish two-board I2C using
[the prepared interface demos](../../docs/interface-demo.md). No v4 PCBs have
been ordered. Passing those tests establishes the baseline; the new v4 buffers,
3.3 V logic supply and complete chain still require physical qualification.

Project-local symbol/footprint libraries and their tables supply the inherited MCU and switch definitions without the old machine's library configuration. Other footprints use installed KiCad libraries. Reports and previews are under ignored `build/hardware/v4/`.

```sh
kicad-cli sch export netlist --format kicadxml -o build/hardware/v4/netlist.xml hw/ledkiv4/ledkiv4.kicad_sch
python3 scripts/check_v4_circuit.py
python3 scripts/check_v4_geometry.py
kicad-cli sch erc --severity-all --format json -o build/hardware/v4/erc.json hw/ledkiv4/ledkiv4.kicad_sch
```

The checker verifies driver pin mappings, 64 LEDs, separated supply rails, UART buffering/series paths, I2C endpoints, head-only pull-ups, USB CC/limiter paths and startup pulls. ERC currently reports zero findings. These checks do not establish PCB routing, brightness, thermal performance or production readiness.

`create_v4_candidate.py` and `v4_buffer_rows.py` record initial creation/revision and refuse existing work. `v4_sync_pcb.py` updates library footprints while preserving placement and refuses a routed board. These are development tools; inspect schematic cleanup for preserved connectivity.

Development helpers record earlier design steps; do not replay them against the routed source. `v4_route_matrix.py`, `v4_import_routing.py`, `v4_ground_fanout.py` and `v4_finish_routes.py` were used in ignored development copies. All copper is now in the source PCB. Official DRC reports no ignored rules and zero findings, including no open GND or supply connections. Custom libraries preserve the reviewed pad geometry and use 0.15 mm silkscreen lines. `ledkiv4.kicad_dru` records NPTH/PTH manufacturing clearances; no DRC exclusions are present.

`check_v4_geometry.py` also verifies every pad/hole stays inside the real outline and both contact arrays run downward at matching Y positions. This catches mirrored back-side contact geometry that DRC alone missed.

Generate a candidate quantity worksheet from the exported schematic with
`python3 scripts/v4_bom.py --tiles 5 --heads 1`. The ignored CSV at
`build/hardware/v4/candidate-bom.csv` separates tile parts from USB head parts,
excludes PCB-only contacts/jumpers, and checks every purchased part has an LCSC
code. Quantities are fitted parts, without supplier minimums or spares. This is
not a procurement release; stock, pricing and final design qualification remain.

See [requirements and completion gates](../../docs/v4-design.md) and [parts research](../../docs/v4-parts-research.md).
The stock-adjusted buying lists are in the generated handoff's
`procurement/BUY-5-BOARDS.csv` and `BUY-20-BOARDS.csv`. They reserve parts for
one more v3 board before crediting the user's shelf stock. All selected LCSC
listings had stock in the 2026-10-12 refresh, including the MCU; both prototype
quantities use existing exact-MPN MCUs. The recommended new parts cost $16.35
for five / $43.82 for twenty, plus an optional $0.38 pigtail minimum. Delivery,
tax, PCBs, assembly and mechanical parts are separate. Supplier stock/prices
are snapshots; recheck them at checkout. See the current reconciliation in
[parts research](../../docs/v4-parts-research.md).

Active FreeCAD assemblies are in `mechanics/`: one-tile and four-tile models.
`python3 scripts/v4_mechanics.py --tiles 1` or `--tiles 4` regenerates them under
`build/hardware/v4/mechanical/`. Dimensions are recorded metadata; regenerate
through the script when changing them. Printable exports also live in ignored
`mechanics/exports/`. The initial optical-only model is preserved in
`archive/hw/ledkiv4-optical-initial/`; its open under-grid gap is obsolete.

The opaque grid now seats on the PCB. A separate translucent face and front
bezel are held by top-edge hooks and two M2 screws through the new 2.2 mm NPTH
mounting holes. A rear carrier supports the boards independently of the seven
soldered wire bridges. For five tiles, print one four-tile carrier and one
one-tile extension, with two splice plates joining the sections behind the
display. The four-tile carrier is 162.56 × 57.27 mm and fits the A1 mini's
180 mm bed. Use ten M2 × 12 screws for the tiles and four M2 × 6 screws for the
carrier joint. Pilot-hole fit and retention need a print trial.

STLs are already oriented for printing. Print the grid/bezel in opaque material
and the 0.6 mm face separately in translucent white; no AMS is required. Closed
meshes, nominal PCB clearances and component-envelope interference checks pass.
The connector STEP files are conservative body envelopes, not detailed supplier
CAD. Real print warp, screws, solder, cable bends, light leakage and readability
remain unqualified. Test one tile assembly before printing five.

J2 accepts the optional vertical Molex 53047-0310/C122442, with the original
large SWIO pads routed in parallel. Pin 1 is REF, pin 2 SWIO, pin 3 GND. Default
assembly BOMs omit this hand-soldered header; the `-swio` variants include it.
C5221408 is an inexpensive probe pigtail candidate; check mating and pin
continuity before adapting it to the WCH-Link. Wire colours are not the pin map.
J2's 0.6 mm prototype holes and enlarged lands allow regular PCB fabrication
tolerance. Molex's 0.5 ±0.05 mm recommendation references a 0.8 mm board;
connector fit, pin protrusion and solder hole fill on the 1.6 mm board need
first-article qualification. No special press-fit process is assumed.

`python3 scripts/v4_cost.py` compares five and twenty boards, including MOQ and price breaks. Use `--spares 0.1` for prototype spare stock and `--refresh` for an explicit public-price refresh. The CSV flags stock limitations; no order is created.

Use `--inventory config/parts-stock.csv` to deduct the user's shelf stock.
Separate `*-stock.csv` outputs credit the exact MCU and LED MPNs; other v3 parts
are not automatically substituted. Counts/usage assumptions are editable in the
inventory CSV. See the stock reconciliation in the parts research; reserve parts
for the planned second v3 board; the current CSV already includes that reservation.


`python3 scripts/v4_package.py` creates the validated prototype package in
`hw/ledkiv4/exports/prototype/`: four-layer Gerbers and separate PTH/NPTH drills,
paste layers, schematic PDF, front/back assembly SVGs, head/follower BOMs and
CPLs, reports and a source/file hash manifest. Its checks fail on ERC, DRC,
open-net or schematic-parity findings. It does not program or order anything. The anonymous lead-free HASL PCB quote was $13.10 for five boards and $35.20 for twenty, before delivery/tax; see the parts research for assumptions and current stock limitations.
Verify supplier placement rotation/polarity in its preview before assembly.

Use `python3 scripts/v4_package.py --with-firmware` for the complete
`ledkiv4-prototype-handoff.zip`, including assembly files, a blank qualification
worksheet, order/bring-up instructions and freshly built text/UART/I2C images.
This builds without programming any device. The images remain unqualified on v4.

For WCH-LinkE programming, power the board from its intended USB/head supply
and connect only probe GND to J2 pad 3 and SWIO to J2 pad 2. Leave the probe's
3.3 V/5 V supply pins disconnected. J2 pad 1 (`REF`) is the board's 3.3 V rail
for measurement or a compatible voltage-sense input; the WCH-LinkE supply pin
is an output and must not feed it. Build the active v3 firmware separately,
identify the new chip, preserve its readback and obtain authorization before
an agent programs a v4 unit. The v3 standing authorization covers its recorded
UUID only.

Join a tile's front-view right contacts to the next tile's left contacts,
matching numbers 1–7: **5V, 5V, SDA, SCL, TX→RX, GND, GND**. Each side uses
seven single plated holes, evenly spaced between the eight LED rows. One shared
`EdgeWire_1x07_P5.08mm_D0.8mm` footprint replaces the earlier offset hybrid.

| Geometry | Dimension |
| --- | --- |
| Left / right contact X, viewed from the front | 1.27 / 39.37 mm |
| Seven contact Y coordinates | 7.62, 12.70, 17.78, 22.86, 27.94, 33.02, 38.10 mm |
| Contact pitch | 5.08 mm |
| Every staple span with abutting PCBs | **2.54 mm**, hole centre to hole centre |
| Plated drill / suggested tinned solid wire | 0.8 / 0.5 mm |
| Rear solder land | Oval, 2.04 × 1.60 mm |
| Front and inner lands | Round, 1.40 mm |

All seven staples use the same bend dimensions. A gap between boards increases
every span by that gap and interrupts the nominal LED pitch; qualify the actual
fabricated outlines before making a batch of wires. These are fully enclosed
ordinary PTHs, with no edge plating/castellated process or purchased inter-board
connector. Rear copper ends 0.25 mm from the outline. Ground contacts have solid
inner-plane attachment and need sufficient soldering heat. The 2 mm front VCC
bus and 1.2 mm rear feeds remain wide. The carrier supports the mechanical chain;
the wire joints carry electrical connections. Assemble unpowered.

The previous offset-hole revision is preserved in
[the dated archive](../../archive/hw/ledkiv4-offset-wire-20261012/README.md),
and the earlier flat-pad version in
[its own archive](../../archive/hw/ledkiv4-flat-pads-20261012/README.md).
Do not replay historical placement/routing helpers on this reviewed PCB.

For the first article, use a regulated supply with a current limit and inspect
before connecting a charger. Required qualification:

Record measurements and evidence in [v4-qualification.csv](../../docs/v4-qualification.csv).
Blank entries are untested; generated CAD reports do not fill physical results.

1. Check every GND contact, U1 ground and C1/C3 grounds for continuity; check
   supply rails for shorts. Inspect USB lands/slots, polarity and edge joints.
2. Measure 3.3 V at the MCU and regulator stability during startup, blank,
   alternating and all-on patterns. Confirm C8/C9 retain sufficient effective
   capacitance; the catalogue alone does not prove their bias performance.
3. Verify all 64 pixels, address order, blanking and 250 Hz frame refresh. Try
   held frames as well as scrolling, and measure LED and buffer supply currents.
4. Measure driver, MCU, regulator and head temperatures under worst intended
   patterns and at the operating supply extremes. Derive the chain current
   budget from these measurements, including HCT input current.
5. Test USB-C cable reversal, inrush, controlled output-short/current-limit
   recovery and charger/cable voltage drop. Use one USB head; every HCT supply
   must remain at least 4.5 V. No arbitrary charger-overvoltage immunity is claimed.
6. Test buffered UART with a 3.3 V-compatible USB adapter, then enumeration and
   I2C across two boards. Close JP1/JP2 only at the head. Measure I2C rise time
   and low levels; qualify the intended full chain at 100 kHz separately.
7. Print and fit the diffuser, check LED clearance and indoor legibility, and
   support joined boards on a backing structure so USB insertion and bending
   loads do not reach the solder bridges. Confirm alignment and joint resistance.
8. Preserve measured results, BOM lots, firmware version and inspection photos.
   Release production only after these results and the manufacturing process
   review pass. V4 is outside the existing v3 standing flash authorization.

ERC footprint/electrical checks are enabled. Standard single-global-label, four-way-junction style and unused-SPICE-model defaults are documented in the design brief and manifest. The exporter rejects other ignored checks.


Ten bare 1.0 mm rear probe pads improve bring-up access without adding any
purchased component or paste aperture. Small rear silk numbers identify TP1–10;
full references and signal names are in the assembly drawing.

| Point | Signal | Purpose |
| --- | --- | --- |
| TP1 | USB input, before current switch | Compare input to downstream 5 V at edge contacts |
| TP2 | Local 3.3 V | Check regulated logic supply |
| TP3 / TP4 | MCU TX / MCU RX | Separate MCU behavior from UART-buffer faults |
| TP5 / TP6 / TP7 | Decoder A0 / A1 / A2 | Inspect column address sequence |
| TP8 | Column 1 gate | Check decoder output to MOSFET |
| TP9 | Column 1 cathode | Check selected column low level |
| TP10 | GND | Local scope ground/pigtail pad |

Edge contacts already expose 5 V, GND, SDA, SCL and buffered chain UART;
J2 exposes SWIO/3.3 V/GND. Row PWM and buffered row outputs remain accessible
at existing row-resistor/logic pads; extra row pads would crowd this routing.
PD7 is shared with a row PWM output and is not a separate reset connection.

The optical grid seats on the PCB and uses **closed solder hoods** at all
fourteen holes: 0.8 mm cavity radius/depth, 0.4 mm opaque walls and roof. The
hoods enclose the solder while preserving separation between light cells.
Keep front wire protrusion ≤0.5 mm and solder within the modeled 0.75 mm
radius / 0.6 mm height. One/four-tile populated-STEP, printed-solid, staple and
carrier/probe clearances pass nominal CAD checks; actual printing, solder fill,
wire bends and light leakage still require a trial.

The symmetric reroute preserves all 64 LED positions and component pad nets.
Only J1/J3, TP8 and the two pull-up jumpers moved. Uniform mirrored rear legends
sit beside the contacts; the full horizontal LED body silkscreen is restored.
Ten new 0.6/0.3 mm ordinary through vias are tented on both faces.

`make pcb-doctor`, `make pcb-check` and `make pcb-preview` use the pinned
[KiCadRoutingTools workflow](../../docs/kicad-routing.md) in isolated copies.
The first supplementary review identified two UART cap-overlap joins, now
repaired to exact centre-line connections. Its extra copper/placement findings
remain visible and documented; official KiCad and native Letki geometry checks
remain the manufacturing checks. No automatic router output is promoted.

Visual review also removed the sharp SCL detour beside J1 contact 4. Its rear
connection to the existing via is now two simple segments, 1.57 mm rather than
7.39 mm. Pads, vias and all other routing remain unchanged; strict DRC, open-net,
schematic-parity and geometry checks passed. The handoff was regenerated.

All 30 fitted resistors and seven capacitors now have visible references on
`B.Silkscreen` for hand assembly: 1.0 mm text, 0.15 mm strokes. Five crowded
references are vertical; R12 has a short pointer to its part. References clear
exposed pads and existing silkscreen, and remain visible beside the component
bodies. Component values are in the BOM and rear assembly drawing. Use the
updated Gerber package when ordering; the earlier upload lacks these labels.


The purchase baseline now uses **HASL with lead (`HAL SnPb`)**, matching the
user-selected JLCONE option. Four layers, 1.6 mm thickness, 1 oz outer /
0.5 oz inner copper and tented ordinary vias are retained. Lead-free comparisons
above are historical. See [desktop quotes and joint shipment](../../docs/jlcone-shipping.md).
