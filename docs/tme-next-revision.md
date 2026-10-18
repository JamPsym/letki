# Wstępne badanie kolejnej rewizji z częściami TME

Stan na 2026-10-12: propozycja do dalszego projektu, bez zmian w CAD v4.
CH32V003F4P6 i pomarańczowe XL-2012UOC pozostają z zapasu użytkownika.
Wymaganie TME obejmuje **nowe zakupy pozostałych komponentów**. SWIO, USART,
I2C, jasność gamma i animacje pozostają wymaganiami; migracja na STM32 nie jest
potrzebna do tej partii prototypów.

Najmniej zmian wymaga zachowanie układu matrycy z v4 i dobór części TME:
HCT238 w SO16, obecny bufor HCT244, tranzystory DMG2302UK, regulator MIC5504
oraz prostszy bufor UART 74LVC2G34. To sensowny punkt wyjścia, ale lokalne
MOSFET-y i minima zakupowe rezystorów mogą podnieść koszt części. Jedna
krajowa przesyłka nie oznacza automatycznie najniższej ceny całego urządzenia.

## Założenia i zapas

Zachowujemy 8×8 LED-ów, rytm 5,08 mm, cztery warstwy, symetryczne siedem
otworów po bokach, jednakowe druty łączące płytki, otwory montażowe i drukowane
elementy optyczne. Docelowo warto utrzymać obrys 40,64×49,27 mm; większe
obudowy i nowe przyciski wymagają sprawdzenia rozmieszczenia. Jest to zadanie
następnego projektu PCB, nie ustalone dopasowanie do obecnej płytki.

W [ewidencji zapasu](../config/parts-stock.csv), po konserwatywnym odliczeniu
zużycia i rezerwy na drugi v3, pozostaje 46 MCU i 872 LED-y. Pięć płytek
potrzebuje 5 MCU i 320 LED-ów. Dwadzieścia potrzebowałoby 20 MCU i 1280 LED-ów:
**brakuje 408 LED-ów**. Zapas wystarcza na 13 kompletnych matryc. Porównanie
20 płytek poniżej obejmuje pozostałą elektronikę, a nie zakup brakujących
LED-ów. Nie przypisujemy automatycznie innych starych części do nowego BOM-u.

Oba kosztorysy zakładają jeden USB head. Liczba kupowanych płytek nie określa
dozwolonej długości łańcucha; dwadzieścia płytek nie zostało zakwalifikowane
do pracy z jednym zasilaczem 1 A.

## Części do wariantu z osobnymi MOSFET-ami

Ceny poniżej są netto z publicznych stron TME. Odczyty zawierają kopie stron
od jednego dnia do kilku miesięcy; stan magazynowy i terminy wymagają
aktualnej wyceny koszyka. „0” dopuszcza badanie zamówienia specjalnego, jeśli
TME potwierdzi ilość, cenę i termin. Niektóre strony jednocześnie pokazują
zapas i oznaczenie „trudno dostępny”; zapis takiej strony nie jest rezerwacją.

| Funkcja | Kandydat i źródło TME | Ilość | Wpływ na projekt |
| --- | --- | ---: | --- |
| MCU i LED-y | CH32V003F4P6 oraz XL-2012UOC z zapasu | 1 + 64 na płytkę | Zachować; koszt nowych zakupów dla pięciu płytek wynosi 0 |
| Dekoder kolumn | [74HCT238D,653](https://www.tme.eu/pl/katalog/dekodery-multipleksery-przelaczniki_113424/?params=2611%3A1494630_technologia%3Attl), symbol `74HCT238D.653` | 1 na płytkę | SO16 zamiast TSSOP16; nowe pady i routing. Odczyt katalogu: 2169 szt., minimum 1; 0,57 USD przy 1+, 0,40 USD przy 10+ |
| Bufor wierszy | [SN74HCT244PWR](https://www.tme.eu/en/details/sn74hct244pwr/buffers-transceivers-drivers/texas-instruments/) | 1 na płytkę | Obecna funkcja i TSSOP20. Odczyt: 2919 szt.; 0,52 USD przy 1+, 0,37 USD przy 10+ |
| Bufor UART | [74LVC2G34GW,125](https://www.tme.eu/no/en/details/74lvc2g34gw.125/buffers-transceivers-drivers/nexperia/74lvc2g34gw-125/), symbol `74LVC2G34GW.125` | 1 na płytkę | Nowa obudowa sześciopinowa SOT363-2. Dwa bufory bez OE; odczyt: 931 szt., 0,13 USD przy 1+/10+ |
| Tranzystory kolumn | [DMG2302UK-7](https://www.tme.eu/pl/details/dmg2302uk-7/tranzystory-z-kanalem-n-smd/diodes-incorporated/) | 8 na płytkę | SOT23, funkcje pinów odpowiadają obecnej topologii. Odczyt: 7155 szt.; 0,61 zł przy 25+, 0,53 zł przy 100+ |
| Regulator 3,3 V | [MIC5504-3.3YM5-TR](https://www.tme.eu/pl/details/mic5504-3.3ym5-tr/stabilizatory-napiecia-nieregulowane-ldo/microchip-technology/) | 1 na płytkę | SOT23-5 zamiast SOT23-3; EN połączyć z wejściem. Odczyt: 8300 szt.; 0,56 zł przy 1+, 0,45 zł przy 25+ |
| Odsprzęganie | [CC0603KRX7R9BB104](https://www.tme.eu/pl/details/cc0603krx7r9bb104/kondensatory-mlcc-smd/yageo/) | 4 na płytkę + 1 na head | Obecne 100 nF, 0603, 50 V, X7R. 0,16 zł przy 10+, 0,08 zł przy 100+ |
| Kondensatory LDO | [CL21B475KAFNNNE](https://www.tme.eu/pl/details/cl21b475kafnnne/kondensatory-mlcc-smd/samsung/) | 2 na płytkę | 4,7 µF, 25 V, X7R, 0805; inny MPN niż v4. Odczyt: 64111 szt., minimum 10; 1,20 zł przy 10+, 0,56 zł przy 100+ |
| Przyciski | [TACT-64K-F](https://www.tme.eu/pl/details/tact-64k-f/mikroprzelaczniki-tact/ninigi/) | 2 na płytkę | THT 6×6 mm; nowe otwory poza polem LED i dostęp przez obudowę. Odczyt: 4740 szt., minimum/wielokrotność 10; 0,33 zł przy 10+ |
| Gniazdo USB-C | [USB4216-03-A](https://www.tme.eu/pl/details/usb4216-03-a/zlacza-usb-i-ieee1394/gct/) | 1 na head | Nowy footprint według GCT, nie podmiana HRO. Odczyt: 1374 szt.; 2,25 zł przy 1+ |
| Ogranicznik USB | [TPS2553DBVR](https://www.tme.eu/pl/details/tps2553dbvr/power-switches-uklady-scalone/texas-instruments/) | 1 na head | Zachować układ z v4. Odczyt: 5 szt.; 3,97 zł przy 1+. Wersja `-1` nie jest automatycznym zamiennikiem |
| SWIO | [Molex 530470310](https://www.tme.eu/pl/details/mx-53047-0310/zlacza-sygnalowe-raster-1-25mm/molex/53047-0310/), symbol `MX-53047-0310` | opcjonalnie 1 na płytkę | Zachować pionowy PicoBlade i równoległe duże pady. 0,69 zł przy 1+, 0,60 zł przy 10+ |

TI CD74HCT238M96 jest drugim kandydatem na dekoder SOIC16; jego ofertę wskazał
użytkownik. Nie należy mieszać obudów SOIC i TSSOP na jednym footprintcie.
Nowa rewizja może przyjąć SOIC, podczas gdy obecny v4 wymaga TSSOP16.

## Rezystory i ilości do magazynków

Rodzina Royalohm z symbolami `SMD...` pozwala kupować odcinki taśmy po 100
elementów zamiast pełnych rolek po 5000. Wartości pozostają jak w v4.
Rezystory wierszy mają 1,2 kΩ, 1%, 125 mW i 100 ppm/°C. Pozostaje zapas
mocy wobec około 24 mW obliczonych dla zwarcia LED przy 5,25 V i −3% R.

| Symbol TME | Na płytkę / head | Próg 100 szt. netto | Próg 1000 szt. netto |
| --- | --- | ---: | ---: |
| [SMD0805-1K2-1%](https://www.tme.eu/pl/details/smd0805-1k2-1%25/rezystory-smd/royalohm/0805s8f1201t5e/) | 8 / 0 | 0,07 zł | 0,02 zł |
| [SMD0805-100K-1%](https://www.tme.eu/pl/details/smd0805-100k-1%25/rezystory-smd/royalohm/0805s8f1003t5e/) | 2 / 0 | 0,06 zł | 0,02 zł |
| [SMD0805-2K2-1%](https://www.tme.eu/pl/details/smd0805-2k2-1%25/rezystory-smd/royalohm/0805s8f2201t5e/) | 2 / 0 | 0,06 zł | 0,02 zł |
| [SMD0603-100K-1%](https://www.tme.eu/pl/details/smd0603-100k-1%25/rezystory-smd/royalohm/0603saf1003t5e/) | 13 / 0 | 0,04 zł | 0,01 zł |
| [SMD0603-2K2-1%](https://www.tme.eu/pl/details/smd0603-2k2-1%25/rezystory-smd/royalohm/0603saf2201t5e/) | 2 / 0 | 0,03 zł | 0,01 zł |
| [SMD0603-5K1-1%](https://www.tme.eu/pl/details/smd0603-5k1-1%25/rezystory-smd/royalohm/0603saf5101t5e/) | 0 / 2 | 0,04 zł | 0,01 zł |
| [SMD0603-33K-1%](https://www.tme.eu/pl/details/smd0603-33k-1%25/rezystory-smd/royalohm/0603saf3302t5e/) | 0 / 1 | 0,05 zł | 0,01 zł |

Publikowane ceny są zaokrąglone do grosza; szczególnie próg 1000 szt. należy
porównywać według wartości całej linii w koszyku. Wyświetlenie 0,00 zł nie
oznacza darmowych części. Według powyższego modelu dla 20 płytek 1000 szt.
100 kΩ/0603 kosztuje mniej niż wymagane 300 szt. po zaokrągleniu do paczek.
Dla 1,2 kΩ/0805 zwiększenie z 200 do 1000 szt. dodaje około 6 zł netto.
To pasuje do preferencji użytkownika dotyczącej zapasu w magazynkach, ale
nie narzuca kupowania 1000 sztuk każdego rodzaju.

## Weryfikacja elektryczna kandydatów

HCT238 zachowuje wybór jednego wyjścia stanem wysokim i progi TTL przy 5 V.
HC138 i LVC138 nie zastępują go w tej topologii. SOIC nie zmienia funkcji
dekodera, lecz wymaga nowego footprintu. Rezystory 1,2 kΩ pozostają punktem
wyjścia; przejście do 1 kΩ ponownie wymaga sprawdzenia całego budżetu prądu
HCT244, w tym dodatkowego poboru wejść. [Nexperia HCT238](https://assets.nexperia.com/documents/data-sheet/74HC_HCT238.pdf),
[dotychczasowy budżet](v4-design.md).

DMG2302UK ma piny 1 G, 2 S, 3 D. Producent podaje maksymalnie 120 mΩ przy
VGS=2,5 V i 25°C oraz typowy ładunek bramki 1,4 nC przy 4,5 V. Dla
obliczeniowego prądu kolumny 36,09 mA daje to około 4,3 mV spadku przy tym
założeniu rezystancji. To nie jest pomiar ani gwarancja dla całego zakresu
temperatur. Bramki obecnego v4 steruje bezpośrednio dekoder; jego netlist
nie ma ośmiu osobnych rezystorów bramka–GND. Zachować osiem pull-downów
wejść bufora wierszy i trzy pull-downy adresów oraz sprawdzić przełączanie
i wygaszanie przy PWM. Ta część jest mocniejszym kandydatem niż dobór dowolnego
BSS138 wyłącznie według nazwy. [Dokumentacja Diodes](https://www.diodes.com/datasheet/download/DMG2302UK.pdf).

MIC5504 pracuje z wejściem 2,5–5,5 V i wymaga co najmniej 1 µF efektywnej
pojemności wyjściowej. W SOT23-5 ma 1 IN, 2 GND, 3 EN, 4 NC, 5 OUT;
EN trzeba połączyć z IN. Wyjście ma rozładowanie przy wyłączeniu i nie daje
gwarancji bezpiecznego zasilania od strony wyjścia. SWIO nadal używa PD1,
a pin REF złącza pozostaje punktem odniesienia 3,3 V, nie wejściem zasilania
z WCH-Linka. [Microchip DS20006006C](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MIC5501-02-03-04-300mA-Single-Output-LDO-in-Small-Packages-DS20006006.pdf).

74LVC2G34 zastępuje funkcję zawsze włączonego bufora UART z v4. Jego piny:
1 A1, 2 GND, 3 A2, 4 Y2, 5 VCC, 6 Y1. Przy zasilaniu 2,7–3,6 V próg
VIH wynosi 2 V; wejścia tolerują 5,5 V i układ ma Ioff. Zachować buforowanie,
spoczynkowe pull-upy i zbadać czas narastania/opadania z rezystorami
szeregowymi i rzeczywistym przewodem. Ioff jednego bufora nie kwalifikuje
całego łańcucha do podłączania pod napięciem. [Dokumentacja Nexperia](https://assets.nexperia.com/documents/data-sheet/74LVC2G34.pdf).

Samsung podaje [Mass Production dla CL21B475KAFNNNE](https://product.samsungsem.com/mlcc/CL21B475KAFNNN.do).
Krzywe DC bias obecnego samochodowego CL21B475KAB6PNE nie odnoszą się
automatycznie do tej części. Wariant oszczędnościowy to
[Murata GCM21BR71E225KA73K](https://www.tme.eu/pl/details/gcm21br71e225ka73k/kondensatory-mlcc-smd/murata/),
2,2 µF/25 V/X7R/0805: odczyt 4047 szt., 0,25 zł przy 10+ i 0,17 zł przy 50+.
Po uwzględnieniu −10% tolerancji i −15% temperatury pozostaje 1,683 µF przed
DC bias i starzeniem. Utrata przez bias większa niż około 40,6% naruszyłaby
przyjęty próg 1 µF. Dlatego wariant 2,2 µF wymaga własnej krzywej oraz testu
stabilności LDO; nie został włączony do bazowego kosztorysu.

Gniazdo GCT wymaga nowego rysunku padów, kotew i odległości od krawędzi.
Podłączyć tylko zasilanie i dwa niezależne rezystory CC 5,1 kΩ; USB data i
PD nie są wymagane. Pozostawić TPS2553 i 33 kΩ z v4, dopóki tańszy
ogranicznik nie przejdzie porównania. TME oferuje także AP2553W6-7, ale
sama obecność w katalogu nie rozstrzyga jego aktualnej ceny i dostawy.

## Porównanie kosztów pięciu i dwudziestu płytek

Model wykorzystuje minima, wielokrotności i dodatnie zaokrąglone progi cenowe
z [danych badania](../config/tme-next-revision.json). Wybiera najniższą wartość
zakupu z rozpatrywanych progów. Nie zwiększa ilości do pełnego magazynka,
jeśli nie obniża to wartości linii. Obejmuje jeden USB head i opcjonalne
złącze SWIO na każdej płytce; nie obejmuje kabla, PCB, montażu, śrub,
VAT ani przesyłki. MCU i LED-y z zapasu nie są nowym zakupem.

Trzy układy logiczne udało się wycenić w USD, resztę w PLN. Waluty pozostają
rozdzielone: sumy nie są końcową wyceną polskiego koszyka TME.

| Składnik nowych zakupów netto | 5 płytek | 20 płytek |
| --- | ---: | ---: |
| Części wycenione w PLN | 90,53 zł | 231,42 zł |
| Dekoder, HCT244 i bufor UART wycenione w USD | 6,10 USD | 18,00 USD |
| W tym osiem MOSFET-ów na płytkę | 24,40 zł | 84,80 zł |
| W tym dwie pojemności 4,7 µF na płytkę | 12,00 zł | 48,00 zł |
| Brakujące LED-y poza powyższymi sumami | 0 | 408 |

Wiersze „w tym” są częściami sumy PLN, nie dodatkowymi kosztami. Szczegóły
zakupów są w `build/hardware/tme-revision/model-5-tiles.csv` i
`model-20-tiles.csv`. To model przyszłej rewizji, nie lista zamienników do
zamówienia obecnego v4. Przypisania dla 18 typów części zawiera
[arkusz kandydatów](tme-next-revision-parts.csv).

Zamiana kondensatorów na kwalifikowane Murata 2,2 µF zmniejszyłaby ich
modelowy zakup do 2,50 zł dla pięciu albo 8,50 zł dla dwudziestu płytek
(50 sztuk jest tańsze niż 40 po wcześniejszym progu). Oszczędność wynosiłaby
9,50 zł / 39,50 zł netto, pod warunkiem spełnienia wymagań pojemności i LDO.

[Standardowa dostawa krajowa TME](https://www.tme.eu/pl/how-to-buy/7428/Sposob-i-koszty-transportu/)
kosztuje 17,10 zł brutto do 30 kg. Według tej samej polityki TME pokrywa
koszt późniejszego dosłania zaległych części. Dla zamówienia specjalnego
nadal potrzebne są zaakceptowane minimum i termin.

## Wariant z jednym układem zamiast ośmiu tranzystorów

[HTC ULN2803AD](https://www.tme.eu/pl/details/uln2803ad-tt/drivery-uklady-scalone/taejin-technology-htc-korea/uln2803ad/),
symbol TME `ULN2803AD-TT`, zawiera osiem stopni Darlingtona w SOP18.
Odczyt: 14443 szt., 3,73 zł przy 1+ i 2,98 zł przy 10+. Mógłby zastąpić
osiem MOSFET-ów. Pull-downy wejść bufora wierszy nadal pozostają potrzebne;
nie zaliczamy ich do oszczędności tego wariantu.
HCT238 nadal wybierałby jedno wejście stanem wysokim. Układ pozostawia
osobne sterowanie PWM ośmioma wierszami, potrzebne do obecnych gradientów.

Sam koszt stopni kolumnowych spadałby z 24,40 do 18,65 zł dla pięciu płytek
i z 84,80 do 59,60 zł dla dwudziestu. To 5,75 zł / 25,20 zł oszczędności
netto przed zmianami rezystorów. Nie należy traktować limitu 500 mA na
kanał jako zalecanego prądu LED.

Darlington ma większy spadek napięcia. Producent podaje typowo 0,9 V,
maksymalnie 1,1 V przy 100 mA i określonym prądzie wejścia; nie jest to
pomiar przy naszym prądzie kolumny. Ilustracyjny spadek 0,9 V na tle
5 V − 2,1 V LED obniża dostępne napięcie na rezystorze o około 31%.
Rzeczywista jasność i pobór wejścia muszą zostać porównane na prototypie.
Nie obniżać automatycznie rezystorów do 1 kΩ, żeby odzyskać jasność.
[Dokumentacja HTC](https://www.tme.eu/Document/e6466bb3f5fa857877115a7fdb7597cc/ULN2803A.pdf).

## Pozostałe kierunki i koszt dostępu SWIO

Zmiana topologii na HCT138, P-MOSFET-y źródłowe kolumn i odwracający bufor
wierszy HCT240 pozwoliłaby korzystać z innej rodziny dekoderów. Wymaga
odwrócenia połączeń anoda/katoda wszystkich LED-ów, nowych pull-upów bramek
i ponownego sprawdzenia blankingu. Nie jest to podmiana układu na v4.
Własne HC138 nie rozwiązują automatycznie progów wejściowych 3,3 V → 5 V.
Na tym etapie brak wykazanej przewagi ceny i dostawy uzasadniającej taki
zakres zmian. [HCT138](https://assets.nexperia.com/documents/data-sheet/74HC_HCT138.pdf),
[HCT240](https://assets.nexperia.com/documents/data-sheet/74HC_HCT240.pdf).

Rejestr 595 mógłby zastąpić równoległy bufor wierszy, a osiem kolumn
otrzymać sterowanie bezpośrednio z MCU. Budżet pinów jest możliwy:
3 do rejestru, 8 do kolumn, 2 UART, 2 I2C, 2 przyciski i 1 SWIO.
Zwykły HC595 przy 5 V nie zapewnia odpowiednich progów; potrzebny jest
HCT/AHCT i ponowne sprawdzenie prądu wszystkich ośmiu wyjść. Statyczny bajt
wierszy plus PWM kolumny zachowuje jasność globalną, ale **nie zachowuje
obecnego niezależnego PWM pikseli** bez nowego skanowania bitplanów.
Koszt ISR, UART i 2 KiB RAM wymagałby osobnego eksperymentu firmware.
Znaleziony SN74AHCT595PWR w TME miał stan 0, więc nie ma jeszcze podstaw
do uznania tego za lepszy wariant prototypowy.
[Rejestr HCT595](https://assets.nexperia.com/documents/data-sheet/74HC_HCT595.pdf),
[oferta AHCT595](https://www.tme.eu/ng/en/details/sn74ahct595pwr/shift-registers/texas-instruments/).

Gotowy [przewód Molex 151340302](https://www.tme.eu/pl/details/mx-15134-0302/zespoly-kablowe-przewod-plytka/molex/151340302/)
ma 3 piny PicoBlade i długość 150 mm; odczytana cena jednej sztuki wynosiła
24,50 zł netto. To akcesorium wielokrotnego użytku, nie koszt każdej płytki.
Nie włączono go do sum części. Tańszy adapter można oprzeć na obudowie
PicoBlade i przewodach ze stykami, ale wymaga oddzielnego doboru części i
sprawdzenia kolejności REF/SWIO/GND. Duże pady SWIO pozostają bezpłatnym
punktem podłączenia podczas pierwszych prób.

## Zalecany następny etap

Pierwszy projekt kolejnej rewizji warto oprzeć na wariancie z MOSFET-ami:
zachowuje polaryzację matrycy, osiem kanałów PWM i obecne funkcje firmware.
Największe zmiany dotyczą obudowy dekodera, regulatora, UART, przycisków
i gniazda USB. ULN2803 pozostaje próbą oszczędnościową do porównania jasności.

Przed rysowaniem trzeba uzyskać aktualny koszyk TME, w szczególności dla
dekodera i przycisków, oraz rozstrzygnąć kondensator 4,7/2,2 µF. Następnie
zweryfikować footprinty z rysunkami producentów, rozmieszczenie poza polem
LED, prześwit drukowanej obudowy, ERC/DRC i zgodność schematu z PCB.
Pierwszy egzemplarz ma sprawdzić stabilność 3,3 V, prąd i temperaturę,
blanking/PWM, USART, I2C oraz spadki napięcia i ogranicznik USB.

Zakres tego badania kończy się na propozycji i kosztach. CAD v4, jego Gerbery,
bieżący firmware i koszyki zakupowe pozostają bez zmian. Nie wykonano
flashowania, zamówienia ani pomiarów nowej rewizji.
