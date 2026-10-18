# JLCONE pricing and combined shipping

Checked on 2026-10-12 in the logged-in JLCONE 1.0.72 desktop app, using the
already-uploaded v4 Gerber quote. Five bare boards were quoted at **$2.00 plus
$1.50 shipping to Poland**. The repo's lead-free HASL/tented-via configuration
was separately checked at **$7.10 plus $1.50 shipping**. These are quote-page
estimates before checkout taxes or other charges; no order was placed.

The user selected **HASL(with lead)** for v4 after this comparison on
2026-10-12. Use the **$2.00 PCB + $1.50 shipping = $3.50** estimate for the
five-board purchase comparison. The lead-free quote below is retained as a
comparison only. The main hardware workflow has now aligned the source finish, exporter check
and regenerated package with this choice (`HAL SnPb`). Ordinary vias remain
tented on both faces. Reupload the latest Gerbers with the passive labels; the
earlier quote used an older PCB revision.

## Reproducing the $2 PCB quote

The tested configuration was:

| Setting | Value |
| --- | --- |
| App | JLCONE desktop, logged in, USD |
| Material / layers | FR-4, FR4 TG135, four layers |
| Dimensions | 40.64 × 49.27 mm, detected from the uploaded Gerber |
| Quantity / designs | Five boards, one design, Single PCB |
| Thickness | 1.6 mm |
| Mask / silk | Green / white |
| Finish | HASL(with lead) |
| Copper | 1 oz outer, 0.5 oz inner |
| Vias | Plugged; Tented was also checked at the same price |
| Minimum via option | 0.3 mm hole / 0.4–0.45 mm diameter |
| Plating / outline | Not Specified / ±0.2 mm Regular |
| Mark / electrical test | Remove Mark / Flying Probe Fully Test |
| Build time | Standard, 3–4 days |
| Extra processes | No castellated holes, edge plating, gold fingers or backdrill |

The breakdown displayed a $2.00 Special Offer, with the normal $8.00 crossed
out. No coupon was selected to obtain it. JLCPCB identifies the $2 deal and
discounted shipping as desktop-exclusive promotions. Its random checkout
discount and coupon bundle are separate offers.
[Official JLCONE announcement](https://jlcpcb.com/news/jlcpcb-jlcone-desktop-app).

Switching to LeadFree HASL kept the $2.00 base offer and added $5.10 for the
finish. Tented vias added $0.00. Both changes together were checked at $7.10;
this investigation did not change the repo's fabrication baseline.

Gerber dimensions were read-only, so the maximum eligible board dimensions
were not tested. This records a working configuration, not a complete reverse
engineering of every eligibility rule. Requote the final revision and any added
fabrication processes before comparing totals.

## The $1.50 shipping promotion

Select **Global Standard Direct Line** for **Poland**. The quote estimated
12–18 business days and 0.16 kg for five boards. Its shipping-method popup showed
$1.50 discounted from $4.55, three uses per month, three remaining, and expiry
on **2026-12-31**. No purchase was made and the remaining count stayed at three.

The route itself lists limits of 1.5 kg, $150 and 55 × 40 cm. Those are service
limits; the $1.50 promotion stopped applying well below the weight limit.

These comparisons explicitly selected the same shipping service after each
recalculation. All rows use the original 1.6 mm, leaded-HASL board settings
unless indicated otherwise.

| Boards / change | PCB quote | Estimated weight | Direct-line shipping |
| --- | ---: | ---: | ---: |
| 5, original | $2.00 | 0.16 kg | $1.50 |
| 5, lead-free HASL + tented vias | $7.10 | 0.16 kg | $1.50 |
| 10 | $8.00 | 0.19 kg | $1.50 |
| 20 | $30.00 | 0.26 kg | $1.50 |
| 25 | $31.20 | 0.29 kg | $1.50 |
| 30 | $32.50 | 0.33 kg | $7.04 |
| 50 | $37.40 | 0.47 kg | $8.87 |
| 100 | $47.60 | 0.82 kg | $13.42 |

A separate 30-board quote at 0.8 mm thickness estimated 0.24 kg and regained
$1.50 shipping despite its higher $37.80 PCB price. A 50-board, 0.8 mm quote at
0.32 kg did not. This supports a weight-dependent promotion cutoff around
**0.30 kg**, rather than a simple board-count or low-price limit. The exact
boundary and rounding rule were not exposed; 0.29 kg passed and 0.32 kg failed.

JLCONE reset the selected shipping method to DHL during parameter changes.
Reopen Shipping Estimate and explicitly select Global Standard Direct Line
before comparing prices. Noneligible rows displayed zero promotion uses and a
placeholder expiry; the original eligible quote still displayed three uses
remaining. Do not interpret that placeholder as consumed discounts.

The app was left at its original five-board, 1.6 mm, leaded-HASL, plugged-via
configuration with the $2.00 PCB and $1.50 shipping estimates restored.

## Combining JLCPCB and LCSC purchases

LCSC's current procedure requires separate orders with the same customer ID
and currency. The LCSC parcel must remain unshipped; mainland-China destinations
are excluded. Combined orders cannot subsequently be split.
[Official consolidation instructions](https://www.lcsc.com/help-center/notice/combine-lcsc-jlcpcb-orders).

1. Before JLCPCB checkout, use LCSC's Hong Kong consolidation warehouse as the
   destination. Copy its current address from the linked instructions; the
   policy says this destination cannot be changed afterward.
2. Place the JLCPCB order first. During the subsequent LCSC checkout, select
   that order for consolidation.
3. If parts were ordered already, contact `support@lcsc.com` with both order
   numbers to request a shipment hold and combination.

Shipping is recalculated and may require another payment. Compatibility with
the desktop $1.50 direct-to-Poland promotion was not verified: a warehouse
shipment follows a different route. Compare the complete consolidated price
against separate deliveries before paying. No support message was sent.

## Accessing the desktop quote during future checks

The app is installed per user and starts with `jlcone`. This session used
Electron's local DevTools protocol to read quote controls and make reversible
parameter comparisons. Close the normal app before launching a debug session:

```sh
jlcone --remote-debugging-port=19327 --remote-debugging-address=127.0.0.1
```

The debugging listener was verified on loopback. Target discovery is at
`http://127.0.0.1:19327/json/list`; operate on the `cart.jlcpcb.com/quote` target.
Restart normally afterward to end debugging access. The normal launcher was
not changed to enable debugging. No credentials, personal addresses or session
tokens are stored in this note.

## Live comparison with the adjusted parts cart — 2026-10-12

The user chose to keep the original components and increased some quantities
manually. Leave the cheaper-alternative samples out of this purchase and
preserve the adjusted cart quantities. LCSC currently shows $37.78 merchandise,
−$0.17 discount and $14.10 Global Direct Standard Line shipping: $51.71 total,
with an estimated 1,500 g shipping weight. This is a cart estimate, not final
checkout tax/customs or a measured parcel weight.

The newly uploaded labelled v4 Gerbers quote at $2.00 for five boards. JLCONE
direct-to-Poland delivery remains $1.50, so the separate-order comparison is
$55.21 total at the displayed cart/quote amounts ($15.60 shipping combined).
A reversible Hong Kong estimator check quoted S.F Express at $2.79 for the
PCB-to-consolidation-warehouse leg. The estimator was restored to Poland.

Consolidation only beats separate delivery if LCSC's recalculated final
shipment costs **less than $12.81**, before any extra charges: $15.60−$2.79.
No final consolidated quote was available because it requires linking the
JLC order during LCSC checkout; no paid JLC order was submitted. The extra PCB
weight can affect the shipping tier, so savings are not assumed. Separate
deliveries currently provide the known comparison. No support message was sent.

One manufacturing-option difference remains visible: the current four-layer,
leaded-HASL quote selects standard **Plugged** vias and disables Tented. The
previous tented-via price check was with lead-free HASL. Before checkout,
reconcile the factory option/instructions with the source's mask-covered vias;
ordinary ink plugging is different from epoxy-filled/copper-capped processing.
Keep solderable 0.6/0.8 mm holes and USB retention slots open.

Before the user proceeds with the PCB-only purchase, the draft quote was
prepared with **Confirm Production file: Yes** and **Do not confirm
automatically** checked. Its PCB remark now reads:

> Plug covered 0.30mm vias only where process allows. Keep exposed testpoint vias, 0.60/0.80mm solder holes, NPTH and plated USB slots open. Follow mask openings. No epoxy/copper capping.

This specifies the ordinary ink-plugging quote rather than the handoff's
earlier tented/no-plugging process wording; it does not change the Gerber
geometry. The factory production files still need review for the preserved
mask openings and usable solder holes. No order was saved or submitted by
the agent. See [JLCPCB's via-covering guidance](https://jlcpcb.com/help/article/pcb-via-covering).
Production-file review adds **$1.05**: the prepared PCB quote is **$3.05**.
Changing that setting reset delivery to DHL; Global Standard Direct Line
was restored to **$1.50**, for **$4.55 before checkout taxes/other charges**.

## TME and DigiKey feasibility check — 2026-10-12

The user requested a local/alternative supplier comparison because the LCSC
shipping estimate is $14.10. The adjusted LCSC cart remains untouched. The
following is a public-listing feasibility check, **not a complete alternative
basket quote**. Product pages returned different cached snapshots; refresh
stock and prices before buying. Direct TME browser access stopped at its
security-verification page, so live account prices were not obtained.

| Supplier | Delivery to Poland | Procurement finding |
| --- | --- | --- |
| LCSC | Current cart $14.10; parts after discount $37.61, displayed total $51.71 | Existing original-component basket, including user-added stock quantities |
| TME | Pocztex 17.10 zł gross; DPD/GLS/FedEx/InPost 19.56 zł gross | Some exact parts available, but a complete basket has not been established |
| DigiKey | Free from 300 zł; 80 zł below the threshold | Exact UART buffer and power switch listings show zero stock; complete basket not established |

The DigiKey threshold is **300 zł, not 200 zł**. Its shipping help page does
not resolve the VAT basis of the qualifying threshold; use checkout for that
detail. Marketplace purchases can have separate shipping. These PLN delivery
figures must not be compared as landed totals against the LCSC cart without
confirming VAT/customs treatment.

Relevant exact-part findings at the user's current quantities:

- Molex 53047-0310/530470310: TME lists 0.60 zł net / 0.74 zł gross at
  10+; fifteen cost about 11.10 zł gross at the rounded published unit price.
- TPS2553DBVR: TME lists five in stock and 3.33 zł net / 4.10 zł gross
  at 4+; five cost about 20.50 zł gross. DigiKey's exact listing shows
  zero stock; TPS2553DBVR-1 is a different operating variant and is not
  an automatic replacement.
- SN74HCT244PWR: TME's international listing shows $0.37 net at 10+,
  versus LCSC $0.2949 at the cart's twenty pieces. These are indicative
  USD list-price comparisons, not a Polish checkout quote.
- SN74LVC2G125DCUR: TME's international listing shows $0.37 net at 10+,
  versus LCSC $0.2091 for twenty. DigiKey's exact listing shows zero stock.
- Nexperia 74HCT238PW,118: the TME listing found in search shows zero
  stock, but that snapshot is older and could not be confirmed live.
- Exact Royalohm 0805W8F1201T5E and 0603WAF2201T5E listings show a
  5,000-piece minimum/multiple, versus current LCSC quantities 200 and
  1,000 respectively. Their rendered $0.00 prices are rounding artifacts,
  not free parts. Equivalent resistor listings may have smaller minimums.
- Exact ME6206A33M3G regulator and Samsung CL21B475KAB6PNE listings
  were not found at TME/DigiKey in this search. This is not proof that no
  compatible alternatives exist; pinout, capacitor stability/bias and
  mechanical fit still require review before using substitutes.

Recommendation for the present original-part purchase: retain LCSC as the
known complete basket unless a complete locally sourced alternative is
qualified and priced. Moving only available items to TME leaves the LCSC
shipping charge and adds domestic delivery. Do not add unnecessary DigiKey
stock merely to reach free shipping. For later iterations, local availability
should be considered when selecting alternate regulators, buffers and USB
connectors, alongside the already recorded cheaper LCSC options.

Sources:

- [TME domestic shipping](https://www.tme.eu/pl/how-to-buy/7428/Sposob-i-koszty-transportu/)
- [DigiKey Poland delivery policy](https://www.digikey.pl/pl/help-support/delivery-information/delivery-time-and-cost)
- [TME Molex header](https://www.tme.eu/pl/details/mx-53047-0310/zlacza-sygnalowe-raster-1-25mm/molex/53047-0310/)
- [TME TPS2553DBVR](https://www.tme.eu/pl/details/tps2553dbvr/power-switches-uklady-scalone/texas-instruments/)
- [TME HCT244](https://www.tme.eu/en/details/sn74hct244pwr/buffers-transceivers-drivers/texas-instruments/)
- [TME UART buffer](https://www.tme.eu/en/details/sn74lvc2g125dcur/buffers-transceivers-drivers/texas-instruments/)
- [DigiKey UART buffer](https://www.digikey.pl/pl/products/detail/texas-instruments/SN74LVC2G125DCUR/484831)
- [DigiKey TPS2553DBVR](https://www.digikey.pl/pl/products/detail/texas-instruments/TPS2553DBVR/2047900)
- [TME 1.2k 0805 resistor](https://www.tme.eu/en/details/0805w8f1201t5e/smd-resistors/royalohm/)
- [TME 2.2k 0603 resistor](https://www.tme.eu/en/details/0603waf2201t5e/smd-resistors/royalohm/)

## Assembly comparison — rejected by the user, 2026-10-12

The user explicitly authorized uploading the v4 BOM and placement CSV for an
assembly quote, then explored omitting TME-sourceable parts and all extended
parts. The comparison used Economic bottom-side assembly on five identical
USB-capable tiles, omitting the stocked MCU, front LEDs and optional SWIO
header. This was a cost comparison, not an accepted population change or a
fully reviewed assembly release. No assembly order was placed or paid.

| Quote | PCB | Assembly | Subtotal before shipping/coupon/tax |
| --- | ---: | ---: | ---: |
| All rear components except MCU: 17 types / 53 placements per tile | $3.05 | $52.70 | $55.75 |
| Basic only: seven resistor types + 100 nF bypasses, 35 placements per tile | $3.05 | $12.20 | $15.25 |

The full comparison included $27.81 extended-part feeder fees, $12.62 parts,
$8.24 setup, $1.55 stencil, $1.57 placement and $0.91 nitrogen reflow.
The basic-only comparison had **zero extended fees**, $0.90 parts, $8.24
setup, $1.55 stencil, $0.59 placement and $0.91 nitrogen reflow. PCB cost
includes the $1.05 production-file review option. Shipping was not quoted for
either assembled population. Do not reuse the bare-board $1.50 delivery
estimate as a verified PCBA shipping price.

The public promotion describes a $9 coupon covering approximately the setup
fee, but no eligible small-order assembly coupon was confirmed in the
account: the existing coupon page displayed no coupons, and current public
PCBA offers required either an EasyEDA design or a much larger order. No
coupon was claimed/applied; no assumed discount is included above.

The user rejected assembly as uneconomic. Retain the original LCSC cart and
return the app to the bare-PCB quote. The uploaded assembly draft is a price
experiment only; its basic-only population is incomplete. Source CAD and the
original full BOM/CPL exports were not changed. Filtered comparison CSVs,
scenario notes and preview screenshots are in ignored
`build/purchase-v4/assembly/`.

The search also found local substitution candidates: TME stocks Nexperia
BSS138BK,215 and Samsung CL21B475KAFNNNE, and lists Royalohm
0805S8F1201T5E cut-tape resistors. These are **not accepted substitutions**.
The Nexperia MOSFET's 2.5 V resistance specification has a different test
current, and the Samsung capacitor still needs a part-specific bias review.
Merely sharing BSS138BK or 4.7 µF/25 V/X7R markings does not complete the
existing electrical/qualification checks.

[JLCPCB coupon promotion](https://jlcpcb.com/news/free-assembly-1-6-layer-pcb-discount-8-20-layer-pcba),
[assembly charges](https://jlcpcb.com/help/article/pcb-assembly-price),
[Economic single-sided capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities).

## TME special orders and Quick Buy — 2026-10-12

The user confirms that the zero-stock decoder listing permits addition to
the basket as a special order and is willing to wait if the delay is acceptable.
Zero stock is therefore not by itself a reason to exclude TME. The required
part remains 74HCT238PW,118 in TSSOP16; check the actual lead time, purchase
minimum/multiple and price in the basket before committing. The earlier
2,500-piece multiple came from an older listing, not a confirmed current
small-quantity quote. No delivery date or small-quantity acceptance was
established by the agent.

TME Quick Buy accepts TXT, XLS and CSV with product symbol and quantity
separated by comma, semicolon, tab or space, one product per line. It also
accepts a pasted list. Use TME symbols rather than LCSC C-codes. The existing
factory BOM/CPL CSV is not the Quick Buy purchase format.

Prepared ignored `build/purchase-v4/tme/QUICK-BUY-EXACT-START.csv` contains
six exact-part lookups, including the special-order decoder, two buffers,
TPS2553, Molex header and 100 nF capacitor. Quantities preserve the user's
adjusted original cart. It is a **partial price/availability lookup**, not a
complete buying list. `BOM-MAPPING-REVIEW.csv` records all nineteen original
cart lines and marks remaining sourcing work. No stock-covered MCUs/LEDs or
unreviewed substitutions were added; nothing was uploaded to TME or ordered.

TME's published domestic shipping policy says it pays the cost of later
backorder shipments when an order is delivered in batches. Its order guide
allows the customer to choose complete delivery or delivery as stock arrives.

Sources: [Quick Buy file format](https://www.tme.eu/si/en/help/1753/uploading-products-from-a-file/),
[pasting a list](https://www.tme.eu/si/en/help/1732/pasting-a-list-of-products/),
[order guide](https://www.tme.eu/pl/how-to-buy/7429/zamowienia-1/),
[domestic delivery and backorder shipping](https://www.tme.eu/pl/how-to-buy/7428/Sposob-i-koszty-transportu/).
