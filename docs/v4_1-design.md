# V4.1: TME prototype iteration

Status: prototype candidate with a pending USB-edge deviation. Official
ERC/DRC/open-net/parity and independent pin/net checks pass. The 2026-10-14
[datasheet audit](v4-pad-audit.md) corrected the USB-edge assertion; geometry
now reports a 0.575 mm inward edge offset and blocks package regeneration.
Physical qualification remains pending. The frozen package's earlier geometry
result is superseded; its source hashes and fabrication bytes remain unchanged.

Procurement update, 2026-10-13: the selected batch is five boards. TME order
35700057 has 20 lines awaiting delivery; the JLCPCB cart is saved and the user
has taken over checkout. [Current state](current-state.md) and
[actual purchase records](../config/purchase/README.md) supersede the initial
worksheet for acquisition. Native CAD and uploaded Gerber bytes are frozen in
`archive/hw/ledkiv4.1-purchase-20261013/`. Current documentation may be newer
than the original manufacturing package manifest.

Open `hw/ledkiv4.1/ledkiv4_1.kicad_pro`. The previous routed v4 remains in
`hw/ledkiv4/` and `archive/hw/ledkiv4-pre-tme-20261012/`, with a source hash
manifest. V3/v3.1 and active firmware are preserved. Creation/ECO helpers are
historical one-time transformations; edit the current routed sources for the
next iteration rather than replaying those helpers.

## Prototype policy and retained interfaces

The user relaxed minimum-cost optimization for these iterations: availability,
electrical margin, hand assembly and repeatability take priority. Costs remain
visible; later batches may buy exact parts or reviewed alternatives from LCSC.
New supporting parts use TME. Stocked CH32V003F4P6 and XL-2012UOC orange LEDs
are the explicit sourcing exceptions.

The PCB retains four layers, 40.64 × 49.27 mm, 1.6 mm thickness, the 8×8 LED
matrix at 5.08 mm pitch, all eight independent row PWM channels, SWIO on PD1,
USART on PD5/PD6, I2C on PC1/PC2 and two buttons. Seven ordinary 0.8 mm PTH
contacts per side sit midway between LED rows. Identical 0.5 mm wire staples
span 2.54 mm with adjacent boards touching. Two M2 mounting holes and the
removable printed optics/carrier provide mechanical support. The wire joints
carry electrical signals; the carrier bears handling and cable insertion loads.

The pin map still matches `firmware/v3/`. V4.1 uses active-high HCT238 outputs
to turn on separate MOSFET sinks; this retains the firmware's column address
ordering. HC138/LVC138 are not substitutes for this decoder. No firmware
change, programming or hardware validation follows merely from exporting CAD.

## Exact component changes

| Reference | V4.1 selection | Purpose and review |
| --- | --- | --- |
| U1 | CH32V003F4P6, user stock | Preserve the MCU, GPIO map and PWM timers |
| D1–D64 | XL-2012UOC, user stock | Preserve orange 0805 LED lands and polarity |
| U2 | Nexperia 74HCT238D,653 | Same active-high logic/pin map, larger SO16 for TME sourcing |
| U3 | TI SN74HCT244PWR | Retain eight row sources and 1.2 kΩ row resistors |
| Q1–Q8 | Diodes DMG2302UK-7 | SOT23 G1/S2/D3; lower specified on-resistance |
| U4 | Nexperia 74LVC2G34GW,125 | Two noninverting UART buffers, SOT363/SC70-6 |
| U6 | Microchip MIC5504-3.3YM5-TR | SOT23-5 regulator; EN tied to input, NC left open |
| C8/C9 | Samsung CL21B475KAFNNNE | 4.7 µF, 25 V, X7R, 0805; reviewed operating-bias model |
| SW1/SW2 | ALPS SKRPABE010 | SMD switch rated for the small button-loop current |
| J4 | GCT USB4105-GF-A | USB-C head-only power receptacle; new manufacturer lands |
| U5 | TI TPS2553DBVR | Retain head-only current limiting with 33 kΩ ±1% |
| J2 | Molex 530470310 | Optional rear vertical PicoBlade; bare SWIO pads remain |
| Purchased resistors | Royalohm S-series cut-tape symbols | Same electrical values and package sizes; exact TME order codes |

All five bypass capacitors share Yageo CC0603KRX7R9BB104. C10, J4, U5 and
R30–R32 are fitted only on the USB head. Close JP1/JP2 only on the head;
followers retain the I2C pull-up selection jumpers open.

For this placed order, R30/R31 use Yageo RC0603FR-075K1L (5.1 kΩ, 1%, 0603)
and U5 uses Diodes AP22653W6-7. The native CAD still names the original parts
above; use [the purchased assembly substitutions](../config/purchase/v4.1-assembly-substitutions.json)
at assembly. Pin mapping matches; existing U5 copper covers the leads but is
0.10 mm narrower than Diodes' suggested lands. See the pad audit for assembly
qualification limits. Keep R32 = 33 kΩ, 1%; AP22653's
manufacturer best-fit equations give about 758 mA typical and 654–871 mA
with a 3% resistor allowance. This estimate does not replace startup, short
circuit and thermal measurements. Use AP22653, not the AP22653A latch-off part.
[Diodes datasheet](https://www.diodes.com/datasheet/download/AP22652_AP22653_AP22652A_AP22653A.pdf).

Independent checks use manufacturer pin maps rather than trusting footprint
names. U4: 1=A1, 2=GND, 3=A2, 4=Y2, 5=VCC, 6=Y1.
U6: 1=VIN, 2=GND, 3=EN, 4=NC, 5=VOUT. The regulator's EN connection and the
old UART OE-pin removal were explicitly checked in the exported netlist.

## Electrical review and operating limits

The 1.2 kΩ row resistors and prior HCT244 current budget remain. At 5.25 V,
even a zero-forward-voltage row fault is bounded to 4.42 mA per row with
initial resistor tolerance. The engineering subtotal including a 3% resistor
allowance, eight 3 mA HCT input-current allowances and static current is about
60.25 mA; the 70 mA absolute package rating is not an operating target. Dynamic
current and brightness remain first-article measurements. DMG2302UK specifies
120 mΩ maximum at VGS=2.5 V and 25°C; temperature and switching behavior still
need physical verification. [Diodes datasheet](https://www.diodes.com/datasheet/download/DMG2302UK.pdf)

UART uses **220 Ω for both R26/R27**, reduced from 2.2 kΩ, and retains 100 kΩ
idle pulls. Nexperia guarantees VIH=2.0 V/VIL=0.8 V throughout VCC=2.7–3.6 V.
Conservative CH32 VOH=2.3 V/VOL=0.4 V therefore gives 0.30 V/0.40 V static
margins. The input transition constraint is still **Δt/ΔV≤10 ns/V**; the
datasheet's description of Schmitt action does not remove that requirement.
Use adjacent-PCB staple links and short leads to a fast push-pull 3.3 V UART
adapter. An engineering 10 pF link budget, two 220 Ω resistors and about 50 Ω
driver resistance gives RC≈5 ns; these capacitance/driver estimates require
measurement. Scope monotonic transitions at both U4 inputs, particularly
through 0.8–2.0 V, as well as testing 115200-baud exchanges. Arbitrary cable
lengths and adapters are outside this initial qualification envelope. The
resistors improve damping/current limiting; they do not establish complete
external-port fault protection.
[Nexperia datasheet](https://assets.nexperia.com/documents/data-sheet/74LVC2G34.pdf).

TI SN74LVC2G17DCKR is recorded as a same-footprint/pin-map alternative with
true Schmitt inputs and adequate threshold margins. Its TME listing has
zero stock and no established delivery date, so it is excluded from the
current purchase list. Substitution still needs updated metadata and checks.
[TI datasheet](https://www.ti.com/lit/ds/symlink/sn74lvc2g17.pdf),
[TI threshold clarification](https://e2e.ti.com/support/logic-group/logic/f/logic-forum/156772/sn74lvc2g17).

MIC5504 operates from 2.5–5.5 V and requires at least 1 µF effective output
capacitance; both selected caps use 4.7 µF nominal. Samsung's exact-part model
gives about 4.08 µF at 3.3 V and 3.26 µF at 5.25 V. Applying separate −10%
initial tolerance, −15% temperature and −10% ageing engineering allowances
gives about 2.81/2.25 µF. These are estimates from typical curves, not a
production guarantee. Verify regulator stability and effective capacitance on
the actual boards. [Microchip datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MIC5501-02-03-04-300mA-Single-Output-LDO-in-Small-Packages-DS20006006.pdf),
[Samsung exact-part model](https://product.samsungsem.com/mlcc/CL21B475KAFNNN.do).

ALPS specifies a minimum switching load of 10 µA at 1 V. The existing button
circuit is nominally 33 µA at 3.3 V. Its custom footprint uses four 1.05 ×
0.65 mm lands at x=±2.075 and y=±1.075 mm. Manufacturer contacts 1/2 form one
permanent row pair and 3/4 the other; these become duplicate logical pad
numbers 1 and 2. The 3D model is a conservative clearance envelope, with no
claim of exact supplier contact geometry.
[ALPS land/circuit drawing](https://tech.alpsalpine.com/cms.media/product_catalog_ta_02_skrp_en_2cd80f610b.pdf).

Use one regulated 5 V, 1 A charger and one USB head. TPS2553's calculated
steady limit is about 0.716–0.867 A for initial resistor tolerance, or
0.702–0.884 A with the provisional 3% resistor allowance. Neither this switch
nor the LDO establishes protection from arbitrary charger overvoltage.
Every HCT supply must stay at least 4.5 V, including cable and intertile drops.
Five boards are the prototype purchase baseline; a supported maximum chain
length requires measurement. Use 100 kHz I2C initially and one pull-up pair.

## Fabrication and mechanical handoff

KiCadRoutingTools was used for five recorded signal-routing trials; unsuccessful
results are retained in the HTML/CSV review. Terminal escapes, power/ground and
residual connections required manual routing. The reviewed manual In1 exception
adds 41 segments totaling 127.022 mm across eight signal nets and one VCC route;
it is larger than a few local jumpers and is recorded explicitly. Ground fill
retains four regions, VCC fill changes three to five, with all power/ground pads
connected under official checks. The seven deliberately wide VCC bus/feed
segments remain unchanged. These establish CAD continuity; signal return paths
and supply quality still need physical qualification. No check severity or
fabrication clearance was relaxed.

The supplementary router checker retains generic NPTH-clearance and native
padstack/redundant-copper advisories. Native KiCad uses the authored 0.2 mm NPTH
rule and real per-layer edge lands; those differences explain the advisories.
Its rounded-end-only joins were repaired explicitly. All reports remain visible;
the supplementary score is not represented as a clean production qualification.

`routing-review/viewer.html` is an offline interactive report produced with
pinned KiCad SVG Extras. It includes final F.Cu/B.Cu/In1.Cu/In2.Cu views,
previous v4 and available working trial outputs. Click a path/pad or choose a
net; the selection carries across layer changes, with zoom and mirror controls.
The real Firefox render/click check passed: nine SVG panels, five visible
MCU_UTX elements selected and 389 other rear elements faded. These are viewer
checks, not hardware qualification. CSV/HTML statistics include failed trials,
engine-reported time, measured command time when available, via counts and
trace lengths. Different inputs prevent a controlled ranking of the attempts.
[KiCad SVG Extras](https://github.com/adamws/kicad-svg-extras).

The 2026-10-14 [datasheet pad audit](v4-pad-audit.md) corrected the GCT USB4105
edge check: contact centres are y=−3.68 mm, 0.65 mm NPTH locators are at
x=±2.89/y=−2.605 mm, and the manufacturer's PCB edge is y=+3.675 mm relative
to the footprint origin. The earlier +3.1 mm value was the text-label anchor,
not the edge line. With the present connector placement, the recommended edge
is at board y=49.845 mm; the actual edge is y=49.27 mm, 0.575 mm inward.
Mounting slots remain within the PCB, but this deviation has no recorded
engineering acceptance or physical fit validation. The geometry checker now
reports it and exits nonzero; earlier claims of exact edge agreement are
superseded. CAD and frozen fabrication/purchase snapshots were not changed.
Four end GND lands are shortened
from 1.15 to 1.13 mm, preserving their centres, to meet the existing 0.2 mm
NPTH copper clearance. This small deliberate land adaptation is recorded in
the local footprint; the locator holes retain manufacturer diameter. The
standard GF-A stake length is 0.95 mm, shorter than the 1.6 mm PCB thickness;
hand solder the shell slots from the component side and inspect barrel fill.
[GCT manufacturer drawing](https://www.tme.eu/Document/1f050d2dc938bcf56fe5f4a6438948a1/USB4105%2B-%2BProduct%2BDrawing.pdf).

Order ordinary four-layer FR4, green mask, 1.6 mm, outer 1 oz/inner 0.5 oz,
leaded HASL, single-board delivery. The enclosed wire holes do not require
castellation or edge plating. All routing vias are ordinary through vias,
minimum 0.6/0.3 mm; retain the authored clearance, hole and silk rules.

The previous JLCPCB portal selected ink plugging for leaded HASL. Select
`Plugged` where required and provide `via-finish-map.png` plus the drill/net
CSV: keep exposed routing vias, solderable PTH holes, plated USB slots and
NPTH holes open; cover other vias according to Gerber mask openings. Near-pad
vias may be mask-covered without complete ink plugging. Paid production-file
confirmation is optional; the prepared quote leaves it off. Explicit mask,
drill and via-finish notes describe the ordinary process. If selected, file
confirmation reviews the fabricator's interpretation; it does not qualify the
circuit. Epoxy/copper capping is not specified.
[JLCPCB via process](https://jlcpcb.com/help/article/pcb-via-covering),
[JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities).

Rebuilt populated STEP and FreeCAD assemblies check nominal component/printed
part intersections and closed STLs for one-tile/four-tile carriers. Printed
fit, retention, cable clearance and optical quality still need the A1 mini
iteration. The solder hoods preserve opaque walls down to the PCB surface.

## Buying lists and first boards

`scripts/v4_1_bom.py` derives exact references/populations from the schematic
netlist, then applies TME minimums, quantity multiples and dated price tiers.
Default purchases include approximately 20% spares, including a second USB
limiter and receptacle. `--spares 0` gives the minimum-cash comparison. The
two-column `TME-QUICKBUY-5-boards.csv` is for TME import; the larger `TME-BUY`
file retains MPNs, references, prices, source age and availability warnings.

The selected U4 has a dated TME snapshot with 931 pieces and MOQ/multiple 1.
All prices/stock snapshots require checkout refresh; no immediate shipping
promise follows from cached catalogue evidence. The user permits special
orders when delivery can be established. Check the exact cut-tape resistor
symbols: identical MPNs under full-reel symbols may have a 5,000-piece minimum.
[TME selected U4 listing](https://www.tme.eu/no/en/details/74lvc2g34gw.125/buffers-transceivers-drivers/nexperia/74lvc2g34gw-125/).

The updated ledger reserves parts for four remaining v3 boards. Conservative
available stock is 43 MCUs and 680 LEDs before v4.1 assembly. Five v4.1 boards
use 5/320 respectively; twenty use 20/1280 and need at least 600 extra LEDs.
The optional 1,000-piece XL-2012UOC restock fills two already demonstrated
500-piece magazines, tightly. LCSC's 2026-10-12 catalogue tier is $0.0068 each
from 500, so 600/1,000 are $4.08/$6.80 before shipping and tax. This is separate
from the TME supporting-parts list. [LCSC LED listing](https://www.lcsc.com/product-detail/C965813.html).

V3 USART passed; the two-board v3 I2C baseline remains pending. For the first
v4.1, check unpowered continuity and polarity, then the 5 V/3.3 V rails before
connecting the probe. SWIO pin 1 is a reference, not a supply input: use SWIO
and GND with the board's own USB power, leaving programmer power outputs
disconnected. Check and record fresh-MCU PD7/NRST option configuration before
the complete row test; option-byte changes require separate authorization.
Run walking pixels, brightness/PWM, UART and two-board I2C before assembling
the entire batch. Record results in `docs/v4_1-qualification.csv`.

## Rebuilding checks and exports

```sh
kicad-cli sch export netlist --format kicadxml \
  -o build/hardware/v4_1/netlist.xml hw/ledkiv4.1/ledkiv4_1.kicad_sch
python scripts/check_v4_circuit.py --revision v4.1
python scripts/check_v4_geometry.py hw/ledkiv4.1/ledkiv4_1.kicad_pcb --revision v4.1
python scripts/setup_kicad_svg.py
python scripts/v4_1_package.py
```

The exporter refuses ERC/DRC/open-net/parity failures and unexplained disabled
checks, checks stackup/finish, generates the TME lists and mechanical exports,
and verifies source hashes stayed fixed. `ledkiv4_1-gerbers.zip` is for the PCB
upload; `ledkiv4_1-handoff.zip` includes drawings, reports and procurement.
Use `scripts/kicad_routing.py ... --revision v4.1` on isolated copies for later
routing changes. Review all instrument reports before source promotion.
