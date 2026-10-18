# V4 parts research — incomplete costing

Historical research checked 2026-10-11; the current 2026-10-12 buying snapshot is below. This partial supplier worksheet is not the final purchase list or released BOM. Prices are USD at the listed quantity tiers, excluding shipping, tax, spares, fabrication and assembly. Refresh price/stock before final procurement.

| Candidate | Role | LCSC | Listed examples | Per tile |
| --- | --- | --- | --- | --- |
| XINGLIGHT XL-2012UOC | Orange 0805 LED | C965813 | 50+: $0.0088; 500+: $0.0068; 6000+: $0.0050 | 64 |
| ElecSuper BSS138BK | Column sink | C5224267 | 100+: $0.0147; 300+: $0.0120 | 8 |
| TI SN74HCT244PWR | Row buffer | C6778 | 50+: $0.2754; 150+: $0.2422; 500+: $0.2008 | 1 |
| Nexperia 74HCT238PW,118 | Decoder | C547472 | 5+: $0.3463; 50+: $0.2704; 500+: $0.1974 | 1 |
| TI SN74LVC2G125DCUR | UART buffer | C21404 | 5+: $0.2091; 50+: $0.1639; 500+: $0.1203 | 1 |
| MICRONE ME6206A33M3G | 3.3 V regulator | C35259 | 10+: $0.0608; 100+: $0.0497 (recheck before purchase) | 1 |
| HRO TYPE-C-31-M-12 | USB-C socket, head only | C165948 | 5+: $0.1879 list / $0.1729 displayed discount | 0 or 1 |
| TI TPS2553DBVR | Head current limiter | C55266 | 1+: $0.5434; 10+: $0.4499; 100+: $0.3284 | 0 or 1 |
| WCH CH32V003F4P6 | MCU | C5187096 | 5+: $0.2904; 50+: $0.2260; 500+: $0.1639 | 1 |

Sources: [LED](https://www.lcsc.com/product-detail/C965813.html), [MOSFET](https://www.lcsc.com/product-detail/C5224267.html), [buffer](https://www.lcsc.com/product-detail/C6778.html), [decoder](https://www.lcsc.com/de/product-detail/C2653311.html).

Eight sinks add about $0.1176 in installed parts at the 100-piece tier; the buffer adds $0.2754 at the 50-piece tier. Compare adequate cheaper vendors and assembly charges before freezing these choices. Same-name parts from different manufacturers still require datasheet and pin-map review.

The [manufacturer-authored orange LED datasheet](https://datasheet.lcsc.com/datasheet/pdf/b40afb7140c7e33828adf1e17d75beb8.pdf?productCode=C965813) specifies 20 mA continuous, 1.8–2.4 V forward voltage at 20 mA/25 °C, orange 600–610 nm and MSL 3. Resistor-limited operation stays below its continuous-current rating even if scanning stops. Actual brightness at the chosen duty/current needs qualification.

Additional supplier pages: [UART buffer](https://www.lcsc.com/product-detail/C21404.html), [regulator](https://www.lcsc.com/product-detail/C35259.html), [USB-C socket](https://www.lcsc.com/product-detail/C165948.html), [current limiter](https://www.lcsc.com/product-detail/C55266.html).

The [MCU listing](https://www.lcsc.com/product-detail/C5187096.html) and
[current-limiter listing](https://www.lcsc.com/product-detail/C55266.html) were
refreshed on 2026-10-11. The selected Nexperia decoder pricing is shown above.
Use `python3 scripts/v4_bom.py --tiles 5 --heads 1` for exact candidate fitted
quantities from the schematic. It gives 320 orange LEDs and 566 total fitted
parts for this provisional chain; it does not add supplier minimums or spares.

Passive candidates now recorded in the schematic include UNI-ROYAL 1.2 kΩ/0805 C17379 (R1–R8), 100 kΩ/0805 C149504, 2.2 kΩ/0805 C17520, 100 kΩ/0603 C25803, 2.2 kΩ/0603 C4190, 5.1 kΩ/0603 C23186 and 33 kΩ/0603 C4216. The 1.2 kΩ choice improves row-buffer supply-current margin without extra parts. All five 100 nF bypasses use Yageo CC0603KRX7R9BB104/0603 C14663. C8/C9 now use candidate CL21B475KAB6PNE/0805 C16194942 (4.7 µF, 25 V, X7R), with effective-capacitance qualification pending. These are researched candidates, not a released purchase list. MCU sourcing is now C5187096.

Switch drawing obtained from the [manufacturer-authored PDF](https://datasheet.lcsc.com/datasheet/pdf/c6651ef0d35056b6421502c57daea130.pdf?productCode=C720479): pins 1/2 are internally common and 3/4 are internally common; actuation joins the two rows. The recommended land pattern is 5.60 × 3.10 mm overall, 1.25 × 1.20 mm pads at ±2.175/±0.95 mm. The v4 local footprint and switch MPN were updated to XUNPU TS-1089S-AR02516, C720479.

Still to complete: resistor drift allowance, capacitor bias data, head-protection qualification, edge-contact process, assembly costs and prototype quantities. The final LCSC buying list must distinguish tile, head-only and optional parts and reflect the completed design.

Lifecycle check on 2026-10-11: [Samsung marks CL21B475KOFNNNE's family NRND](https://product.samsungsem.com/mlcc/CL21B475KOFNNN.do), with no specified replacement.
C107365 was therefore replaced in the source with [CL21B475KAB6PNE/C16194942](https://www.lcsc.com/product-detail/C16194942.html),
whose [Samsung family page](https://product.samsungsem.com/mlcc/CL21B475KAB6PN.do)
states Mass Production. Ten cost $1.089 at the refreshed snapshot (9,100 stocked),
adding $0.722 to the five-board batch. Manufacturer bias curves and existing land
compatibility are assessed in the design brief. Effective capacitance under
bias/temperature and regulator stability still need first-article evidence.


Prototype quantity comparison (2026-10-11): the user defaults to five boards.
Each set below has one USB head. Parts subtotals round to supplier multiples and
choose a cheaper quantity break when it reduces the total cash outlay.

| Quantity | Parts, without extra spares | PCB, lead-free HASL | Combined reference subtotal |
| --- | --- | --- | --- |
| 5 | $15.84 | $13.10 | $28.94 |
| 20 | $45.87 | $35.20 | $81.07 |

PCB values were obtained from the anonymous [JLCPCB parameter quote](https://cart.jlcpcb.com/quote/)
for 40.64 × 49.27 mm, four layers, 1.6 mm, green mask, 1 oz outer/0.5 oz inner,
regular outline tolerance and standard build time. No files were uploaded and no
cart/order was created. An uploaded-Gerber engineering review may change the price.
Ordinary leaded HASL instead showed $8.00 / $30.00. The five-board web quote also
advertised a separate JLCONE desktop promotion; this comparison uses web prices.

These figures exclude shipping, tax, stencil and assembly. Adding 10% nominal
spares to component requirements gives $23.66 / $55.09 in parts; MOQ rounding
causes some IC quantities to double. The five-board spare worksheet chooses 500
LEDs because that quantity break costs less than 400. Keep five prototype PCBs
as the normal first iteration; common spare parts can carry into later revisions.
Twenty untested PCBs increase the cash tied to this revision by about $52.13.

C1591 and C23003 were replaced after confirming in-stock equivalents: Yageo
CC0603KRX7R9BB104/C14663 (100 nF, 50 V, X7R, ±10%, 0603) and UNI-ROYAL
0603WAF3302T5E/C4216 (33 kΩ, ±1%, 100 ppm/°C, 0603). The slightly changed
current-limit value remains below the intended 1 A envelope; see the design
brief for recalculation. These replacements preserve all pads and copper.
C5187096 remains unavailable in the current LCSC snapshot; its figure is a
reference price. Recheck stock or source the exact TSSOP MCU before buying. C5299908 is
CH32V003F4U6 in QFN, so it is **not** a TSSOP replacement for the selected MCU.
`v4_cost.py --refresh` records public supplier snapshots; its output lists stock
limits. Prototype lists are under ignored `build/hardware/v4/`, separately from
the manufacturing head/follower BOMs. Physical qualification and the final
production purchase list remain outstanding.

Replacement sources: [Yageo exact-part sheet](https://www.yageogroup.com/download/specsheet/CC0603KRX7R9BB104), [capacitor stock/price](https://www.lcsc.com/product-detail/C14663.html), [resistor stock/price](https://www.lcsc.com/product-detail/C4216.html).

The exact TSSOP20 MCU is available from
[Olimex](https://www.olimex.com/Products/RISC-V/WCH/SMD-IC-CH32V003F4P6/):
one pack of ten CH32V003F4P6 chips lists at €2.50, in stock on 2026-10-11.
This changes the supplier, not the chip or PCB. For five boards the in-stock
LCSC parts excluding MCUs total $14.39, plus that €2.50 MCU pack. For twenty,
they total $40.06 plus two packs (€5.00). Delivery and tax remain separate;
do not add the currencies without checking the exchange rate. JLCPCB's
assembler inventory also currently shows zero stock for C5187096 and offers
pre-ordering in quantities of 32; those parts cannot be shipped separately.
User-arranged fabrication/assembly must allow for the MCU source or consignment.


## Updated SWIO and mechanical prototype worksheet

The selected SWIO connector is the optional vertical Molex 530470310, [LCSC C122442](https://www.lcsc.com/product-detail/C122442.html), currently $0.1321 at a five-piece minimum. The [C5221408 pigtail](https://www.lcsc.com/product-detail/C5221408.html) is $0.0752 each before the temporary promotion, with a five-piece minimum; cross-vendor mating needs a sample. One reusable probe cable is the requirement; the supplier minimum leaves spares.

After the C8/C9 lifecycle replacement, the five-board stock-available PCB component subtotal is $15.77, including five optional headers and one USB head; twenty boards total $45.59. The pigtail minimum adds $0.38. The full reference worksheet is $17.60 for five and $51.77 for twenty, including an unavailable MCU price; these are not complete available carts. CH32V003F4P6/C5187096 remains out of stock. PCB, printed parts, fasteners, assembly, delivery and tax are separate. Earlier price comparisons above predate the optional headers and capacitor replacement.

The importer files are `build/hardware/v4/lcsc-available-{5,20}-boards.csv`; candidate pigtails are separate in `lcsc-probe-accessories-{5,20}-boards.csv`. The user will verify USART/I2C on v3 before ordering v4. Physical v4 qualification and final sourcing remain open.

## User shelf stock — 2026-10-11

`config/parts-stock.csv` normalizes the supplied eleven-line LCSC order. Its
source filename/hash and consumption assumptions are recorded in
`config/parts-stock-source.json`; the original receipt is left untouched.
One assembled v3 board is deducted using the archived schematic. The user
reported roughly two ICs used while debugging disconnected ground, so each IC
type allows zero to two additional losses. These are estimates, not a physical
stocktake: CH32V003F4P6 has 47–49 left, SN74HC138PWR 47–49, and the assumed
orange-LED count is 936. Four 100 nF capacitors, one 10 µF capacitor, two switches,
four 10 kΩ resistors and two 4.7 kΩ resistors are deducted. V3's eight unspecified
row values leave an unknown 51/68 Ω split; their independent ranges are 992–1000
each, rather than inventing an exact count.

Only exact LCSC/MPN matches are credited to v4: the MCU and orange LEDs.
The old HC138 decoder has different output polarity/logic-family requirements;
the old 0805 bypass capacitors do not match v4's 0603 lands. Switches and the
10 µF X5R capacitors remain substitution candidates needing explicit review.
Other owned resistor values are not the selected v4 values. No CAD/BOM
substitution was made during stock reconciliation.

Run `python3 scripts/v4_cost.py --inventory config/parts-stock.csv` to create
separate `*-stock.csv` estimates/imports without overwriting the earlier
no-stock worksheets. It deducts the conservative remaining quantity before MOQ
and price-break selection; shelf-supplied lines buy zero pieces even if the
supplier is out of stock. The five-board PCB-parts cash estimate falls from
$15.77 to **$12.69**, or **$13.07** including the candidate pigtail minimum.
Twenty boards need 344 more LEDs (buy 350 at the saved quote), with **$39.83** in
PCB parts or **$40.21** including the pigtails. All MCUs are covered in both
batches. Prices use the existing supplier snapshots and exclude PCBs, mechanics,
assembly, shipping and tax.

No parts are reserved for the next v3 board yet. Set the inventory `reserved`
column before final buying: a second v3 board would reserve another 64 LEDs and
one MCU/decoder, plus its remaining components. Five v4 boards still fit within
the available MCU/LED stock; the twenty-board LED purchase would change.
The detailed remaining-range report is `build/hardware/stock/remaining.csv`.

The user organizes cut tape in Printables model 580643. Magazine filling is a
soft preference: optimize total cash, price breaks and useful stock as well.
The user explicitly favours 1,000 reusable resistors when the batch costs roughly
$1.50, even with tight packing. `config/smd-storage.json` records per-part capacity:
1,000 XL-2012UOC LEDs fitted into two magazines, so 500 each is confirmed as a
tight fit. These LEDs use flexible plastic tape; the user reports paper tape is
harder to fit and will check the other components. Width, pocket pitch and tape
thickness/type affect packing, so a common quantity is not inferred from 0805
or 0603 package size alone.

Add `--magazines config/smd-storage.json` to the stock-adjusted cost command for
separate `*-stock-magazines.csv` outputs. Only supplier MOQ/multiples constrain
quantities; magazine capacities add comparison candidates and packing notes.
Unknown capacities do not prevent cost optimization. Shelf-covered parts buy
zero. The editable draft heuristic recommends 1,000 reusable resistors when the
batch costs up to $2, interpreting the user's roughly $1.50 example; this is an
automatic suggestion threshold, not a purchase budget or packing requirement.
It leaves the minimum-cash quantity, total and extra spend visible. Parts outside
that heuristic retain the minimum-cash recommendation for individual review.

The three selected 0603 bulk lines cost $1.20/$1.40/$1.60 for 1,000 each, versus
$0.15/$0.18/$0.21 for their 100-piece minimums. This adds $3.66 to either batch:
five-board recommended new PCB parts are $16.35, or $16.73 with candidate pigtails;
twenty-board totals are $43.49/$43.87. The twenty-board LED shortfall can still
buy 350 for $3.08; one 500-piece magazine is an alternative at $3.40 (+$0.32),
not an enforced choice. Full tier comparisons are in
`lcsc-price-options-{5,20}-boards-stock-magazines.csv` beside the purchase sheets.
All figures use supplier snapshots and exclude boards, assembly, mechanics,
shipping and tax. These are drafting recommendations; no order is created.

## Current stock-aware buying snapshot — 2026-10-12

This supersedes earlier stock/quantity/cash estimates above. All 21 selected
LCSC listings were refreshed and checked against the exact code/MPN. They
currently have stock, including C5187096 (3,980 pieces) and C547472 (290).
The direct product snapshots and timestamps are preserved in the handoff;
recheck at checkout. [MCU](https://www.lcsc.com/product-detail/C5187096.html),
[decoder](https://www.lcsc.com/product-detail/C547472.html).

The receipt is an estimate rather than a counted stocktake. Inventory now
reserves one further v3 board first, including one MCU/decoder, 64 LEDs,
buttons/capacitors/pulls and both possible row-resistor choices until confirmed.
Conservative remaining stock credits 46 exact-MPN MCUs and 872 orange LEDs.
Five v4 boards consume 320 LEDs; twenty consume 1,280, so buy 500 more at $3.40.
No MCU purchase is needed in either case. No v3 decoder, 51/68 Ω resistor or
unidentified capacitor substitution was made.

| Prototype quantity | Minimum cash incl. optional cable | Recommended incl. optional cable |
| --- | --- | --- |
| Five, one USB head | $13.07 | **$16.73** |
| Twenty, one USB head | $40.54 | **$44.20** |

Both columns include five/twenty optional SWIO headers and the $0.38 pigtail
MOQ. The recommended column chooses 1,000 each of C23186/C4190/C4216 at
$1.20/$1.40/$1.60, adding $3.66 over their 100-piece minimums. Magazine capacity
is a soft preference; other quantities follow price breaks, need and supplier
minimums. Assembly, PCBs, screws/wire, printing, delivery and tax are separate.
The earlier $13.10/$35.20 PCB quote remains a baseline, not a new upload/quote
for this symmetric CAD revision.

Generate with:

```sh
python3 scripts/v4_cost.py --inventory config/parts-stock.csv --magazines config/smd-storage.json
python3 scripts/v4_package.py --with-firmware
```

The package's `procurement/BUY-5-BOARDS.csv` and `BUY-20-BOARDS.csv` are LCSC
import lists for the recommended PCB parts. Optional cable imports are separate.
Detailed sheets retain fitted requirements, shelf credits, reserves, spares,
MOQ, tiers and alternatives; supplier snapshots are included. No order/cart
has been submitted. Finish the planned v3 two-board I2C check before fabrication.

## Cost reduction after the first prototypes — 2026-10-12

The user accepts the selected parts for a small initial test, while explicitly
requesting cheaper alternatives for subsequent quantities. Samsung, TI and
Nexperia are not required brands. The current order establishes a reviewed
baseline; cost comparisons and substitution experiments must preserve the
features and electrical limits that the application actually needs.

Current public-page snapshots, excluding delivery/tax/assembly:

| Selected part | Installed per tile | Unit price at prototype quantity | Unit price at 500 pieces |
| --- | --- | --- | --- |
| Samsung C16194942, C8/C9 | 2 | $0.1089 | $0.0735 |
| TI C6778, HCT244 row buffer | 1 | $0.2949 | $0.1647 |
| Nexperia C547472, HCT238 decoder | 1 | $0.3463 | $0.1974 |
| TI C21404, UART buffer | 1 | $0.2091 | $0.1203 |
| WCH C5187096, MCU | 1 | $0.2916 reference; current batch uses shelf stock | $0.1646 |

The three logic ICs total $0.8503 per tile at the initial tiers; C8/C9 add
$0.2178. The MCU is unusually inexpensive, so supporting chips can dominate
despite doing simpler jobs. Compare quantities at the same procurement tier,
and distinguish fitted BOM cost from reusable stock/MOQ cash in the initial cart.
[Capacitors](https://www.lcsc.com/product-detail/C16194942.html),
[row buffer](https://www.lcsc.com/product-detail/C6778.html),
[decoder](https://www.lcsc.com/product-detail/C547472.html),
[UART buffer](https://www.lcsc.com/product-detail/C21404.html),
[MCU](https://www.lcsc.com/product-detail/C5187096.html).

The next cost pass should cover:

1. C8/C9: cheaper capacitor families or the already-owned Samsung
   CL21A106KAYNNNE/C15850 (10 µF, X5R, 0805). Validate exact lands/body height,
   effective capacitance under bias, temperature/ageing and regulator stability.
   The conservative shelf estimate is 198 pieces after the second-v3 reservation;
   a substitute would avoid buying this line for a future batch. Do not reduce
   voltage/capacitance specifications based on nominal values alone.
2. Logic ICs: compare lower-cost manufacturers with suitable packages and
   guaranteed characteristics. A bounded listing check found MDD 74HCT244PW,
   C54411089, TSSOP-20L: 1,960 stocked, five-piece minimum, $0.2082 at five /
   $0.1199 at 500. This is a sourcing candidate, not an approved drop-in: verify
   its pin map, body/lands, drive, TTL thresholds, input-current allowance and
   switching behavior against the actual load.
3. Circuit simplification: use first-board current, GPIO-level, brightness and
   interface measurements to assess whether a buffer/regulator function can be
   removed or combined economically. The v3 HC138 cannot replace the current
   HCT238 directly: decoder polarity and input thresholds differ. Returning to
   direct drive needs a demonstrated current/voltage budget for worst patterns.

A second capacitor listing for comparison is Yageo CC0805KKX5R8BB475/C132173,
4.7 µF, 25 V, X5R, 0805: 124,195 stocked, five-piece minimum, $0.0848 at five /
$0.0541 at 500. It still needs lifecycle, bias, package and regulator review.
These first candidates offer moderate savings; broader sourcing or removing a
function may save more. No lower-cost vendor or different dielectric has been
qualified, and no candidate has been added to the current purchase CSV.
[MDD candidate](https://www.lcsc.com/product-detail/C54411089.html),
[Yageo candidate](https://www.lcsc.com/product-detail/C132173.html),
[owned capacitor](https://www.lcsc.com/product-detail/C15850.html).

Record cheaper variants in separate development copies, measure them against
the original prototype, and then promote a reproducible BOM. This follow-up
does not change the current CAD, firmware, quantities or draft carts. The bounded
price evidence is under ignored `build/hardware/v4-cost-followup/`.

## Three TI replacements: sourcing and datasheet review — 2026-10-12

This follow-up covers U3 SN74HCT244PWR, U4 SN74LVC2G125DCUR and head-only
U5 TPS2553DBVR. The decoder U2 is Nexperia, outside these three. Prices below
are current public-page snapshots in USD, before delivery/tax; supplier
minimums matter. Original prototype CAD, buying CSVs and carts are unchanged.

| Reference | Selected part price | Cheaper candidate | LCSC | Candidate price / minimum | PCB implications |
| --- | --- | --- | --- | --- | --- |
| U3 row buffer | $0.2949 at 5 | JSMSEMI 74HCT244PW,118-JSM | C53114424 | $0.1714 / 5; $0.1011 at 500 | Same TSSOP20 body/pitch and pin functions; vendor qualification pending |
| U4 UART buffer | $0.2091 at 5 | TECH PUBLIC 74LVC2G17GW | C19829576 | $0.0532 / 10; $0.0436 at 300 | Six-pin SOT363, requires footprint/routing changes |
| U5 USB current limiter | $0.5434 at 1 | TI TPS2553DDBVR | C521201 | $0.1878 / 5; $0.1064 at 500 | Same DBV pinout; existing 33k current-limit calculation matches |

Snapshot stock: 2,015 JSMSEMI buffers, 7,070 TECH PUBLIC buffers and 11,390
TPS2553D parts. These are viable sourcing/engineering candidates, not physically
qualified substitutions. [U3 listing](https://www.lcsc.com/product-detail/C53114424.html),
[U4 listing](https://www.lcsc.com/product-detail/C19829576.html),
[U5 listing](https://www.lcsc.com/product-detail/C521201.html).

JSMSEMI's manufacturer sheet confirms both active-low OE groups, inputs
2/4/6/8/11/13/15/17, corresponding outputs 18/16/14/12/9/7/5/3, GND 10 and
VCC 20. HCT supply is 4.5–5.5 V, VIH 2 V, VIL 0.8 V; the full-temperature
output specification includes VOH ≥3.7 V at −6 mA/VCC=4.5 V. The 70 mA
package-current rating and input-current contribution still need a load-budget
review and measurements. TSSOP body 6.4–6.6 ×4.3–4.5 mm, 0.65 mm pitch,
matches the current land pattern. Retain the 1.2k row resistors for comparison.
[Manufacturer sheet](https://datasheet.lcsc.com/datasheet/pdf/df4269938ac964ea432aecaaf93ecf21.pdf?productCode=C53114424).

U4's OE inputs are permanently grounded, so always-enabled non-inverting
buffers can replace that function in a new layout. TECH PUBLIC's 2G17 sheet
specifies 1.65–5.5 V supply, 5.5 V tolerant inputs, Ioff ±10 µA, and
light-load VOH ≥VCC−0.1 V. Pin map is 1 A1, 2 GND, 3 A2, 4 Y2, 5 VCC,
6 Y1; GW is SOT363, not the current eight-pin footprint. Schmitt thresholds
and the sheet's 25 °C electrical-characterization scope require validation
with the actual MCU/adapter levels and intended temperatures. This part must
not replace C21404 in the current assembly CSV.
[Manufacturer sheet](https://datasheet.lcsc.com/datasheet/pdf/243c1f26ceed969cd4ed7d33e8e5a293.pdf?productCode=C19829576).

TPS2553DDBVR remains TI, but is substantially cheaper. Its manufacturer sheet
confirms the same IN1/GND2/EN3/nFAULT4/ILIM5/OUT6 pinout and active-high,
constant-current/recovery behavior. The 33k ±1% resistor gives about
715.7–867.1 mA; a 3% total resistor allowance gives an 883.9 mA steady maximum.
These match the existing resistor calculation. It operates at 2.7–6.5 V,
appropriate for the intended regulated 5 V input; current, temperature,
inrush and short recovery still need measurements. Five cost $0.939: cheaper
per IC, but more initial cash than buying one original at $0.5434.
[TI datasheet](https://www.ti.com/lit/ds/symlink/tps2553d.pdf).

A non-TI U5 candidate is DIODES AP2553W6-7/C212302, $0.2315 at five
(61,050 stocked; $0.1312 at 500). Its SOT26 pin functions also match. Its
33k calculation is approximately 709.3–859.0 mA with ±1% resistor tolerance,
or 875.0 mA maximum with a 3% allowance. Its limit/short-circuit behavior and
5.5 V maximum input need separate qualification; the TI D variant is cheaper
at the checked tiers. [Listing](https://www.lcsc.com/product-detail/C212302.html),
[manufacturer datasheet](https://datasheet.lcsc.com/datasheet/pdf/4799ce13c8a27f7e69031649961075dd.pdf?productCode=C212302).

Rejected shortcuts: HC244 has unsuitable guaranteed input thresholds for the
present 3.3 V-to-5 V arrangement; cheap LOWPOWER LPW5213B6F has a different
pinout and lacks the adjustable limiter used here. An aggregator's “similar”
label is insufficient. No materially cheaper same-footprint UART replacement
was established; the listed Nexperia 2G125DC was dearer at $0.5393 and had
only 21 pieces in stock.

Optional sample imports are kept separate from the production-part list:
`build/hardware/v4-ti-alternatives/samples-current-footprints.csv` contains
five JSMSEMI U3 and five TI D U5 candidates (about $1.80).
`samples-uart-redesign.csv` contains ten TECH PUBLIC UART candidates ($0.532),
for a different footprint/bench adapter. Combined samples cost about $2.33.
Datasheets, OCR/page images, supplier snapshots and limit calculations are
preserved under that ignored directory. No samples were added to any cart.
