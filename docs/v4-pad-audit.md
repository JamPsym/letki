# V4 / v4.1 pad and manufacturer drawing audit

Audited 2026-10-14: retained `hw/ledkiv4/` and active `hw/ledkiv4.1/`, including
the purchased AP22653W6-7 and RC0603FR-075K1L substitutions. No CAD, frozen
purchase package, stock count, firmware or hardware was changed.

No pin swap, LED polarity reversal, rear-side double reflection or lead-pitch
mismatch was found in the reviewed devices. One mechanical deviation was
hidden by an incorrect USB-edge assertion. Several generic copper patterns
also differ from manufacturer recommendations; lead contact is geometrically
plausible, but an exact manufacturer land-pattern match is not established.

## GCT USB4105: confirmed edge discrepancy

The v4.1 connector's manufacturer PCB-edge line is at local y=+3.675 mm.
The text reading `PCB Edge` is anchored at +3.1 mm; that anchor was incorrectly
used by the previous checker and design brief.

| Reference, in front-view PCB coordinates | y, mm |
| --- | ---: |
| Connector origin | 46.170 |
| Locator centres | 43.565 |
| Front shell-slot centres | 47.245 |
| Manufacturer edge: slot centre + 2.60 mm | 49.845 |
| Actual PCB edge | 49.270 |
| Actual edge minus manufacturer edge | **−0.575** |

The independent locator calculation is 43.565 + 3.68 + 2.60 = 49.845 mm.
The native footprint's drawn edge agrees; its label position does not define
an edge. The connector shell nominally overhangs the actual PCB by 0.575 mm.
[GCT product drawing, Rev B3](https://www.tme.eu/Document/1f050d2dc938bcf56fe5f4a6438948a1/USB4105%2B-%2BProduct%2BDrawing.pdf).

The front slot drill ends at y=47.945 mm and its copper at 48.145 mm,
leaving 1.325 mm substrate and 1.125 mm copper-to-edge clearance. Neither is
cut by the actual edge. This is a real placement deviation, without a
demonstrated impossible mounting fit. No recorded acceptance of this overhang
or physical plug/carrier/retention trial was found.

The contact centres, 0.5 mm pitch, locator positions/diameters and four shell
slots agree with the drawing. Four GND lands are deliberately shortened from
1.15 to 1.13 mm to retain the existing NPTH copper clearance. The GF-A shell
stakes are 0.95 mm long on a 1.6 mm PCB; component-side soldering and barrel
fill still require qualification.

`check_v4_geometry.py` now uses the real drawing reference, completes its
other checks, records the offset and exits **1 for v4.1**. V4.1 package
generation therefore stops at this finding. Resolve it through a reviewed
placement correction or explicit engineering acceptance supported by fit
testing. The previously saved cart/files were not regenerated. Their earlier
claim of complete geometry agreement is superseded by this audit.

V4's HRO TYPE-C-31-M-12 locator-to-edge distance is 5.79 mm and matches its
current board. Its 0.46 mm nominal shell overhang is a different documented
manufacturer geometry; it does not justify GCT's offset automatically.

## Pin identities and revision changes

Pad numbers below are KiCad numbers. PCB coordinates are viewed from the
front; rear component diagrams were compared after exactly one reflection.

| Position | V4 / v4.1 check |
| --- | --- |
| U1, CH32V003F4P6 | TSSOP20, 0.65 mm pitch; VSS 7, VDD 9, PD1/SWIO 18, PD5/TX 2, PD6/RX 3 and row/decoder GPIO maps agree with the retained WCH drawing. |
| U2, HCT238 | PW/TSSOP16 changed to D/SO16: pitches 0.65 / 1.27 mm, package-specific lands updated. A0/A1/A2 1/2/3; enables 4/5/6; GND 8; VCC 16; outputs 15/14/13/12/11/10/9/7. |
| U3, SN74HCT244PWR | TSSOP20, 0.65 mm; enables 1/19 to GND, GND 10, VCC 20, eight input/output pairs agree. |
| U4, UART | V4 LVC2G125/DCU: pins 1/7 enable low, 2 TX input, 6 TX output, 5 RX input, 3 RX output, 4 GND, 8 VCC. V4.1 LVC2G34/GW: 1 TX input, 6 TX output, 3 RX input, 4 RX output, 2 GND, 5 VCC. Correct rear orientation. |
| U5, native TPS2553DBVR | 1 IN, 2 GND, 3 active-high EN, 4 FAULT unconnected, 5 ILIM, 6 OUT; 0.95 mm pitch. |
| U5, purchased AP22653W6-7 | Same six functions and active-high EN; W6 is leaded SOT26 Type A1, with no exposed pad. The differently numbered DFN and AP22653A were not substituted. |
| U6, regulator | V4 ME6206 **M3**: 1 GND, 2 OUT, 3 IN. V4.1 MIC5504/YM5: 1 IN, 2 GND, 3 EN, 4 NC, 5 OUT. Both maps correct; these packages are not interchangeable. |
| Q1–Q8 | BSS138BK changed to DMG2302UK-7; both are 1 gate, 2 source/GND, 3 drain/cathode column. |
| D1–D64 | XL-2012UOC: pad 1 cathode on the left, pad 2 anode on the right; consistent with the manufacturer mark and circuit. |
| SW1/SW2 | XUNPU and ALPS lands were changed to their respective drawings. Same-row physical contacts share a logical pad number; a press connects the two rows. No permanently closed button net. |
| J2, Molex 530470310 | 1 REF/3V3, 2 SWIO, 3 GND; 1.25 mm pitch. |

The current GW package is called SOT363-2/TSSOP6 by Nexperia. The local
`SOT-363_SC-70-6` name is loose metadata, but its 0.65 mm pitch and nominal
body dimensions agree. ME6206's M3 drawing is on PDF page 12; the smaller
X-package drawing on page 14 must not be used for it.
[Nexperia LVC2G34](https://assets.nexperia.com/documents/data-sheet/74LVC2G34.pdf),
[MicrOne manufacturer-authored V20, distributor mirror](https://img.ichunt.com/doc/pdf/cms/201808/29/f71d85f01883a662ed366ee77b8e7c47.pdf).

## Copper compared with recommended lands

Dimensions are millimetres, copper length along the lead × transverse width.
Opposing row distance means pad-centre distance. Paste and mask dimensions
were not treated as copper. Generic hand-solder lands are not automatically
incorrect because they differ from a reflow example.

| Device | Actual PCB | Manufacturer comparison / consequence |
| --- | --- | --- |
| CH32V003, both | 1.475 × 0.40; rows 5.725; pitch 0.65 | WCH gives a package drawing, not an exact recommended land pattern. Nominal leads overlap. Its broad drawing tolerance note needs assembly allowance review; do not infer full tolerance qualification. |
| HCT238PW, v4 | 1.475 × 0.40; rows 5.725 | Outer lead-axis copper span 7.20 agrees with the Nexperia reflow drawing; inward extension and transverse/end-pad details differ. |
| HCT238D, v4.1 | 1.95 × 0.60; rows 4.95 | Nexperia example: length 1.75, ordinary width 0.70 / end width 0.80, rows 5.65. Actual outer span 6.90 versus 7.40; still extends 0.35 past centred maximum-span leads. |
| HCT244, both | 1.475 × 0.40; rows 5.725 | TI example 1.50 × 0.45, rows 5.80; actual pads are 0.05 narrower and outer edge 0.05 inward per side. |
| LVC2G125, v4 | 1.25 × 0.35; rows 2.80 | TI example 0.85 × 0.30, rows 3.10. Actual pads extend farther inward; correct 0.50 pitch. |
| LVC2G34, v4.1 | 1.025 × 0.35; rows 1.675 | Nexperia copper 0.75 × 0.40, rows 1.95. Same outer span 2.70, extra inward copper, narrower width. |
| TPS2553, both | 1.325 × 0.60; rows 2.275 | TI example 1.10 × 0.60, rows 2.60. Actual outer span 3.60 versus 3.70. |
| AP22653, purchased v4.1 | Same U5 lands above | Diodes suggests 0.90 × 0.70, rows 2.50. Actual width 0.10 narrower; centred widest lead retains 0.05 copper per side. Compatible pin geometry, without exact land-pattern or solder-process qualification. |
| MIC5504, v4.1 | 1.325 × 0.60; rows 2.275 | Microchip suggests 1.10 × 0.60, rows 2.80. Actual outer edge is **0.15 inward per side**; centred lead tips remain covered. |
| ME6206 M3, v4 | 1.475 × 0.60; rows 1.875 | Maximum terminal span 3.10 versus actual copper span 3.35: centred toe margin only 0.125. Generic Fab body width 1.3 is smaller than M3's 1.5–1.8. Copper reaches the leads; body drawing is inaccurate. |
| BSS138BK / DMG2302UK | 1.475 × 0.60; rows 1.875; paired pitch 1.90 | Gate/source/drain and lead envelopes agree; no recommended identical copper pattern established. |
| XL-2012UOC | 0.975 × 1.40; centres 1.875 | Manufacturer example 0.60 × 1.20; centres 1.60. Larger actual copper, correct polarity. |
| XUNPU button, v4 | 1.25 × 1.20; x ±2.175, y ±0.95 | Land dimensions and centre offsets match its drawing. |
| ALPS button, v4.1 | 1.05 × 0.65; x ±2.075, y ±1.075 | Land dimensions and centre offsets match its drawing No. 1. |
| Molex J2 | 0.60 drilled holes, 1.25 pitch | Drawing requests 0.50 ±0.05 holes on 0.8 PCB; current 0.60 holes / 1.6 PCB are documented prototype adaptations. Insertion, protrusion and hole fill remain unqualified. |
| Samsung C8/C9 | 1.00 × 1.45; gap 0.90 | V4 KAB6PNE ±0.25-body table includes these lands. V4.1 KAFNNNE ±0.10-body example is slightly smaller; actual width is 0.10 above its tabulated upper recommendation. |
| 0603 resistors/caps; 0805 row resistors | Package identities agree | Purchased Yageo 0603 resistor exact-part PDF retained. Royalohm reference is a generic family document, not an exact S-series electrical qualification. |

Centred toe/side margins above exclude component placement error, lead
coplanarity, manufacturing tolerances, solder-mask registration and solder
volume. They are geometric deductions, not measured joint quality.

Sources and immutable copies are indexed in the
[shared datasheet archive](../../electronics/datasheets/README.md), including
[Nexperia SO16 drawing](https://assets.nexperia.com/documents/package-information/SOT109-1.pdf),
[TI HCT244](https://www.ti.com/lit/ds/symlink/sn74hct244.pdf),
[Diodes AP22653](https://www.diodes.com/datasheet/download/AP22652_AP22653_AP22652A_AP22653A.pdf)
and [Microchip MIC5504](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MIC5501-02-03-04-300mA-Single-Output-LDO-in-Small-Packages-DS20006006.pdf).
Manufacturer-authored distributor mirrors are identified. WCH copies are the
retained v1.3/v1.9 documents; latest revision is not claimed.

## Verification and limits

Raw evidence: `build/hardware/pad-audit-20261014/`.

- Native PCB pads match the local footprint geometry on **135 footprints per
  board**, after accounting for the original library side and PCB rotation.
- Independently exported schematic nets and footprint IDs agree with **361
  numbered physical pads per board**, including duplicate switch contacts.
  No missing schematic footprint or pad/net mismatch was found.
- Native v4.1 DRC with absolute paths and schematic parity: zero violations,
  zero open connections, zero parity findings, zero ignored checks.
- ERC: zero findings on both boards; three documented style/simulation defaults
  remain ignored as before. Circuit checks passed on both.
- Corrected geometry checker: v4 passes; v4.1 reports the USB edge deviation
  and exits 1. Other containment/contact/button/LED/label checks completed.
- V4's initial relative-path DRC produced a zero-finding report, but logged an
  absolute-path assertion while loading its schematic. Absolute-path reruns
  crashed KiCad 10.0.7, including attempts without refill or without parity.
  That native parity run is not claimed as successful. The independent
  schematic-to-pad comparison above passed; failed logs are preserved.
- SHA-256 comparison preserved all **28 v4 / 33 v4.1** CAD, project, rule,
  symbol and footprint source files. Five canonical inventory records also
  retained their pre-archive hashes.

No physical fit, current, waveform, optical or production-process validation
was performed. Documentation and the USB checker were corrected; board
redesign and changes to frozen fabrication files remain a separate task.
