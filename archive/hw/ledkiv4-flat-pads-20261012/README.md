# Archived v4: original flat bridge pads

Source snapshot before the first wire-hole/testpoint ECO. The complete KiCad
project, local libraries and one/four-tile FreeCAD source models are preserved.
This was a checked prototype candidate, not fabricated hardware.

# Letki v4 — design in progress

Open `ledkiv4.kicad_pro` in KiCad. This is a separate low-cost candidate; v3/v3.1 and the working firmware are preserved. The source PCB is fully routed and passes ERC, DRC, connectivity, schematic parity and independent geometry checks. It remains an unqualified prototype candidate; no v4 first article has been fabricated.

The circuit uses the CH32V003F4P6, 64 orange XINGLIGHT XL-2012UOC LEDs (LCSC C965813), eight 1.2 kΩ ±1% row resistors, an SN74HCT244PWR row buffer, a Nexperia 74HCT238PW,118 decoder (C547472) and eight ElecSuper BSS138BK column sinks. Startup pulls define buffer inputs and decoder addresses. Open solder jumpers JP1/JP2 enable 2.2 kΩ I2C pull-ups at the chain head only (100 kHz target).

The MCU, buttons, SWIO voltage reference and I2C pull-ups use a local 3.3 V ME6206A33M3G regulator. U4 buffers UART TX/RX through an SN74LVC2G125DCUR, with 2.2 kΩ series resistors and 100 kΩ idle pulls. The LED drivers retain the 5 V VCC rail.

C8/C9 use active Samsung CL21B475KAB6PNE/C16194942, 4.7 µF/25 V X7R,
replacing the previous NRND part. The existing 0805 lands match the manufacturer's
reflow range. Typical bias curves support a useful capacitance margin; physical
effective-capacitance and regulator-stability qualification remains open.

J4/U5/R30/R31/R32/C10 are an optional `HEAD_ONLY` population: a USB-C socket, independent 5.1 kΩ CC pull-downs and a TPS2553 current switch. Populate/connect one USB head per chain. The 33 kΩ ±1% resistor gives a calculated 716–867 mA steady limiting range, before resistor temperature/ageing allowances. This is for a regulated 5 V, 1 A charger; no PD negotiation or USB data. SWIO pad 1 is a 3.3 V reference, not an input for powering the board through the programmer.

Four layers and the existing GPIO mapping are retained. The active-high decoder gates MOSFETs that pull the selected LED cathodes low, preserving the existing display polarity and address order. The PCB is 40.64 × 49.27 mm with uniform 5.08 mm LED pitch across horizontal joints. PCB-only edge pads avoid purchased inter-board connectors. Routing and manufacturer USB footprint checks are complete; supply, optics, mechanical integration and physical qualification remain.

Before ordering v4, verify USART to the PC and two-board I2C on v3 using
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
Stock-available prototype quantities are in `build/hardware/v4/lcsc-available-5-boards.csv`,
with a twenty-board comparison. Optional probe pigtails have a separate import CSV
and need a mating sample. The MCU remains out of stock at LCSC; these are prototype
worksheets rather than a complete production procurement release.

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
for the planned second v3 board before final buying.


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

Join a tile's front-view right pads to the next tile's left pads, matching
numbers 1–7: 5V, 5V, SDA, SCL, TX→RX, GND, GND. These are ordinary rear copper
pads, with no castellated-hole or edge-plating fabrication option. Use short
tinned-wire bridges across the seam; qualify their resistance and reinforce the
chain with a backing structure. Solder bridges provide electrical connection,
while the backing structure carries insertion and bending loads. Assemble and
inspect the connections with power disconnected.

For the first article, use a regulated supply with a current limit and inspect
before connecting a charger. Required qualification:

Record measurements and evidence in [v4-qualification.csv](../../docs/v4-qualification.csv).
Blank entries are untested; generated CAD reports do not fill physical results.

1. Check every GND contact, U1 ground and C1/C3 grounds for continuity; check
   supply rails for shorts. Inspect USB lands/slots, polarity and edge joints.
2. Measure 3.3 V at the MCU and regulator stability during startup, blank,
   alternating and all-on patterns. Confirm C8/C9 retain sufficient effective
   capacitance; the catalogue alone does not prove their bias performance.
3. Verify all 64 pixels, address order, blanking and 125 Hz frame refresh. Try
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
