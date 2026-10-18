# V4 design brief and release evidence

Status: routed prototype candidate, not a production release. No v4 PCB has been fabricated or qualified. Existing v3/v3.1 sources and firmware remain intact.

The candidate is in `hw/ledkiv4/`. Its four-layer source PCB is now fully routed. KiCad reports zero ERC findings, zero DRC violations, zero open connections and zero schematic-parity findings. Independent circuit and geometry checks cover the LED matrix, ground endpoints, interface pins and manufacturer USB placement. These establish CAD consistency; power, brightness, mechanical and physical first-article qualification remain.

## Requirements from the user

- Create production-ready v4 hardware.
- Cost reduction is a primary goal: preserve the rationale for an extremely cheap CH32V003, cheap supporting chips and solderable board-edge connections without purchased connectors.
- Four layers are intentional because JLCPCB prices this board size favourably. Evaluate total cost before changing the layer count.
- Broader layout and connector changes are permitted, but must retain the low-cost intent. Edge-contact alternatives may be considered.
- Power from an inexpensive USB charger. Assess a conventional 5 V supply and a conservative current budget; do not depend on USB PD higher-voltage negotiation.
- Use inexpensive orange LEDs for the v4 design and current-budget assessments. The initial green candidate has been superseded; compare orange LED forward voltage, brightness and cost using the exact chosen part's datasheet.
- Retain the useful distinction between directional UART for physical-order enumeration and the shared I2C bus for addressed communication. UART bootloader work remains a separate development task.

An eight-board chain is a provisional engineering target, not a user-confirmed limit. Brightness, exact charger rating, supplier/MPNs, operating environment and production quantity remain to be established. Price references must identify supplier, quantity, currency and date; distributor list prices alone cannot justify an upgrade in this project.

## Evidence collected from v3.1

The exported schematic netlist shows each 74HC138 output directly connected to the cathodes of eight LEDs. Row resistors R1–R8 have the unspecified value `R`; LEDs have no specified manufacturer part number. The existing design therefore does not establish a reproducible LED-current limit or a verified combined-column current rating. This is not evidence that the current physical board exceeds ratings, because its installed resistor values and LED currents have not been measured.

The original ground disconnection between C1 and C3 has been repaired in v3.1. Its demonstrated front trace is a recovery route, not an optimized v4 ground layout. Existing ERC/DRC/library/edge issues remain in v3.1. Local baseline netlist: `build/hardware/v4-audit/v3.1-netlist.xml`.

The CH32V003 datasheet specifies GPIO output characteristics at 8 mA per pin, with absolute VDD/VSS current limits of 100/80 mA. Those absolute maxima are not design targets. A low-current design can retain GPIO row sources if the per-pin and aggregate budget is demonstrated with margin. The TI HC138 is a logic decoder with approximately 4 mA output drive, so a full lit column requires a separate current budget or buffer.

Sources: [WCH datasheet, manufacturer-authored mirror](https://www.jc-net.co.jp/pdf/CH32V003DS0-EN.pdf), [TI SN74HC138](https://www.ti.com/product/SN74HC138).

## Current low-cost candidate and electrical review

The candidate uses an ordinary active-high HCT decoder and eight inexpensive MOSFET column sinks, retaining the existing address ordering. It also uses one HCT244 row-source buffer. Direct GPIO row drive was considered, but the WCH VOH table does not provide sufficiently clear assurance for the desired LED voltage/brightness. HCT inputs provide a documented 2 V high threshold, and the buffer carries the LED current with stronger guaranteed output voltage. This is a costed ordinary-logic alternative to a specialised matrix driver; selected parts still need complete sourcing, manufacturing and physical qualification.

The selected orange LEDs use **1.2 kΩ ±1%** row resistors. At 5.25 V, a zero-LED-voltage fault bounds one row to 4.42 mA and all eight to 35.35 mA using initial tolerance. With a provisional 3% total resistance allowance (initial tolerance, temperature and drift), the eight-row bound is 36.09 mA. The chosen LED specifies 1.8–2.4 V at 20 mA/25 °C; an ideal 5 V/1.2 kΩ estimate is 2.17–2.67 mA selected (0.27–0.33 mA average at 1:8). Driver/sink drops reduce that estimate; the 20 mA forward-voltage specification is not a guarantee at our lower current. Brightness requires qualification.

A third focused review found that TI HCT244's additional supply current cannot be omitted: its revised datasheet allows 3 mA per input at the specified 0.5/2.4 V test levels. The former 1 kΩ design gave only about 3.4 mA below the buffer's 70 mA absolute VCC-current rating after adding eight such input allowances and 160 µA quiescent current. The 1.2 kΩ resistors improve the engineering subtotal to about 60.25 mA with the 3% resistance allowance, before dynamic effects. This costs no extra parts but predicts roughly 17% less LED current. Exact GPIO VOH/input current and transitions still need qualification: the 3 mA test point does not establish a bound at every possible MCU output voltage.

Nexperia 74HCT244PW,118 was also researched: its lower specified input-current increment is attractive, but tested at VCC−2.1 V. Its quoted 50-piece price was $0.2911 versus the TI candidate's $0.2754, and it retains a GPIO-voltage qualification caveat. The least-cost current implementation retains TI and increases row resistance. Do not substitute a vendor solely by its generic 74HCT244 name. [TI buffer datasheet](https://www.ti.com/lit/ds/symlink/sn74hct244.pdf), [Nexperia buffer datasheet](https://assets.nexperia.com/documents/data-sheet/74HC_HCT244.pdf), [Nexperia quote](https://www.lcsc.com/product-detail/C131088.html).

Confirm the MCU's own current, other loads, temperature derating, optical output and full-chain consumption. No first article has been measured.

Evaluate charger input current limiting, inrush, reverse-current prevention and connector robustness against their actual cost. A purchased USB power connector may be confined to a chain-head assembly rather than fitted to every tile. Compare a head/tile population option with identical fully populated boards; account for assembly setup charges and operational simplicity.

The initial focused Astra review identified the GPIO-voltage uncertainty, floating decoder inputs, accumulated I2C pull-ups and remaining UART/unpowered-chain concerns. The candidate now has startup pulls and head-only pull-up jumpers. For MOSFET assessment, use the selected ElecSuper part's conservative 4.5 Ω maximum at 2.5 V gate drive/25 °C rather than claiming its 4.5 V resistance throughout the supply envelope. The fault-current bound gives about 0.159 V sink drop and 5.6 mW dissipation with initial resistor tolerance at that characterization point. Temperature, optical output, chain capacitance and actual supply consumption remain qualification items.

Sources: [TI HCT244](https://www.ti.com/lit/ds/symlink/sn74hct244.pdf), [TI HCT238 family](https://www.ti.com/lit/ds/symlink/cd74hc238.pdf), [ElecSuper BSS138BK](https://datasheet.lcsc.com/datasheet/pdf/9d90026c4a547e4de8cc26451c8db995.pdf?productCode=C5224267). The user-selected orange LED and partial pricing evidence are in [parts research](v4-parts-research.md).

A second focused read-only review checked the regulator, dual UART buffer and current-switch candidates before schematic implementation.

The head I2C pull-ups are now 2.2 kΩ. With a 3% resistor allowance and 400 pF load, the first-order rise-time estimate is 768 ns, below the 1 µs Standard-mode limit. At 3.366 V and VOL=0.4 V, the low-level pull current is about 1.39 mA per line. Full-chain capacitance, low level and waveforms still need measurements; 400 kHz is not a qualified chain rate. [NXP I2C specification](https://www.nxp.com/docs/en/user-guide/UM10204.pdf).

## Supply and interface implementation

The 5 V VCC rail supplies the HCT driver pair and the input of a ME6206A33M3G regulator. Its SOT-23-3 M3 pin map is 1 GND, 2 VOUT, 3 VIN. Its 3.3 V output supplies the MCU, buttons, SWIO reference, UART buffer and selectable I2C pulls. C3/C7 provide local 100 nF bypassing; C8/C9 are candidate Samsung CL21B475KAB6PNE/C16194942, 4.7 µF/25 V X7R capacitors, which must retain at least 1 µF effective capacitance after bias/tolerance/temperature. The redundant C4 bulk capacitor was removed; C9 supplies regulator output capacitance alongside the MCU/UART local bypass capacitors. Never feed the regulator output from an unpowered programmer supply: no reverse-current guarantee was found. [MICRONE manufacturer-authored V20 datasheet](https://img.ichunt.com/doc/pdf/cms/201808/29/f71d85f01883a662ed366ee77b8e7c47.pdf).

U4 SN74LVC2G125DCUR uses 3.3 V. Pin 2 receives MCU TX and pin 6 drives the right UART contact through R26; the left UART contact enters pin 5 through R27 and pin 3 drives MCU RX. Pins 1/7 OE are grounded, pin 4 is GND and pin 8 is VCC. Both line series resistors are 2.2 kΩ, with 100 kΩ idle pulls. The chip has 5.5 V tolerant inputs and Ioff support. Its near-rail output at light load gives the MCU a defined receive-high level. Use an adapter accepting 3.3 V TX logic; tolerating a 5 V input does not make the whole chain hot-pluggable. I2C still requires a commonly powered chain. [TI UART buffer datasheet](https://www.ti.com/lit/ds/symlink/sn74lvc2g125.pdf).

The optional USB head uses J4 HRO TYPE-C-31-M-12, individual 5.1 kΩ ±1% CC resistors, input bypass C10 and TPS2553DBVR. U5 pin map: 1 IN, 2 GND, 3 EN (active high, tied to IN), 4 FAULT (unused open-drain), 5 ILIM, 6 OUT. R32 33 kΩ ±1% sets a 715.7–867.1 mA steady current-limit envelope using TI equations and resistor initial tolerance. The equations already include IC process/temperature, but final resistor TCR/ageing and transient overshoot need separate allowance. The switch provides soft start, overcurrent/thermal limiting and reverse input-output voltage protection. It does not establish immunity to arbitrary overvoltage from a faulty charger. One regulated 5 V, 1 A charger and one populated USB head are the intended configuration. [TI current-switch datasheet](https://www.ti.com/lit/ds/symlink/tps2553.pdf).

The former 500 mA ceiling was an engineering assumption rather than a user requirement. The head now targets an inexpensive regulated 5 V, 1 A charger. Its steady maximum is still below 1 A with a 3% resistor allowance; transient overshoot and head current are separate.

Eight tiles remain provisional. Their worst normal load must be below the **minimum** current-limit threshold; derive the final budget from component characteristics and first-article measurements. HCT parts require at least 4.5 V locally, so limiter resistance, USB cable drop, edge joints and plane resistance must fit the input-to-last-tile voltage budget. A 4.75 V charger output does not establish 4.75 V at every tile.

PCB candidate dimensions are 40.64 × 49.27 mm, preserving 5.08 mm LED pitch across horizontal seams and space for a USB socket below the matrix. Regular signal routing uses 0.2 mm clearance/track width, with 0.7/0.3 mm manual through vias and 0.6/0.3 mm router vias. A 2.0 mm front-top 5 V bus and 1.2 mm rear edge-feed legs carry chain current separately from ordinary signal tracks. Ground remains on In1; In2 carries matrix columns, a 5 V pour and some additional signal routing. Pour connectivity must be checked after routing. U4 has a local 0.15 mm clearance for its 0.175 mm pad gaps; other nets retain the default 0.2 mm clearance. [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities) specify 0.15 mm minimum different-net SMD pad spacing. Board-edge solder-pad setback is 0.25 mm nominal and needs tolerance/process review before release. The local USB footprint now follows the manufacturer’s 2020-12-08 lands: 1.14 mm land length, centres 1.07 mm behind the locator holes, VBUS/GND centres at ±2.4/±3.2 mm. The board edge is 5.79 mm ahead of the locators, allowing 0.46 mm socket protrusion. Locator holes are 0.60 mm; front retention slots retain the standard 1.20 mm length, meeting the fabricator’s two-times-width slot rule. [HRO drawing](https://datasheet.lcsc.com/datasheet/pdf/9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948).

Bypass placement was revised after routing exposed long supply loops: C3 now sits beside the MCU VDD pin, C6 beside row-buffer VCC, C1 beside decoder VCC and C7 near UART-buffer VCC. C8/C9 are beside regulator input/output; placement and final trace-loop review remain distinct from a zero DRC count. All five 100 nF bypass capacitors use the same Yageo 0603 candidate to reduce BOM variety.

## Routing checks and tool limits

All five inherited disabled PCB checks (courtyards, footprint filters/type, via endpoints and tuning geometry) are enabled as warnings, and the DRC report confirms no ignored checks. DRC exclusions are empty. PCB-only pads now have courtyards and no stencil apertures or pick-and-place entries; the switch courtyard includes its body and pads. A separate geometry checker validates the actual closed outline, every pad/hole, contact orientation, interface pin positions and LED pitch/cathode orientation. It caught a back-side contact-array mirroring error that ordinary edge-clearance DRC did not report.

The reviewed routing was promoted to the source PCB after official DRC, full schematic parity and geometry checks passed. The ground fill has four regions, joined electrically by deliberate traces/vias; all ground and supply connections pass DRC. Unused routing branches and unanchored pour islands were removed. The 5 V pass-through retains its 2.0 mm bus and 1.2 mm feeds; the USB input routes are 0.5 mm. Local footprint copies use 0.15 mm silkscreen lines, with functional labels at least 1.0 mm high and 0.15 mm from pads. The project enforces those fabricator limits. NPTH-to-copper clearance is 0.2 mm, scoped by pad type; PTH-to-copper is 0.28 mm. These are explicit rules, not exclusions.

Local Freerouting 2.2.2 and Temurin Java 25 artifacts were verified with their published SHA256 values. Routing development copies and an unrouted pre-promotion backup remain under ignored `build/hardware/v4/`. Creation/placement helpers refuse routed source boards; do not replay the old routing seed against the current source.

The selected decoder is now Nexperia 74HCT238PW,118 (C547472), replacing TI CD74HCT238PWR after checking the same pin map, active-high outputs, 2 V high threshold and TSSOP16 dimensions. Its current small-quantity price is lower. Three address-input current increments are 3 × 343 µA at the specified VCC−2.1 V test point over −40…125 °C, plus 160 µA static supply current; exact GPIO levels remain part of qualification. [Nexperia datasheet](https://assets.nexperia.com/documents/data-sheet/74HC_HCT238.pdf), [LCSC quote](https://www.lcsc.com/product-detail/C547472.html).

The user selected five boards as the normal prototype purchase, with a comparison against twenty. `scripts/v4_cost.py` computes minimum-cost purchases over supplier MOQ, multiples and price breaks, and flags insufficient stock. Current reference component subtotals are $15.84 for five boards and $45.87 for twenty, each with one USB head, before spares, PCB, stencil, assembly, delivery or tax. The unavailable bypass capacitors and head resistor were replaced with C14663 and C4216; C5187096 still shows zero stock, so these estimates are not an available cart. The live parameter quote gave lead-free HASL PCB totals of $13.10 for five and $35.20 for twenty; combined reference parts/PCB totals are $28.94/$81.07 before spares, delivery, tax, stencil or assembly. No files were uploaded. The generated prototype manufacturing package is in `hw/ledkiv4/exports/prototype/`, with four-layer Gerbers, separate drills, paste, BOM/CPL variants, drawings and a validation/hash manifest. Factory setup and parts-loader fees must also be considered, particularly for double-sided assembly. [JLCPCB assembly charges](https://jlcpcb.com/help/article/pcb-assembly-price).

## Mechanical integration and programming access

Two 2.2 mm NPTH mounting holes at (2.54, 46.75) and (38.10, 46.75) mm reserve
M2 fastener positions without changing board dimensions or LED pitch. Their
4.9 mm fastener envelopes and all-layer copper keepouts are checked. J2 combines
the original bare pads with a vertical Molex 53047-0310/C122442: pin 1 REF
(3.3 V), pin 2 PD1/SWIO, pin 3 GND. The connector is optional and can be
hand-soldered after normal SMT assembly. Bare pads remain usable.

The local footprint uses 0.6 mm prototype PTH holes with 1.0 × 1.4 mm lands.
Molex recommends 0.5 ±0.05 mm holes on its t=0.8 drawing; JLCPCB's regular PTH
tolerance is +0.13/−0.08 mm. The larger prototype hole avoids the smaller end of
that ordinary process tolerance. It requires actual fit, pin protrusion and
solder-hole-fill qualification on the 1.6 mm PCB.
[Molex drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/530/53047/530470310_sd.pdf),
[JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities/).

Active assemblies are in `hw/ledkiv4/mechanics/`; `scripts/v4_mechanics.py`
generates the grid, translucent face, front bezel with top hooks, rear carrier
and carrier splice plates. Cell walls reach the PCB surface. Two M2 × 12 screws
clamp each tile assembly to the carrier; two splice plates and four M2 × 6 screws
join carrier sections. One four-tile section plus one one-tile extension covers
the first five prototypes. The four-tile carrier is 162.56 × 57.27 mm, within
the A1 mini bed envelope. Source dimensions are recorded metadata rather than
live parametric links.

Closed printable meshes, nominal assembly clearances and populated STEP
interference checks pass. Connector STEP geometry is a conservative body
envelope, with no supplier contact/solder or cable-bend model. Printing, screw
retention, cable overmould clearance, light leakage and viewing quality still
need physical evidence. The initial unmounted optical model is archived.
Do not replay the mechanical ECO helper on the current routed board.

The user will verify USART to the PC and two-board I2C on v3 before ordering
v4. Those results establish the baseline, while v4's new drivers/buffers/supply
and full chain require separate first-article tests.

## Production completion gates

- Approved operating envelope: supply range, maximum chain length, current budget, brightness, mechanical assembly and environmental limits.
- Reproducible KiCad schematic/PCB, local custom libraries where needed, and fully specified BOM with purchasable MPNs and assembly variants.
- Prepare an LCSC purchase list after design review, with exact part codes, quantities and optional/head-only parts clearly identified. Do not label a partial pricing worksheet as a ready-to-buy list.
- Datasheet-backed electrical review of LED current paths, GPIO limits, logic thresholds, power faults, pull-ups, interfaces and startup states.
- Reviewed ERC/DRC with no unexplained violations or exclusions. Ground continuity, footprint pin mapping, edge contact process and assembly orientation checked independently of rule-pass counts.
- Costed fabrication and assembly process with dimensions/layer stack verified against the selected fabricator; no orders without explicit authorization.
- Reviewed manufacturing package: Gerbers, drill files, BOM, placement, assembly/polarity drawings, programming instructions and inspection/test procedure.
- Physical first-article qualification: current/temperature, LED patterns, USB supply behaviour, full-chain UART/I2C, mechanical joints and manufacturing repeatability. A successful export or software test cannot substitute for these measurements.

Do not label the design production ready until the evidence for these gates exists. Continue work toward the complete objective; do not narrow the objective to a rule-clean layout or an untested fabrication package.


A sourcing review replaced the five bypass capacitors with Yageo
CC0603KRX7R9BB104/C14663, retaining 100 nF, 50 V, X7R, ±10% and 0603.
The manufacturer's exact-part sheet confirms its 1.6 × 0.8 mm body. R32 is now
UNI-ROYAL 0603WAF3302T5E/C4216, 33 kΩ ±1%, 100 ppm/°C, matching the existing
0603 land pattern. TI's equations give 715.7–867.1 mA with initial tolerance;
the 3% total resistor allowance raises the steady maximum to 883.9 mA. The
slight increase remains below 1 A. No copper, pad geometry or schematic
connections changed, and the complete prototype package was revalidated.
[Yageo part sheet](https://www.yageogroup.com/download/specsheet/CC0603KRX7R9BB104),
[UNI-ROYAL datasheet](https://datasheet.lcsc.com/datasheet/pdf/0a975aaa49b7c97f38a963127be4a823.pdf?productCode=C4216).


A final report audit found the source project still had five ignored DRC rules;
these were enabled in the actual source settings. Two VCC endpoints were moved
onto their connected via centre. ERC footprint-filter checking was also enabled;
local footprint names now retain their type prefix, and project-local edge/SWIO
pad symbols explicitly name the intended footprints. No pads or pin connections
changed. DRC now has no ignored rules, findings, open connections or parity
findings; ERC has no findings under its declared settings.

Three standard ERC defaults remain explicitly documented: a single global label
is legal in this single-sheet design, intentional four-way wire junctions are
allowed, and no SPICE-model validation is claimed. These are style/simulation
choices; footprint and electrical checks are enabled. The package generator
rejects any disabled PCB check or any other unexplained disabled ERC check, and
records these explanations in its manifest. It also verifies a complete handoff
archive with assembly files, firmware images and a blank physical-test worksheet.

## Bounded Astra final review — 2026-10-11

A read-only Astra review found no additional definite connectivity defect and
confirmed the recorded source/package hashes, interface pin maps, ordinary PTH
vias and valid FreeCAD solids. It identified a manufacturing metadata mismatch:
the source inner copper was 35 µm and the finish was `None`, while the quote and
handoff specified 0.5 oz inner copper and lead-free HASL. The source now records
17.5 µm inner / 35 µm outer copper and `HAL lead-free`; the nominal core was
adjusted to preserve the 1.6 mm total. Dielectric dimensions and properties are
nominal, not a controlled-impedance specification. Confirm the fabricator's
ordinary stack before ordering. The exporter checks the generated Gerber job
against these requirements and excludes FreeCAD backup files from the handoff.

Regeneration exposed a checker defect: a temporary KiCad bounding box's vector
references were used after the box was released. The checker now retains the box
and measures circular-pad clearance from the circle, avoiding false overlap from
its enclosing square. The source passes; an enlarged SWIO pad deliberately
crossing H1's fastener envelope in a temporary copy is correctly rejected.

Samsung marks the original C8/C9 CL21B475KOFNNNE family **NRND**, with no specified
replacement. It has been replaced by the active CL21B475KAB6PNE described below.
Effective capacitance under bias/temperature remains a separate open physical
qualification item.
[Samsung family status](https://product.samsungsem.com/mlcc/CL21B475KOFNNN.do).

Production sign-off remains open: physical power/temperature/brightness and
full-chain interface measurements, J2 insertion/protrusion/solder-fill evidence,
printed fit/retention/cable clearance, and exact MCU sourcing/assembly process.
The 60.25 mA HCT244 allowance is not a measured operating guarantee; establish
chain length and charger/cable limits from the qualification results. Follow the
user's v3 USART/I2C pre-order gate before arranging v4 fabrication.

## C8/C9 lifecycle issue resolved — 2026-10-11

The schematic and PCB now specify Samsung CL21B475KAB6PNE/C16194942,
4.7 µF ±10%, 25 V, X7R, 0805. Samsung lists it as **Mass Production**.
The existing lands match its manufacturer reflow range for the ±0.25 mm body:
0.9 mm gap, 1.0 mm land length and 1.45 mm width. Body height is at most 1.5 mm;
the rear carrier allows 5.8 mm. No routing or land changes are needed.
[Samsung lifecycle/specifications](https://product.samsungsem.com/mlcc/CL21B475KAB6PN.do),
[manufacturer reference sheet](https://datasheet.lcsc.com/datasheet/pdf/3bed8a67135935e31df2d84dc20d8daa.pdf?productCode=C16194942).

Samsung's embedded typical DC-bias curve at 25 °C gives about 3.70% capacitance
loss at 3.366 V and 10.71% at 5.25 V: approximately 4.53 µF and 4.20 µF.
Applying the initial −10% tolerance and X7R −15% temperature allowance to the
5.25 V estimate gives about 3.21 µF. This is an engineering margin estimate,
not a guaranteed combined-bias/temperature/ageing limit. Preserve the physical
effective-capacitance and regulator-stability gate; vendor typical curves cannot
fill measured results. The original downloaded page and numerical curves are
retained under ignored `build/hardware/v4/supplier/`.

The verified LCSC snapshot has 9,100 pieces, a five-piece minimum/multiple and
$0.1089 per piece below 50. Ten capacitors cost $1.089 for five tiles, versus
$0.367 for the former NRND part: an additional $0.722 per batch (about $0.14 per
tile). The active TDK C2012X7R1C475K125AB listing is out of stock; the researched
Murata GRM21BR71C475KA73L listing is dearer at $0.1232, and its lifecycle has not
been established. The selected candidate resolves the known lifecycle problem
with no extra supplier or PCB change.
[LCSC selected part](https://www.lcsc.com/product-detail/C16194942.html).


## Wire-hole and probe access iteration (2026-10-12)

The original rear bridge lands remain usable. Fourteen inward PTH wire holes
use 0.8 mm drills and 1.3 mm lands for 0.5 mm tinned solid copper staples.
Their matching Y coordinates and individual left/right inward positions are
recorded in `config/v4-mechanics.json`; the staples do not assume one fixed
width. Existing rail feeds remain wide. Ordinary through-hole fabrication is
intended, with no castellated/edge-plating or filled-via option.

Ten numbered rear copper probe pads expose USB input, 3.3 V, MCU-side UART,
all three decoder addresses, the first MOSFET gate/cathode and a local ground.
They are explicitly labelled `PCB_ONLY` in the schematic and excluded from
BOM, placement and paste. The circuit/geometry checkers bind their net maps,
positions and legends. Existing edge contacts and SWIO pads cover the external
interfaces; existing resistor/logic pads give row-PWM access.

Grid relief pockets clear the modeled trimmed pins and front solder envelope
without connecting neighboring cells. The carrier clears staple bridges and
probe-tip access. Physical print/solder/hole-fit testing remains pending.
Old mechanical sources were preserved in the ignored ECO backup before
regeneration. BOM part quantities and board dimensions/LED pitch are unchanged.
