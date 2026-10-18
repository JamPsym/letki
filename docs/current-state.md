# Stan projektu Letki

Current v3 firmware milestone: [five-board UART display platform R3](milestones/v3-general-r3-20261017.txt), verified 2026-10-17.
Source/image/evidence recovery snapshot and checksums are recorded there.

Latest parts commitments (2026-10-17): reservations now cover 5 v4.1,
5 v3.1 and 15 v3.2. See the final inventory section and
[the shared reservation record](../config/board-reservations.json).

Attachment architecture agreed and saved (2026-10-17): independently developed
V007 custom buck and X035 host/PD-supervisor boards, with ESP-12F as the X035's
Wi-Fi peripheral. The buck starts autonomously from USB-C 5 V and maintains
3.3 V after higher-voltage PD negotiation; it powers the controller and the
continuous v3.2 display rail. One converter, optional multiple feeds, provisional
60–65 W charger class; no independent converter outputs paralleled. PC USB is
for data. Tiles implement a host-independent UART/I2C protocol. X035 supervises
V007 over I2C and exposes management to PC; regulation/protection remain local.
User handles initial SWIO setup; later updates use Wi-Fi -> ESP -> X035 -> I2C.
Converter learning/iterations are required; topology and ratings remain open.
Stock remains four confirmed WeAct X035F8 V1.0 boards, one held for prototyping.
See [the agreed architecture](attachments-study-20261017.txt) and
[the proposed loader contract](v3_2-network-update.txt).

Prototype staging update (2026-10-18): [WeAct/X035 bring-up plan](x035-bringup-plan-20261018.txt)
records LinkE/USB setup, a PC-powered USB-UART proxy for the current five v3
tiles, I2C/gyro logging and animations, later fast SPI to ESP, then PD tests.
Hardware has not been prepared; this is planning. ESP SPI supersedes the
earlier UART transport choice.

The media host remains the last planned system component (user clarification2026-10-18);
development can continue after its integration. Work on that component is deferred.
The spare N5095/M2S is the leading reuse candidate; its actual configuration and
Letki performance are unverified. No purchase, OS change or platform port was
requested. The current focus remains the ESP/SPI/X035 bridge and generic tile
interfaces; see the final media-host section of
[the attachment architecture](attachments-study-20261017.txt).

## Drukowane szablony pasty v3 (15 października 2026)

Na prośbę użytkownika przygotowano dwa eksperymentalne szablony PETG 0,20 mm:
przód 128 otworów LED, tył 82 otwory elementów. Tył jest odbity do widoku
od strony elementów. Kontrola ścieżek ekstrudera zachowuje wszystkie otwory
i 32 przegrody padów TSSOP. Zwężenie otworów IC do 0,25 mm pozostawia
przegrody 0,40 mm; rzeczywisty prześwit i nanoszenie pasty wymagają próby.
Oryginalny plik PCB v3 zachowuje hash.

Po potwierdzeniu pustego stołu wysłano zadanie
`letki-v3-stencils-20261015.gcode.3mf` do A1 mini. Drukarka potwierdziła
RUNNING, 5%, przygotowanie/grzanie, właściwy plik, jedną warstwę i brak
błędów/HMS; ukończenie druku nie jest jeszcze potwierdzone. Pierwszą próbę
anulowano przed ekstruzją: domyślne AMS trzeba jawnie wyłączyć przez
`--no-ams`. Poprawione zadanie używa szpuli zewnętrznej.
Szacunek slicera: 19m23s z przygotowaniem,
1,49 g PETG. Ustawienia: dotychczasowa szpula zewnętrzna, dysza 255°C,
stół teksturowany 70°C. Pliki i instrukcja w
[archiwum v3](../archive/hw/ledkiv3/README.md), zapis zadania w
`build/printer/stencils-v3-job.json`. To wydruk pomocniczy do istniejących
płytek v3, bez zmian CAD, firmware, zamówień lub rezerw części.

Letki to modułowy wyświetlacz z matrycami LED 8×8, łączonymi w łańcuch.
Niski koszt CH32V003, LED-ów i połączeń płytka–płytka pozostaje podstawą
projektu. Cztery warstwy i rozmiar PCB dobrano pod korzystną produkcję małych
płytek; dla tej partii wygoda prototypowania i dostępność części mają większą
wagę niż najniższa cena każdego elementu.

Stan zapisany 13 października 2026. Wybrana partia to **pięć prototypów v4.1,
montaż ręczny i części z TME**, z CH32V003 oraz pomarańczowymi LED-ami z półki.
Części TME są zamówione. PCB zapisano w koszyku JLCPCB, a użytkownik przejął
dokończenie zakupu; potwierdzenia opłacenia PCB jeszcze nie ma.

## V3.1 — wspólny projekt, 15 października 2026

Użytkownik zatwierdził ten projekt jako **docelową bazę v3.1**.
[Rejestr wersji](../hw/ledkiv3.1/baseline.json) zapisuje hashe CAD i pakietu;
zamrożona kopia jest w archive/hw/ledkiv3.1-baseline-20261015/.
To przyjęta wersja projektu CAD; kwalifikacja fizyczna pozostaje otwarta.

Rozmieszczenie użytkownika zachowano; Astra ukończyła routing zasilania,
mostki GND, marginesy przelotek i opisy montażowe. 146 footprintów, 974 odcinki
ścieżek i 131 zwykłych przelotek. Wszystkie pozycje części, modele, 350 mapowań
pad–sieć oraz geometria LED-ów/złączy/mocowań są zachowane.

ERC, DRC, przerwy połączeń, parity i ignorowane kontrole: **zero**.
Niezależna kontrola geometrii miedzi potwierdza jedną fizyczną sieć VCC i GND.
Trzy obszary GND na In1 łączą mostki z tyłu; VCC ma jawną magistralę2mm,
szersze doprowadzenia i szynę źródeł PMOS. Opisy77części są z tyłu.
[Ukończenie i ograniczenia](v3_1-completion-20261015.txt).
Eksport prototypowy trafia do hw/ledkiv3.1/exports/prototype/ dopiero po
pełnych kontrolach, kompilacjach i nominalnej mechanice jednej/czterech płytek.
Nie zamawiano, nie wgrywano firmware ani nie zmieniano inwentarza.
Kwalifikacja fizyczna i potwierdzenie procesu/preview producenta nadal oczekują.

[Dobór rezystorów TME przed zmianą PCB](v3_1-resistor-sourcing.txt):
wartości E12; 1k/0603 bramki 5%, 10k/0603 polaryzacja 1% według dostępnych
ofert, 33Ω/0805 nadal 1%. Minimum zakupowe dla pięciu kafelków około 18 zł
brutto łącznie z 1k/0805 UART, bez dostawy. To zaokrąglony szacunek publicznych
cen, nie koszyk ani zamówienie. Wybrane MPN zapisano osobno w
config/v3_1-resistor-sourcing.json; ich naniesienie do CAD/BOM pozostaje
częścią następnej iteracji.

Jedyny aktywny projekt człowieka i agenta to
[hw/ledkiv3.1/ledkiv3_1.kicad_pro](../hw/ledkiv3.1/ledkiv3_1.kicad_pro).
Schemat i PCB mają teraz pojedyncze33Ω z szereguE12 (część1%), bezR58–R65
iJP1/JP2. Pull-upyI2C wybiera obsadzenieR11/R12 na jednym kafelku.
[Zasady współpracy](v3_1-shared-workflow.txt) określają zapis i przeładowanie
edytorów oraz użycieIPC bez nadpisywania niezapisanych zmian użytkownika.
Stara kopia w build/hardware jest historią; nie ma drugiego edytowanego projektu.

Poprzedni sprawdzonyCAD34Ω i zamrożone eksporty zachowano w
archive/hw/ledkiv3.1-checked-34R-20261015/. Aktualny pakiet prototypowy ma własny manifest w exports/prototype/.
Kwalifikacja fizyczna oraz potwierdzenie procesu producenta pozostają otwarte.
ESP-12F i głowica zasilania są odłożone. Firmware źródłowy identyfikuje33R;
nie wgrywano obrazów ani nie zmieniano zamówień, zapasów i rezerw v4.1.

## Zamówienia i inwentarz

| Zapis | Stan |
| --- | --- |
| TME 35700057 | 20 pozycji, 883 elementy; wszystkie oczekują na dostawę. Eksport wskazuje dostępność i wydawanie towaru na magazynie TME. |
| JLCPCB `ledkiv4_1-gerbers_Y8`, `Y8-10656422A` | Koszyk: 5 PCB, 2 USD i szacowana dostawa 1,50 USD przez Global Standard Direct Line. Podatki i końcowe koszty rozstrzyga checkout. |
| [Zapasy na półce](../config/parts-stock.csv) | Szacowany zapas LCSC; po rozliczeniu drugiej v3 rezerwa obejmuje trzy niezmontowane płytki oraz brakujące części dwóch zmontowanych. |
| [Zamówione części](../config/parts-incoming.csv) | Osobny rejestr TME, obecnie `on_hand_confirmed = 0`. Odbiór i ilości należy potwierdzić po dostawie. |

Aktualny wykaz ilości faktycznie zamówionych to
[TME-35700057-ordered.csv](../config/purchase/TME-35700057-ordered.csv).
Jest zapisem istniejącego zamówienia, nie listą do ponownego dodania do koszyka.
[Pochodzenie danych](../config/orders/TME-35700057-source.json) obejmuje nazwę
i hash [zachowanego eksportu TME](../config/orders/TME-35700057-backorders.csv)
oraz podsumowanie ilości. Zwiększono kondensatory 100 nF do
50 sztuk; zamówiono też pięć obudów PicoBlade i 20 styków.

Wartość samych elementów z eksportu wynosi około 174,15 zł brutto. Wcześniej
użytkownik podał około 193 zł za koszyk; eksport nie zawiera dostawy ani
rozliczenia tej różnicy. Nie przypisywać jej automatycznie do konkretnej opłaty.

Po rozliczeniu drugiej v3 i zachowaniu rezerw nadal szacunkowo pozostają
43 MCU i 680 LED-ów dostępnych dla kolejnych projektów przed planowaną v4.1. Pięć v4.1
zużyje 5 MCU i 320 LED-ów. Dla 20 płytek potrzeba 600 dodatkowych LED-ów;
wariant ten nie został zamówiony. Zamówienie części dla 20 płytek nie byłoby
kwalifikacją jednego łańcucha 20 modułów.

## Części do montażu v4.1

Zachowany CAD i pierwotny pakiet produkcyjny mają dwa wcześniejsze numery
części. **Przy montażu należy stosować zamówione zamienniki** zapisane w
[wykazie podmian](../config/purchase/v4.1-assembly-substitutions.json):

| Pozycja | W CAD | Zamówione | Wpływ |
| --- | --- | --- | --- |
| R30, R31 | Royalohm 0603SAF5101T5E | Yageo RC0603FR-075K1L | Nadal 5,1 kΩ, 1%, 0603; te same pola lutownicze. |
| U5, tylko moduł z USB | TI TPS2553DBVR | Diodes AP22653W6-7 | Zgodny układ pinów; istniejące pola pokrywają wyprowadzenia, ale są o 0,10 mm węższe od zalecenia Diodes. R32 pozostaje 33 kΩ, 1%. |

AP22653 ma aktywne wysokim poziomem EN i ograniczanie prądu; nie zamieniać go
na wariant AP22653A. Z 33 kΩ obliczeniowy limit typowy to około 0,758 A;
wzory dopasowane przez producenta dają około 0,654–0,871 A przy przyjętym
3% rozrzucie rezystora. To oszacowanie do prototypu. Rozruch, ograniczanie
prądu przy zwarciu i nagrzewanie trzeba zmierzyć.
[Dokumentacja Diodes](https://www.diodes.com/datasheet/download/AP22652_AP22653_AP22652A_AP22653A.pdf).

Reszta wybranych części: HCT238D w SO16, HCT244, DMG2302UK, bufor UART
74LVC2G34GW z dwoma rezystorami 220 Ω, MIC5504, kondensatory 4,7 µF X7R,
przyciski ALPS i USB-C GCT USB4105-GF-A. Szczegóły pinów i ograniczeń są w
[opisie v4.1](v4_1-design.md). Generator BOM nadal opisuje pierwotną selekcję
CAD; nie zastępuje zapisu faktycznego zamówienia ani powyższego wykazu podmian.

## PCB i archiwa

Pracujemy w `hw/ledkiv4.1/ledkiv4_1.kicad_pro`. Wgrany plik to
`hw/ledkiv4.1/exports/prototype/ledkiv4_1-gerbers.zip`, SHA-256:

```text
31de94b8df6cec8883f9bfa811c942c091c43b7e7b3588ef1af4935bc057a927
```

Wycena: cztery warstwy, 40,64 × 49,27 mm, grubość 1,6 mm, zielona maska,
biały nadruk, HASL z ołowiem, miedź 1 oz na zewnątrz i 0,5 oz wewnątrz.
Otwory do lutowania drutów są zwykłymi PTH; bez kastelacji i metalizacji
krawędzi. Uwagi dla `Plugged` nakazują zachować otwarte otwory lutownicze,
szczeliny USB i NPTH oraz przestrzegać otwarć maski. Potwierdzenie plików
produkcyjnych jest opcjonalne i pozostawiono je wyłączone.

ERC, DRC, otwarte połączenia, zgodność ze schematem oraz niezależna kontrola
pinów przechodzą. [Audyt datasheetów z 14 października](v4-pad-audit.md)
wykrył błąd wcześniejszej kontroli krawędzi USB: rzeczywista krawędź PCB
jest o 0,575 mm cofnięta względem rysunku GCT. Poprawiony checker geometrii
zgłasza tę rozbieżność i blokuje regenerację pakietu do jej rozstrzygnięcia.
Otwory mocujące mieszczą się na PCB; fizycznego dopasowania nie sprawdzono.
Poniższy zamrożony pakiet i źródła CAD pozostały bez zmian.
Źródła odpowiadające wgranemu PCB są zamrożone w
[archiwum v4.1](../archive/hw/ledkiv4.1-purchase-20261013/ARCHIVE.md).
Oryginalne ZIP-y i manifest zachowano dodatkowo w
`build/hardware/v4_1/purchase-snapshot-20261013/`.
Aktualne dokumenty mogą być nowsze od tych w zamrożonym pakiecie; nie
regenerować go przed kolejną zmianą projektu tylko dla aktualizacji notatek.

V4.0 pozostaje w `hw/ledkiv4/`, a wcześniejszy snapshot w
`archive/hw/ledkiv4-pre-tme-20261012/`. Niewybrane listy LCSC, porównania
5/20 płytek i warianty przewodu są w
[archiwum zakupowym](../archive/purchase/20261013-drafts/README.md).
LCSC odłożono po zgłoszonej przez użytkownika wycenie 20 USD dostawy i
20 USD opłaty określonej w checkout jako tariff. Historyczne koszyki zawierały
inne ilości, więc podobny rachunek nie oznaczał podobnej ceny za element.

V4.1 poprawia parametry MOSFET-ów, zapas dla zboczy UART, wygodę lutowania
dekodera oraz dokumentację do iteracji. Zachowuje możliwości i geometrię
matrycy v4.0. Nie wykazano dużej poprawy obrazu ani jednoznacznej przewagi
routingu; ręczne trasy na In1 mają łącznie 127,022 mm.

## Przewód SWIO

Zamówiono `MX-51021-0300` ×5 i `MX-50079-8000` ×20. Do jednego przewodu
potrzebne są obudowa oraz dwa styki, cienka linka 28 AWG i końcówki do
programatora. J2: **1 = REF 3,3 V, 2 = SWIO/PD1, 3 = GND**. Dla używanego
WCH-Link podłączamy SWIO i GND, pozostawiamy pin 1 pusty i zasilamy PCB przez
USB. Wyjścia zasilania programatora zostają odłączone.

Użytkownik ma zaciskarkę LionRage z wymiennymi szczękami; zdjęcie wskazuje
najmniejsze pole 0,08 mm². Dokładny model i dopasowanie do PicoBlade nie są
potwierdzone. Najpierw wykonać próbny zacisk: styk powinien utrzymywać przewód,
pozostać prosty i zatrzasnąć się w obudowie. Nie zamówiono nowej zaciskarki.
Rozważane alternatywy to IWISS IWS-2820M i ENGINEER PA-09. Dane narzędzi i
dawne ceny są w archiwum zakupowym; ponowny zakup wymaga świeżej wyceny.

Magazynki to model Printables 580643. Potwierdzone 500 pomarańczowych LED-ów
na magazynek mieściło się ciasno; taśmy papierowe pakują się inaczej. Nie
przenosić tej pojemności na inne komponenty. Układy scalone nie będą w tych
magazynkach. Pojemność pojemnika jest preferencją, nie wymogiem zakupu;
porównywać cenę całej pozycji, ilość i użyteczność zapasu.

## Firmware i sposób pracy

Aktualizacja 14 października 2026: **druga płytka v3 jest zmontowana i działa**.
MCU ma UUID `d7-6e-ab-cd-41-3a-bd-ff`. Wgrano osobne demo
`v3-scan-demo` (wiersze, kolumny i 64 pojedyncze piksele); wszystkie 5228 bajtów
potwierdzono odczytem po zachowaniu dwóch zgodnych kopii całego flash.
Za osobną zgodą użytkownika ustawiono PD7 jako GPIO: USER 0x17 → 0x1f,
z poprawnym bajtem odwrotnym i bez zmian pozostałych option bytes.
SWIO potwierdziło start, pauzę/wznowienie i trzy fazy skanu. Po poprawkach montażu
użytkownik potwierdził działanie wszystkich diod; zgłoszona martwa kolumna jest
naprawiona, ale dokładnej poprawki nie zapisano. Dowody:
`build/board-readback/second-v3-scan-20261013T220549Z/` (czas UTC).
Ostatni obraz zweryfikowany przez agenta to skan; później podano polecenia
wgrania fali, bez potwierdzenia wykonania lub odczytu. **Następny krok to
lutowanie połączeń brzegowych**, kontrola ciągłości i zwarć oraz przygotowanie
testu I2C obu płytek. Samo działanie LED nie potwierdza jeszcze I2C ani
pomiarów zasilania/prądu. Zużycie drugiej v3 rozliczono następnie w kanonicznym
inwentarzu przy użyciu skilla shelf-inventory: 1 MCU, 1 dekoder, 64 LED-y,
8 rezystorów 51 Ω, 1 kondensator C4 i 4 kondensatory C1/C2/C3/C5.
Użytkownik potwierdził, że tylko te osiem rezystorów i pięć kondensatorów są
wlutowane; przyciski i cztery rezystory 10 kΩ drugiej v3 pozostają w rezerwie.
R11/R12 na obu płytkach nie zużyto: wcześniejsze odliczenie dwóch sztuk
skorygowano do zera. Rezerwa obejmuje teraz trzy niezmontowane v3 oraz brakujące
części zmontowanych, w tym cztery rezystory 4,7 kΩ dla obu działających płytek.
Pozostawiono niepewny podział 51/68 Ω pierwszej v3 i historyczne straty IC.
Planowane 5 MCU / 320 LED-ów dla v4.1 jest nadal osobnym zapisem; zamówienia
TME nie zmieniono. Bilans konserwatywny: 46 MCU i 872 LED-y na półce,
po rezerwie v3 43/680, po planie v4.1 38/360. To nadal szacunki, nie inwentaryzacja.

Użytkownik potwierdził następnie, że **na obu płytkach v3 nie wlutowano
rezystorów I2C**: R11 (SCL–VCC) i R12 (SDA–VCC), oba 4,7 kΩ.
Przed testem wymagana jest przynajmniej jedna para podciągania na wspólnej
magistrali. Przygotowane obrazy I2C mają ustalone role: pierwsza płytka jako
master, druga jako odbiornik `0x32`; master wysyła licznik automatycznie co
sekundę. Wystarczy jeden WCH-LinkE do kolejnego programowania płytek i logów
mastera; obie płytki muszą być zasilane. [Procedura testu](i2c-v3-test.md).
Nowych obrazów I2C nie wgrano podczas przygotowania; test fizyczny pozostaje
do wykonania po lutowaniu brzegów/podciągania i ustaleniu zasilania.

Przygotowano też żądany łańcuch USART: **ten sam obraz `v3-uart-chain` na każdej
płytce**. TX komputera trafia do RX pierwszej z lewej, każdy TX płytki trafia do
RX następnej, a TX skrajnej prawej wraca do RX komputera. Komputer inicjuje
pakiety; firmware nie wymaga wyboru mastera/odbiornika. Każda płytka sprawdza CRC,
zwiększa licznik przebytych płytek i przekazuje pakiet. Matryce pokazują pozycję
i licznik, logi lokalne trafiają tylko do SWIO. Do tego testu nie są potrzebne
R11/R12. [Instrukcja i program PC](uart-chain.md). Nowego obrazu nie wgrano;
fizyczne połączenie dwóch płytek USART nadal czeka na lutowanie i test.

Arch jest środowiskiem roboczym; konfigurację opisuje [instrukcja](arch-setup.md).
V3 z CH32V003 na PCB potrzebuje naprawy GND między C1 i C3; poprawiony CAD zachowano w `archive/hw/ledkiv3.1-ground-repair-20261014/`.
Nazwa v3.1 oznacza teraz nowy rework z części v3 i wybranymi funkcjami v4;
osobna sesja projektowa pracuje w `build/sessions/v3.1-design/`. USART na zidentyfikowanej płytce v3 działa, dwupłytkowe I2C pozostaje
do sprawdzenia. Plan bootloadera przez UART nie oznacza gotowej implementacji.

Domyślne `make` buduje tekstowy firmware v3: tekst UTF-8, SWIO/USART, regulacja
tempa, pauza, ramki i jasność gamma 2,2. Tekst zmienia `t TEKST` i Enter;
limit to 64 znaki. TUI ma sterowanie Vim przez oba interfejsy. Naprawiono CRLF
oraz wygaszanie GPIO przy przełączaniu kolumn, usuwając zgłoszone obce piksele.
Skany mają 250 Hz pełnych ramek, PWM nominalnie 10 kHz i przerwę 100 µs.
[README](../README.md) oraz [instrukcja TUI](tui.md) zawierają polecenia i wyniki.

Osobny `v3-visual-demo` jest animacją fali 8×8, działającą na płytce.
Ostatni zapisany stan po flashowaniu to fala 45 ms/krok i jasność 100%; nie
jest to świeży odczyt urządzenia. Tekst nadal jest domyślnym projektem.
Demo mowy używa Supertonic na CPU z naturalnym zwolnieniem, ciągłym napisem
i wybranymi punktami synchronizacji. Odrzucono rozciąganie gotowego audio
i syntezę słowo po słowie. [Szczegóły mowy](tts-demo.md).

CAD obsługiwano przez KiCad CLI i skrypty pcbnew; demonstracja naprawy GND
korzystała z oficjalnego IPC. KiCadRoutingTools pomaga w próbach routingu,
a KiCad SVG Extras daje [interaktywny raport](../hw/ledkiv4.1/exports/prototype/routing-review/viewer.html).
Raport obejmuje dziewięć paneli SVG, wybór sieci i statystyki prób, także
nieudanych. Źródła i geometria mają być sprawdzane niezależnie od oceny routera.
FreeCAD i modele dla A1 mini pozostają dostępne do iteracji dyfuzora i nośnika.

## Następne kroki

1. Użytkownik dokańcza zakup JLCPCB; zapisać potwierdzenie rewizji i parametrów.
2. Po dostawie TME przeliczyć części i uzupełnić `on_hand_confirmed`.
3. Sprawdzić zaciski i ciągłość przewodu SWIO.
4. Druga v3 działa: wlutować połączenia brzegowe, sprawdzić ciągłość/zwarcia
   i ustalić zasilanie obu płytek przed testem I2C.
5. Na pierwszym v4.1 zmierzyć zasilanie, prąd, temperaturę i zbocza UART,
   sprawdzić każdy piksel/PWM, I2C oraz dopasowanie mechaniki i optykę.
   Wyniki zapisać w [kwalifikacji](v4_1-qualification.csv).

Stała autoryzacja firmware/testów obejmuje od 2026-10-14 obie zidentyfikowane v3:
`d7-73-ab-cd-41-3f-bd-ff` oraz `d7-6e-ab-cd-41-3a-bd-ff`. Inne płytki,
zmiany option bytes i zasilania programatora nadal wymagają osobnej autoryzacji. Nie wykonywano flashowania,
zmian CAD ani płatności przy porządkowaniu zakupów i tych notatek.


## Pomiar prądu v3 dla reworku v3.1 (2026-10-14)

Na żądanie użytkownika wgrano `v3-current-demo` z osobnej sesji
`build/sessions/v3.1-design/` na drugą v3, UUID
`d7-6e-ab-cd-41-3a-bd-ff`. Dwie pełne kopie 16 KiB są zgodne;
wszystkie 5240 bajtów nowego obrazu potwierdzono odczytem.
Option bytes są identyczne przed/po; nie zmieniano zasilania programatora.
Build i testy hosta przeszły. SWIO potwierdziło start/status, wygaszenie `0`
i powrót `1`. Ostatni stan to pojedynczy dolny lewy piksel, R1/S1,
jasność 100 i nominalne wypełnienie skanu 10%. To zastępuje wcześniejszy
zapis ostatniego zweryfikowanego obrazu skanowania na tej płytce.
Napięcie szyny, napięcie na rezystorze, prąd i przebieg nadal niezmierzone;
firmware/status nie potwierdzają fizycznego obrazu ani bezpieczeństwa obciążenia.
Dowody: `build/board-readback/current-demo-20261014/summary.json`,
`swio.log` i zachowane odczyty. Następny krok: pomiar napięcia na wybranym
rezystorze oraz rzeczywistego napięcia zasilania.

Użytkownik podał następnie odczyty UNI-T UT61B: 0,067 V na R1
i 3,312 V zasilania (interpretacja kolejności zgodna z prośbą o pomiary).
Dla nominalnych 51 Ω to 1,31 mA średnio i szacowane 13,1 mA w impulsie
przy nominalnym wypełnieniu 10%. Rzeczywistej rezystancji i przebiegu nie
zmierzono; wynik zakłada prawidłowe uśrednianie przez miernik. Rozbieżność
zakresów mV/V pozostaje niewyjaśniona. Pomiar pojedynczego piksela nie
kwalifikuje obciążenia pełnej kolumny. Zapis: `build/board-readback/
current-demo-20261014/user-current-measurement.json`; przekazano sesji reworku.

### Full-column current test (2026-10-14)

Full-column follow-up (2026-10-14): user explicitly requested full-column mode
after the decoder limits were discussed and reported having tested it before.
The testing session built an isolated app in build/hardware/v3-current-column/;
design-session sources were not modified. Second v3 UUID
d7-6e-ab-cd-41-3a-bd-ff: two matching full backups, all 5428 image bytes match
readback, all option bytes unchanged, no programmer power commands. Actual
command-path host checks and SWIO startup/status/blank/full-column restore passed.
Final firmware selection: full S1 column, 8 pixels, brightness 100, nominal
10% per-pixel scan duty. c selects full column, 0 blanks, 1..8 selects one row.
No new current or supply readings yet; this flash does not qualify the load.
Evidence: /home/pies/letki/build/board-readback/current-column-20261014/summary.json.
For total column current, measure each R1..R8 branch drop and sum V/R; do not
interpret one resistor reading as total current or assume all branches equal.

User-reported FULL-COLUMN readings: R1 drop 0.020 V; supply 3.309 V.
User confirms power from WCH-LinkE 3.3 V. Nominal R1=51 ohm gives
0.392 mA mean / 3.92 mA estimated pulse current in R1 only, assuming valid
meter averaging and nominal 10% timing. Total column current remains unknown;
R2-R8 measurements pending. Single-pixel R1 was 0.067 V at supply 3.312 V.
R1 current fell about 70% while supply changed -3 mV. This is consistent
with decoder output voltage increasing under load, but that voltage has not
been measured. Do not infer identical branch currents or electrical qualification.
Evidence: /home/pies/letki/build/board-readback/current-column-20261014/user-current-measurement.json.

Completed full-column readings: user reports ALL R1-R8 at 0.020 V.
With nominal 51 ohm rows, sum of mean branch currents is 3.137 mA;
at nominal 10% scan duty estimated combined pulse current is 31.37 mA.
Assumptions/uncertainties remain: meter mean response, resistance tolerance,
rounding/resolution and unmeasured timing/waveform. TI SN74HC138 Rev G
per-output absolute maximum is 25 mA; estimated result exceeds it and does
not qualify the existing direct-drive circuit. This is useful rework evidence
for limiting instantaneous aggregate column current, not only PWM average.
The test display was blanked via SWIO 0, acknowledged CURRENT blank.
Firmware reset/reopening SWIO restarts its full-column default.
Evidence: /home/pies/letki/build/board-readback/current-column-20261014/user-current-measurement.json
and swio-measurement-end.log; no further flash/option/power changes.

### V3 diffuser print batch (2026-10-14)

User accepted the transparent-PETG diagnostic (some stringing) and requested
five diffusers. Prepared fresh face-down mesh from the preserved v3 FreeCAD
model, dimensions 40.64 x 44.45 x 4.9 mm, 0.4 mm face. Nominal solid/mesh
and imported board/component intersections checked; native source hash unchanged.
Classic slicing omitted many 0.4 mm pixel separators; Arachne paths were
inspected at Z=0.6 mm and preserve all five grids. Batch uses 0.20 mm layers,
no supports, Generic PETG 255 C nozzle/70 C textured bed; no AMS.
Started via local bambu-cli after user confirmed clear, reinstalled plate.
A1 mini 192.168.1.129 reported RUNNING/preparing, 25 layers, no HMS errors.
Estimated 30m54s total and 7.24g object filament. These are slicer estimates;
completion, fit/retention and optical quality are not yet verified.
Records: `build/printer/diffusers-five-job.json`, `diffusers-five-start-status.json`,
and `build/hardware/v3-diffuser-print/five-grid-toolpaths.png`. Sliced archive:
`archive/hw/ledkiv3/dyfuzor/exports/v3-diffusers-five.gcode.3mf`.
Earlier diagnostic start was rejected by MQTT verification; user enabled
LAN Only/Developer Mode and cleared error, after which it started and completed.
Credentials remain in protected ignored files; no secrets recorded in docs.

### Two-board UART-chain setup: left board flashed (2026-10-14)

User reports the edge bridge assembled and both boards connected to WCH-LinkE
3V3/GND with LinkE TX/RX for the PC chain; left board connected to SWIO.
Host USB serial is /dev/serial/by-id/usb-wch.cn_WCH-Link_02858F0687B7-if01
(current /dev/ttyACM0). UART initialized to 115200 8N1 before flashing; original
tty settings saved in build/board-readback/uart-chain-20261014/tty-original.pkl
for restoration after the chain test. No other port reader was found.
Left UUID d7-73-ab-cd-41-3f-bd-ff: two matching 16KiB backups, all 10136
UART-chain image bytes matched readback, option bytes preserved, no programmer
power commands. SWIO startup and initial zero diagnostics passed. Build/host
tests passed. Image SHA256 4b805c9b432766bb231e833b73fc7d17c398d1f9079c053c73f776992821f547.
Evidence: build/board-readback/uart-chain-20261014/left/summary.json.
Right board not yet flashed with this image; end-to-end test still pending.
Next: user moves only SWIO signal to right board; verify second UUID, preserve
its firmware twice and option bytes, flash the same frozen image, then run
20 checked PC packets expecting two hops. Actual rail/baud/waveforms not measured
during this step. Earlier current measurements used the second board.

## Physical two-board UART-chain result (2026-10-14)

Both assembled v3 boards passed the complete PC TX -> left RX -> left TX ->
right RX -> right TX -> PC RX chain using the same 10136-byte image.
Left UUID: `d7-73-ab-cd-41-3f-bd-ff`; right UUID: `d7-6e-ab-cd-41-3a-bd-ff`.
Each board had two matching 16 KiB backups and complete image readback
verification; option bytes and programmer power settings were preserved.
User confirmed existing WCH-LinkE 3V3/GND power through the soldered bridge
and the LinkE TX/RX connection. The host serial device is
`/dev/serial/by-id/usb-wch.cn_WCH-Link_02858F0687B7-if01` (`/dev/ttyACM0`).

At configured 115200 8N1, all 20 distinct checked requests returned with two
hops, matching random tokens/counters and valid CRCs. Every accumulated
diagnostic count was zero. Right SWIO, held open during UART traffic, confirmed
`CHAIN position=2 counter=46665 ok=20 bad=0 drop=0 uart=0 txdrop=0`.
The original pre-initialization host tty settings were restored and verified.
Both boards retain UART-chain firmware; last accepted counter is 46665.
Matrix appearance was not independently inspected. Actual rail/baud/waveforms
and runtime stack high-water were not measured in this run. This confirms
physical two-board UART transport; two-board I2C remains untested, and it does
not qualify v4 buffers or resolve the measured v3 decoder-loading limitation.

Evidence: `build/board-readback/uart-chain-20261014/live-result.json`,
`uart-traffic.log`, `right/swio-live-test.log`, both board summaries/backups
and readbacks. Image SHA256:
`4b805c9b432766bb231e833b73fc7d17c398d1f9079c053c73f776992821f547`.

I2C preparation follow-up (2026-10-14): user confirms R11/R12 fitted on the
left/original v3. One 4.7k pair is sufficient for the shared two-board bus.
Shared inventory records two C26022 consumed and two matching holds released;
remaining hold is 8 (right pair plus three future pairs), free balance 990.
The separate v4.1 plan and all other lots remain unchanged. Evidence:
build/inventory/left-v3-i2c-20261014/summary.json. Controller/target images
rebuilt successfully; they have not been flashed. Both boards retain UART-chain
firmware. I2C roles remain left/original controller, right/second target 0x32.

User authorization update (2026-10-14): standing firmware-update/test permission
now covers both identified v3 boards. User explicitly said not to require
per-image second-board permission anymore and approved the I2C test. Preserve
identity checks and backups; option bytes/power/other boards remain outside it.

I2C right/receiver flash (2026-10-14): right UUID d7-6e-ab-cd-41-3a-bd-ff
now runs target-role interface firmware at 7-bit address 0x32. Two matching
full UART-chain backups preserved; all 12396 target image bytes match readback;
option bytes unchanged and no programmer power commands. SWIO banner and
explicit status verify mode=target, ok=0 fail=0 counter=0 uart_errors=0
tx_dropped=0 auto=0. Initial combined SWIO banner/status exceeds its 127-byte
queue capacity; initial status was dropped, so the test requested status after
the banner drained. Failed wait and successful explicit status logs retained.
Evidence: build/board-readback/i2c-two-v3-20261014/right/summary.json, swio.log
and swio-status.log. Left remains UART-chain; physical I2C not tested yet.
Next: user moves only SWIO signal to left, then controller flash and live test.
Standing firmware-update/test permission now covers both identified v3 boards.

## Physical two-board I2C result (2026-10-14)

The existing two assembled v3 boards passed 20 consecutive physical I2C
exchanges with matching requested counters and `reason=reply CRC`, configured
for 100 kHz. Left/original UUID `d7-73-ab-cd-41-3f-bd-ff` is controller
(12412-byte image); right/second UUID `d7-6e-ab-cd-41-3a-bd-ff` is target
at 7-bit address 0x32 (12396-byte image). Both images matched readback after
two matching full-flash backups per board; all option bytes preserved and
no programmer power commands. User confirmed existing WCH-LinkE 3V3/GND
power through the soldered edge bridge and one nominal 4.7k R11/R12 pair
fitted on the left board. UART TX/RX wires remained connected but commands
and acceptance evidence used SWIO; no host serial port was opened in this run.

Controller final checked status: ok=20, fail=0, counter=46665, uart_errors=0,
tx_dropped=0, auto=0. Then `auto on` was acknowledged; the controller now
increments from 46666 once per second. Right target startup/status previously
verified clean; its final UART/drop diagnostics were not separately read.
Visual counter agreement, actual frequency/waveforms/rail/current and runtime
stack remain unmeasured in this run. This establishes v3 physical I2C packet
transport, not v4/v4.1 logic/power/buffer or production qualification.

Evidence: `build/board-readback/i2c-two-v3-20261014/live-result.json`,
`controller-swio.log`, `commands.json`, setup/source hashes and each board's
identity/backups/readback/options/summary. Final firmware remains I2C controller
and target, with automatic counting on. This supersedes older pending-I2C
status paragraphs. No CAD or purchases changed during this test.

## Two-board ping-pong demo (2026-10-14)

User wanted a visual indication of board communication. Separate
`firmware/pingpong-demo/` forms one 16x8 bouncing-ball scene. Left advances
a phase only after matching I2C reply CRC; right renders received phases only.
Corner indicators derive from successful exchanges; failures or 1.5s without
valid transport freeze the last ball and light the corner steadily. Pause
continues communicated held phases. Uses unchanged active binary/PWM display
driver and shared interface-demo I2C/protocol sources; no UART initialization.
Build: `make pingpong-demos -j4`; default v3 text unchanged. Preview:
`build/preview/pingpong.gif`; host tests, all variants and clangd passed.
Left/right images are 10988/10448 bytes; RAM including 256-byte stack is
672/664 bytes; conservative foreground+both ISR stack sum 240 bytes, runtime
high-water unmeasured. Evidence: `build/pingpong-validation.json`.

Left/original board was flashed/readback verified after two matching backups
and unchanged option bytes/power. It passed 20 consecutive CRC-confirmed phase
updates against the existing right interface-demo target, plus pause (continued
exchanges with held phase) and resume. Last checked status:
`PONG role=left phase=21 ok=24 bad=0 link=1 paused=0 ms=100`.
Right/second board was then identified, flashed and readback verified after
two matching full backups; option bytes and programmer power were preserved.
With both final demo images running, right received 32 consecutive CRC-validated
phases, covering a full horizontal round trip, with zero receiver failures:
`PONG role=right phase=151 ok=32 bad=0 link=1 paused=0 ms=100`.
Both boards are left running at 100 ms/step. Optical seam quality, physical
link-loss behaviour and runtime stack high-water remain unmeasured. Evidence:
`build/board-readback/pingpong-20261014/left-live-result.json`,
`right-live-result.json` and each board's `summary.json`.


## Native C strip renderer (2026-10-14)

`make renderer-run BOARDS=5` launches a native Wayland/Cairo window with
configurable horizontal 8x8 tiles and a local Unix-socket agent interface.
Keyboard presets cover 1-5; dynamic storage/geometry support 1-256 tiles within
the existing 15-bit phase field. Real firmware pong geometry and packet CRC
code are compiled into the host app; original two-board firmware API is retained.
Agent commands expose deterministic stepping/time, per-link loss/corruption,
JSON pixel/state inspection, external validated phases/packets, raw arbitrary
frames and PNG snapshots. See `host/renderer/README.md`.

Full native-process integration tests passed for complete 1-5 trajectories,
seams/wrap, CRC damage/rejection, lost-link timeout/recovery, pause with traffic,
external/raw frames, invalid input preservation, 256-board allocation, client
CLI, PNGs and stalled/duplicate clients. Address/undefined sanitizer checks
passed (third-party global font-cache leak scanning disabled). Existing firmware
host tests, all variants and clangd pong checks passed. Hyprland confirmed a
native window (xwayland false); targeted 1/5 and Space input were verified with
socket state readback. Evidence: `build/renderer/`.

Generalized firmware builds are 11324 bytes left / 10776 right; RAM including
256-byte stack remains 672/664. Conservative stack sum stays 240: I2C recovery
foreground 204 plus 36 ISR bytes; generalized render/callback paths are smaller.
These new images were NOT flashed. Physical boards retain the previously verified
10988/10448-byte images frozen in `build/board-readback/pingpong-20261014/`.
No programmer, power, option bytes, hardware CAD or inventory changed in this task.
Host simulation does not qualify actual multi-board I2C discovery/electrical or
optical behavior; its configurable linear acknowledgement chain is a test model.


## Standard two-board text candidate and preview (2026-10-14)

User requested two standard images with a different moving-text default,
UART control and a native display demonstration before flashing. Candidate
`firmware/strip-text/` builds with `make strip-text-images` (roles left/right,
-Os); existing single-board v3 and diagnostic builds remain available.
Default compact Polish text is LETKI DZIAŁA, bounce with endpoint holds,
75ms/column and brightness 100; UART `m scroll` selects continuous leftward
scrolling, `m bounce` restores bounce. UART text/speed/brightness/pause/resume/
reset/arm/ping/status and eight-/sixteen-column host-frame commands are supported.

Left handles PC UART commands and sends the right tile's actual pixels and
brightness over separate 14-byte CRC-8/sequence I2C frames (target 0x32,
configured 100kHz, existing left pull-up pair). Left animation commits after
reply-CRC confirmation; failed exchanges retry without advancement. Newer
commands win over older in-flight snapshots. Right renders received pixels only
and transparently relays left UART replies to the PC using the existing
PC TX -> left RX -> left TX -> right RX -> right TX -> PC RX arrangement.
Right boot/status logs stay on SWIO. Active PWM/gamma/scan pin map is reused.

The native C renderer now shares this exact scene/font/UTF-8/command/packet code.
`make renderer-text` opens a two-board demonstration; socket `demo text` and
`uart COMMAND` support direct agent tests. The tour showed bounce then scroll
and returned to bounce. Full-cycle native recordings are in
build/strip-text-preview/bounce.gif and scroll.gif. These are host demonstrations,
not physical UART/I2C/optical validation of the new images.

Frozen images and source hashes: build/strip-text-prepared/manifest.json.
Left image 12320 bytes, RAM 1932 including 256-byte stack (116 spare);
right image 6652 bytes, RAM 992 including stack. Conservative head stack bound
244 bytes: assessed foreground 196 plus retained older O0 equivalent IRQ budget
48; the current Os fast IRQ software paths report zero stack and were inspected
in disassembly. Right conservative bound 176. Runtime high-water is unmeasured.
Host scene and both real app roles, actual frame driver with register mocks,
all native socket tests, address/undefined sanitizers and clangd passed. All
variants passed a serial retry after a temporary assembler segfault in an
unchanged archived ADC source; the failed log was retained.

No board has been flashed during this task. Current physical images remain the
preceding verified ping-pong 10988/10448-byte images. Programming helpers and
frozen binaries are prepared but NOT EXECUTED in
build/board-readback/strip-text-20261014/{left,right}/. When proceeding after
preview, program/identify/back up/verify right first, then left; preserve option
bytes and programmer power. Read firmware/strip-text/README.md for controls,
wiring, limitations and follow-up. No CAD, inventory or procurement changed.


## Standard text right receiver flashed (2026-10-14)

At the user's explicit request, right UUID d7-6e-ab-cd-41-3a-bd-ff was
programmed with the frozen 6652-byte standard text receiver. All bytes matched
readback, two full 16KiB backups matched, option bytes were unchanged and no
programmer power commands were issued. SWIO verified the correct receiver
startup and status: seq=0 ok=0 fail=0 link=0 uart_errors=0 tx_dropped=0.
This is receiver startup validation, not a passed two-image transport test.
Left remains the prior ping-pong image; the right needs matching 14-byte frames
from the new head before it can display text. Old diagnostic requests may be
rejected. Evidence: build/board-readback/strip-text-20261014/right/summary.json,
right/swio-live.log and right-live-result.json. Prepared manifest is now
RIGHT_FLASHED_LEFT_PENDING. Next is moving only SWIO to the left for the
matching head image; existing power/GND and UART/I2C wiring stay in place.


## Standard text pair programmed and tested (2026-10-14)

Left/original d7-73-ab-cd-41-3f-bd-ff was identified and flashed with the frozen
12320-byte standard text head. All bytes matched readback after two matching
full 16KiB backups; option bytes and programmer power were unchanged. Right
retains its previously verified 6652-byte receiver. Both now run standard text.

Physical UART passed 20 exact random-token replies through the right's transparent
relay, with zero head receive-error/drop counters under fast 10ms scrolling.
Mode changes, pause/resume, speed, brightness 25/100, Polish UTF-8, 64-character
input, rejected 65-character/invalid UTF-8/invalid speed/brightness, legacy eight-
column frames and full sixteen-column frames passed. The head's real RAM snapshot
showed 1839 successful new 14-byte I2C frame CRC acknowledgements and zero I2C
failures; scene and committed revisions matched. Read-only debug snapshots briefly
halted the head and then resumed it. A subsequent UART check confirmed uptime
advanced 610ms across a 600ms host wait, with zero UART errors/drops. This checks
software clock progress, not waveform timing or oscillator calibration.

The initial adapter opening missed the boot banner; the first subsequent status
was an invalid line, then status replied cleanly with hardware UART counters zero.
Failed startup logs were preserved; no reset/counter clearing was used to obtain
the passing full test. Host uart_text.py now recognizes mode/full-strip-frame
acknowledgements and both legacy/new help formats; live m scroll/m bounce/help/
status and seven host serial tests passed. Final state is LETKI DZIAŁA, bounce,
75ms/column, unpaused, brightness 100, host-frame mode off; SWIO remains on left.

Evidence: build/board-readback/strip-text-20261014/summary.json, per-board backups/
readbacks/options, pair-live-result.json, UART traffic/raw log, head counter/scene
snapshots and post-ram-clock.json. Prepared manifest is BOTH_FLASHED_PAIR_TESTED.
Right final cumulative diagnostics, optical rendering, rail/current/waveforms and
runtime stack high-water were not independently measured. No CAD/stock/purchases
changed. Earlier left-pending statements are superseded.


## Third v3 assembly test (2026-10-16)

Third-board UUID `d7-69-ab-cd-41-35-bd-ff` passed the separate scan demo
without USART connected. The user explicitly authorized flashing/testing this
board and a PD7 reset-to-GPIO option change. Two identical full 16 KiB flash
backups were saved first. All 5,228 scan-image bytes matched readback.
USER changed from 0x17 to 0x1f with its inverse byte; all other option bytes
were preserved and verified. No programmer power commands were issued.

Live SWIO startup, pause/status/help/resume and a complete row/column/pixel
cycle passed. The user confirmed all LEDs and patterns look correct.
The board remains running the automatic scan at brightness 100, unpaused.
Evidence and backups: `build/board-readback/third-v3-20261016/summary.json`
and adjacent files. Rail/current/waveform and runtime stack high-water were
not measured; USART and inter-board interfaces were not tested in this session.
No CAD or inventory changes were made; assembly consumption is not inferred
from the functional test.


## V3 next assembly steps and authorization (2026-10-16)

Three v3 boards are assembled; the third passed the scan test and the user
confirmed all LEDs/patterns look correct. The user will solder the remaining
two boards before connecting all five. Test each new assembly individually
before full-chain testing; the five-board chain is not yet connected/tested.

The user explicitly grants standing permission to prepare and execute v3 test
procedures and flash/restart any v3 board without asking again, including new
assemblies. This supersedes the earlier restriction to two known UUIDs. Still
identify boards, save matching full flash backups and verify programmed-image
readback. New option-byte changes, programmer power changes, separate erase
operations and purchases retain their existing separate authorization rules.
Third-board PD7 GPIO configuration was separately authorized and verified.
See AGENTS.md for the known identities and third-board evidence.


## Fourth v3 assembly scan test (2026-10-16)

Fourth-board UUID `d7-50-ab-cd-41-1c-bd-ff` was identified and tested with
unchanged `v3-scan-demo`. Two matching full 16 KiB flash backups were saved.
The user separately authorized PD7 GPIO configuration for this board: USER
changed from 0x17 to 0x1f with its inverse byte; all other option bytes were
preserved and verified. All 5,228 programmed image bytes matched readback.
No programmer power commands or separate erase operations were issued.

SWIO startup, pause/status/help/resume and a complete row/column/64-pixel scan
cycle passed. `make test` passed. The board remains in automatic scan mode,
brightness 100, unpaused. The user confirmed all eight rows, eight columns and 64 individual pixels
look correct, without missing LEDs or ghosting. Rail/current/waveforms, runtime stack, USART and inter-board interfaces were
not measured/tested in this session. No CAD or inventory changes were made;
assembly consumption is not inferred from this test.

Evidence and backups: `build/board-readback/fourth-v3-20261016/summary.json`
and adjacent files. This identifies the fourth assembled board; the fifth
board and full five-board chain still need their own tests.


## Fifth v3 assembly scan test (2026-10-16)

Fifth-board UUID `d7-56-ab-cd-41-22-bd-ff` passed the unchanged v3 scan demo.
Two matching full 16 KiB flash backups were preserved before updates. The user
explicitly requested reset-pin reprogramming: PD7 was configured as GPIO
(USER 0x17 to 0x1f plus inverse), with all other option bytes preserved and
verified. All 5,228 programmed image bytes matched readback. No programmer
power commands or separate erase operations were issued.

SWIO startup, pause/status/help/resume and a complete row/column/64-pixel cycle
passed. The user confirmed all patterns look correct, without missing LEDs
or ghosting. The board remains running automatic scan, brightness 100,
unpaused. Evidence/backups: `build/board-readback/fifth-v3-20261016/summary.json`
and adjacent files. The unchanged image matches the third/fourth scan images;
`make test` passed earlier in this session.

The last two assemblies now have individual scan/readback/SWIO and user optical
checks recorded. The complete five-board chain remains untested. USART,
inter-board interfaces, rail/current/waveforms and runtime stack were not
measured in this test. No CAD or inventory changes; assembly consumption is
not inferred from functional validation.


## Two additional v3 diffusers started (2026-10-16)

User requested two diffusers before resuming firmware work and confirmed the
plate cleared/reinstalled and external PETG loaded. Started
`letki-v3-diffusers-two-20261016.gcode.3mf`; A1 mini verified RUNNING,
25 layers, correct filename, print_error=0 and no HMS entries during preparation.
Same preserved v3 face-down mesh, 0.20 mm layers, Arachne, no supports,
255 C nozzle / 70 C textured plate profile, AMS explicitly disabled. Both full
pixel grids inspected in actual extrusion toolpaths at Z=0.6 mm. Slicer estimate
16m38s total, 2.94 g PETG. Completion/fit/optical quality not yet verified.
Records: `build/printer/diffusers-two-job.json`, `diffusers-two-start-status.json`;
sliced file and grid toolpath image in `build/hardware/v3-diffuser-print/two/`.
No source CAD edits. Print runs independently while firmware work continues.


## Falling text, brightness pulse and five-tile candidate (2026-10-16)

Prepared third text mode `m fall`: word-wrapped, centered lines moving from
above the top down through the bottom, using the existing compact Polish font.
`m fall` enables brightness modulation; `e off` makes it steady, `e pulse`
enables it in any mode. `b 0..100` remains the brightness ceiling. Pause holds
both movement and modulation. Gamma/PWM scanning remains in the existing driver.

`make strip-five-images -j4` builds a separate head and four receiver images
for 40x8 geometry, at addresses 0x32/0x33/0x34/0x35 from left to right after
the head. UART replies relay through all receivers. The head commits a scene
after all four CRC replies; receivers publish sequentially on arrival, without
synchronized scan clocks or batch rollback. Retain common SDA/SCL/GND, one
existing pull-up pair and the existing UART chain. Physical UUID-to-position
mapping must be established before flashing; assembly order is not assumed.

`make test`, all firmware variants, seven native renderer tests and clangd
main/scene checks passed. Five-head sections: 13,572 bytes flash, 1,952 bytes
RAM including the 256-byte stack. Foreground maximum 204 bytes plus retained
conservative ISR budget 48 gives 252 bytes; runtime high-water is unmeasured.
The original two-tile build commands remain available. Frozen previous images
and board readbacks remain intact. New binaries, hashes and evidence:
`build/strip-text-fall-prepared/manifest.json`.

Five-board preview: `build/strip-text-preview/fall.gif`. Launch with
`python3 scripts/demo_strip_text.py --boards 5 --mode fall --text 'LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM'`.
No hardware was flashed during preparation; five-board electrical/transport and
new optical effects still need physical testing after soldering. No CAD changes.


## Five-board chain programming: position 5 (2026-10-16)

User connected the five-board chain, with the three newer assemblies on the
left and the two previous text boards on the right. User confirmed SDA/SCL
also connected across all five with the existing single pull-up pair.
WCH-Link USART is `/dev/ttyACM0`; no USART traffic tested yet in this session.

Rightmost position 5 identified as UUID `d7-6e-ab-cd-41-3a-bd-ff` and programmed
with frozen `tile4` receiver, I2C address 0x35. Two matching full 16 KiB
working backups saved; all 6,668 image bytes matched full-flash readback.
All option bytes preserved, no programmer power or separate erase commands.
SWIO startup and complete status passed: seq=0 ok=0 fail=0 link=0,
uart_errors=0 tx_dropped=0. This is receiver startup, not five-board transport
validation. Positions 4/3/2/head remain pending. Move only SWIO one board
left to position 4 next, preserving existing supply and chain wiring.
Evidence: `build/board-readback/strip-five-20261016/position-5/summary.json`,
`swio.log` and per-board readbacks/options; `chain-progress.json` tracks mapping.


## Five-board chain programming: position 4 (2026-10-16)

Position 4 (second from right) is original UUID `d7-73-ab-cd-41-3f-bd-ff`.
Programmed frozen `tile3` receiver, I2C 0x34, after two matching full 16 KiB
working backups. All 6,668 image bytes matched full-flash readback; existing
option bytes `a55aff00ff00ff00ff00ff00ff00ff00` were preserved exactly. This
is the as-found value for this session, including USER=0xff with valid inverse;
no option-byte change was performed or inferred from older records. No
programmer power or separate erase commands. SWIO startup and complete status
passed: seq=0 ok=0 fail=0 link=0 uart_errors=0 tx_dropped=0.

Positions 4 and 5 now run their respective five-tile receivers; positions
3/2/head remain pending. These startup checks do not qualify the full chain.
Next move only SWIO one board left to position 3. Evidence:
`build/board-readback/strip-five-20261016/position-4/summary.json`, backups,
readbacks/options and `swio.log`; mapping is in `chain-progress.json`.


## Five-board chain programming: position 3 (2026-10-16)

Middle position 3 identified as third-assembly UUID
`d7-69-ab-cd-41-35-bd-ff`. Programmed frozen `tile2` receiver at I2C 0x33
after two matching full 16 KiB working backups. All 6,668 image bytes matched
full-flash readback; all option bytes preserved (`a55a1fe000ff00ffff00ff00ff00ff00`).
No programmer power or separate erase commands. SWIO startup and complete
status passed: seq=0 ok=0 fail=0 link=0 uart_errors=0 tx_dropped=0.

Positions 3/4/5 now run their addressed receivers. Position 2 and leftmost
head remain pending; no five-board transport pass yet. Next move only SWIO
one board left to position 2, preserving power and chain wiring. Evidence:
`build/board-readback/strip-five-20261016/position-3/summary.json`, backups,
readbacks/options and `swio.log`; mapping in `chain-progress.json`.


Position-2 connection attempt (2026-10-16): after the user moved SWIO one
board left, two identity attempts returned no chip response / link errors.
Position 2 remains unidentified and unprogrammed; no flash, option-byte or
programmer power writes were issued. Retry after reseating SWIO on the second
board from the left, J2 middle pad, with existing common ground retained.
Evidence: `build/board-readback/strip-five-20261016/position-2-identify-retry.log`.
Previously programmed positions 3/4/5 remain recorded in `chain-progress.json`.


## Five-board chain programming: position 2 (2026-10-16)

Reseating SWIO restored communication. Position 2 identified as fifth-assembly
UUID `d7-56-ab-cd-41-22-bd-ff`, with transient link retries on initial identity.
Subsequent backup/program/readback/startup procedure succeeded. Programmed
frozen `tile1` receiver at I2C 0x32 after two matching full 16 KiB working
backups; all 6,668 image bytes matched full-flash readback. Option bytes
`a55a1fe000ff00ffff00ff00ff00ff00` preserved exactly. No programmer power or
separate erase commands. SWIO startup and complete status passed: seq=0 ok=0
fail=0 link=0 uart_errors=0 tx_dropped=0. Earlier connection failure is resolved.

All four receivers (positions 2..5, addresses 0x32..0x35) are programmed and
startup-verified. Leftmost position 1/head remains pending. Next move only
SWIO to the leftmost board's J2 middle pad; preserve power and chain wiring.
The full five-board transport is not tested until the matching head is running.
Evidence: `build/board-readback/strip-five-20261016/position-2/summary.json`,
backups/readback/options and `swio.log`; physical mapping in `chain-progress.json`.


## Five-board head and live chain test (2026-10-16)

Leftmost head UUID `d7-50-ab-cd-41-1c-bd-ff` programmed with the frozen
13,572-byte five-tile head image. Two matching full 16 KiB backups saved;
all image bytes matched full-flash readback, all option bytes preserved,
no programmer power or separate erase commands. SWIO startup/status passed.
All five positions are now programmed, left to right:

1. Head: d7-50-ab-cd-41-1c-bd-ff.
2. Receiver 0x32: d7-56-ab-cd-41-22-bd-ff.
3. Receiver 0x33: d7-69-ab-cd-41-35-bd-ff.
4. Receiver 0x34: d7-73-ab-cd-41-3f-bd-ff.
5. Receiver 0x35: d7-6e-ab-cd-41-3a-bd-ff.

Physical USART returned 20 exact random tokens through all four transparent
receiver relays. Scroll/bounce/fall, pulse on/off, speed, pause/resume,
brightness, Polish text and 64-character bounds passed; invalid mode/effect,
brightness/speed and 65-character text were rejected. Initial adapter open
returned an invalid line and head uart_errors=2; subsequent first-run tests
added no UART errors/drops. Logs and counters were retained without clearing.

Head RAM snapshot showed 4,466 I2C CRC acknowledgements and zero failures,
committed falling mode at 100 ms, ceiling 70, pulse phase 19, actual driver 61
and PWM 404. The batch logic commits after all four receiver replies. This is
logical packet/scene evidence; receiver cumulative diagnostics and waveform/
rail/current/runtime stack were not independently measured.

A second RAM inspection found the head had restarted during the diagnostic
window (uptime 90,340 -> 661 ms and default bounce). Cause was not established.
The failed comparison and both snapshots were preserved; do not claim that
this probe session resumed without reset. Falling mode was restored via UART.
A separate serial-only run passed another 20 exact pings and the controls,
with zero head UART errors/drops during that run and uninterrupted uptime
progress across ten 0.5 s waits. No probe operations or counter resets occurred
in that final serial run. Its zero counters follow the observed restart and
do not supersede the initial UART startup error record.

Left running **LETKI DZIAŁA PIĘĆ PŁYTEK RAZEM**, fall, 100 ms/row,
brightness ceiling 70, pulse enabled, unpaused. Optical confirmation pending.
Evidence/backups: `build/board-readback/strip-five-20261016/summary.json`,
per-position records, `attempt1-*`, `head-fall-a/b*`, UART raw/traffic and
`chain-live-result.json`. Earlier preparation/head-pending paragraphs are
superseded. No CAD or inventory changes; scan clocks remain independent.

The two-diffuser print is still RUNNING, latest 90%, layer 10/25, no print/HMS
errors; completion not yet verified (`build/printer/diffusers-two-job.json`).


## Stronger brightness pulse flashed (2026-10-16)

User confirmed all five boards work correctly, but found the original pulse
amplitude too low. The head alone was updated to a 5–100% brightness envelope
(relative to `b` ceiling), over 64 animation steps instead of 32. Four-line
pulse period gives successive fully visible falling lines different brightness
levels; at 100 ms/row the cycle lasts 6.4 s. At ceiling 70 the requested driver
range is approximately 4–70. Existing gamma correction and scan/blanking remain.

Head UUID d7-50-ab-cd-41-1c-bd-ff: two matching full 16 KiB working backups
saved before updating; all 13,580 image bytes matched readback; all option
bytes preserved, no programmer power or separate erase commands. Receivers
and their position mapping remain unchanged. `make test` and all seven native
renderer tests passed; RAM remains 1,952 bytes including 256 stack, conservative
stack sum 252 unchanged. Preview clip: `build/strip-text-pulse-prepared/pulse.gif`.

SWIO startup/status passed. First UART open rejected an invalid startup line;
subsequent 20 exact pings, mode/text/speed/brightness/effect acknowledgements
and two seconds of uptime progress passed. Head errors stayed at the startup
baseline 1, drops 0; no clearing or reset to obtain a clean counter. No RAM
diagnostic reads were used in this run. Left running the same Polish falling
sentence, 100 ms/row, ceiling 70, pulse on, unpaused. Stronger-pulse optical
assessment pending. Original all-five optical confirmation is retained.

Newest head image/hash: `build/strip-text-pulse-prepared/manifest.json`.
New backups/readback/status/live evidence:
`build/board-readback/strip-five-pulse-20261016/summary.json`. Earlier frozen
candidate and all five initial program records are preserved. No CAD/stock edits.


## Six-scene PWM simulation, MCU budget and PC soundtrack (2026-10-16)

User requested simulation before any further five-board flashing. Added a
native 40x8 PWM show with Silk ribbon, Ripple garden, Ember trails, Five lanterns,
Light ladder and Daisy chain. Independent 0–100 pixel levels, integer synthesis,
38.4-second exact loop with 960 ms crossfades. `make renderer-pwm` opens it;
N selects next scene, A auto, Space pause, +/- brightness. Visible native
window was inspected; complete recordings and six-scene sheet are in
`build/pwm-show/`. Desktop floating/resize attempts failed; preview remains
in its ordinary tiled window. No unrelated windows were closed or modified.

A separate full MCU candidate builds via `make pwm-show-images`: head plus
four addressed receivers, each running the same integer core locally from
14-byte phase/scene/brightness packets (new magic 0xb6, rejecting text 0xa6).
No full 320-pixel buffer on the head. Link/batch/scan limitations are in
`firmware/pwm-show/README.md`. Actual WCH link results: head 11,116 flash /
1,620 RAM including 256 stack (428 RAM free); receivers 7,712 / 1,164 (884 free).
Foreground max 128 plus retained 48 ISR allowance = 176 / 256 stack; runtime
high-water and real-time throughput unmeasured. Pattern/packet/head/receiver
host tests, eight renderer tests, all firmware variants and head clangd passed.
Exact sizes/hashes/stack evidence: `build/pwm-show/resources.json`.

User then requested PC music/voice synchronization in a bell-led progressive
style. Prepared original music and original complete-phrase narration using
local CPU Supertonic M1, native speed 0.95, no waveform stretching. Source
`config/pwm-show-audio.json` and `scripts/pwm_show_audio.py`; earlier speech
config/ROCm untouched. Audio DAC presentation time drives absolute simulator
phase; Space pauses audio and light. One full 38.4-second PC playback completed
without audio warnings; 38 scene/tick checks cover all six scenes. A standalone
narrated MP4 is `build/pwm-show/pwm-show-narrated.mp4`; replay with
`.tools/native-tts/bin/python scripts/pwm_show_audio.py`, optional `--loop`.
PC audio is not a claim of measured physical board synchronization.

No MCU, serial, probe, power, option-byte or CAD operation occurred in this
PWM-show task. Real boards retain the previously verified falling-text firmware
and stronger pulse; picocom was left alone. New PWM images remain unflashed.


## PWM show head programmed only (2026-10-16)

User explicitly requested flashing the head (position 1 from left). Identified
UUID d7-50-ab-cd-41-1c-bd-ff and preserved two matching full 16 KiB working
flash backups before writing. All 11,116 frozen head-image bytes matched
full-flash readback. All option bytes preserved; no programmer power or
separate erase commands. SWIO banner and complete status passed: 40 ms,
unpaused, requested brightness 100, UART errors 0/drops 0.

Positions 2..5 retain the previously verified text receivers (0xa6). They reject
new PWM phase packets (0xb6), so the PWM head cannot complete its four-receiver
batch and advance the show yet. No full-chain/optical PWM pass is claimed.
Matching PWM receiver images are built but unflashed. PC music/narration still
targets the simulator, not the physical chain. The earlier complete text/pulse
state is no longer active across the entire chain; original images/readbacks
and the immediately preceding working head are preserved.

Evidence/backups: `build/board-readback/pwm-show-20261016/summary.json` and
`position-1/`. SWIO remains on position 1; no terminal left open. No CAD or
inventory changes. This supersedes the earlier all-PWM-images-unflashed status
only for the head.


## PWM receiver position 2 programmed (2026-10-16)

On the user's request to flash the next board, the probe UUID
`d7-56-ab-cd-41-22-bd-ff` identified recorded position 2 from the left.
Programmed the matching PWM-show tile1 receiver (I2C 0x32): all 7,712 image
bytes matched full-flash readback after two identical full 16 KiB backups.
Option bytes and programmer power were preserved. SWIO startup and complete
PWM receiver status reply passed; terminal closed afterward.

Positions 1 and 2 now run PWM-show firmware; positions 3..5 still require their
matching receiver updates before the complete show can advance and be tested.
PC music/narration remains synchronized to the simulator only.
Evidence/backups: `build/board-readback/pwm-show-20261016/position-2/`;
current deployment summary: `build/board-readback/pwm-show-20261016/summary.json`.
SWIO is on position 2. This supersedes the preceding head-only deployment status.


## PWM receiver position 3 programmed (2026-10-16)

Probe UUID `d7-69-ab-cd-41-35-bd-ff` matched recorded position 3 from the left.
Flashed matching PWM-show tile2 receiver (I2C 0x33) after two identical full
16 KiB backups. All 7,712 image bytes matched full-flash readback; options and
programmer power preserved. SWIO startup and complete receiver status passed;
terminal closed. Evidence: `build/board-readback/pwm-show-20261016/position-3/`.
Positions 1..3 now run PWM-show; positions 4..5 still require updates before
full-chain testing. PC audio remains simulator-only. SWIO is on position 3.
This supersedes the preceding deployment status.


## PWM receiver position 4 programmed (2026-10-16)

Probe UUID `d7-73-ab-cd-41-3f-bd-ff` matched recorded position 4 from the left.
Flashed matching PWM-show tile3 receiver (I2C 0x34) after two identical full
16 KiB backups. All 7,712 image bytes matched full-flash readback. Existing
option bytes (USER ff) and programmer power were preserved. SWIO startup and
complete receiver status passed; terminal closed. Evidence:
`build/board-readback/pwm-show-20261016/position-4/`.
Positions 1..4 now run PWM-show; position 5 still requires its update before
full-chain testing. PC audio remains simulator-only. SWIO is on position 4.
This supersedes the preceding deployment status.


## All five PWM-show images programmed (2026-10-16)

Final probe UUID `d7-6e-ab-cd-41-3a-bd-ff` matched recorded position 5.
Flashed matching tile4 PWM receiver (I2C 0x35) after two identical full 16 KiB
backups; all 7,712 bytes matched full-flash readback. Option bytes and programmer
power preserved. SWIO startup/status passed and terminal closed. Evidence:
`build/board-readback/pwm-show-20261016/position-5/` and parent `summary.json`.
All five positions now have matching PWM-show firmware, superseding the prior
mixed deployment. Full-chain visual confirmation is pending. Picocom was found
open and left undisturbed; no new UART traffic pass is claimed. PC audio still
drives only the simulator. SWIO remains on rightmost position 5.


## Five-tile PWM show visually confirmed (2026-10-16)

After all five matching PWM-show images were programmed and readback/startup
verified, the user confirmed: "works." This records a user-observed full-chain
visual pass, superseding pending visual confirmation. No instrumented PWM,
current, optical timing or runtime stack measurement was performed; no new
UART traffic test is claimed. PC music/narration still targets the simulator.
Evidence: `build/board-readback/pwm-show-20261016/summary.json`.


## Physical PWM audio synchronization (2026-10-16)

User requested music and narration on the physical chain and connected SWIO
to the head, with the UART free. Head UUID d7-50-ab-cd-41-1c-bd-ff received
an application-only update after two matching full 16 KiB backups. All 11,372
image bytes matched readback; options/power preserved; SWIO startup/status
passed. Four PWM receivers remain unchanged. RAM is 1,620 bytes including the
256-byte stack, conservative maximum stack remains 176 bytes. Host tests pass,
including absolute tick parsing/rejection, four-receiver acknowledgements and
transfer retry. No scan/PWM driver or CAD changes.

Launch from the repository root, after closing picocom:
`.tools/native-tts/bin/python scripts/pwm_board_audio.py` (add `--loop` to repeat).
UART auto-detects the WCH-Link serial port; `--port` overrides it. Ctrl+C returns
to the standalone automatic show and restores tty settings. PC DAC presentation
time drives UART `k 0..959`; the head acknowledges only after all four receivers
CRC-acknowledge. Late host frames are skipped, preventing accumulated clock
drift. PC speakers provide the score and complete-phrase narration.

User confirmed spoken scenes match all five physical tiles ("yep"). First
cycle: no audio warnings, UART errors stayed at baseline 2, drops 0; phase ACK
mean 16.05 ms, max 24.68 ms. Audio backend completion arrived before final DAC
samples, so the launcher now continues to the final presentation tick; final
cycle result is recorded in `build/board-readback/pwm-audio-20261016/summary.json`.
This supersedes simulator-only audio status. Bus/scan/OS latency is present;
no instrumented optical timing or PWM waveform measurement is claimed.


Final physical audio run passed: all 960 ticks acknowledged; no audio warnings,
UART errors unchanged at 2 and drops at 0. Phase ACK mean 16.06 ms,
max 24.22 ms. User confirmed scene alignment. Tiles returned
to standalone automatic show; serial released. Evidence:
`build/board-readback/pwm-audio-20261016/summary.json`.


## General firmware R3 — verified five-board chain (2026-10-17)

`v3-general` provides binary UART routing, RAM/flash loading, timed text/bitmap/
brightness tracks, scheduled RAM segment replacement, queued raw frames and PC
audio synchronization. I2C carries the shared clock. All five role images have
matching physical readbacks and preserved backups/options. All five passed
3008-byte saved-show restart/readback checks. The chain now runs the228-byte
looping demo from safe A/B flash at brightness100; the serial port is released.
Normal content updates use UART without reflashing or moving SWIO.

The user resoldered the intermittent head S5 connection and reported it appears
okay. Final38.4-second narrated PWM streaming passed at230400/18fps with0late/
skipped frames,0added UART errors/drops and0audio warnings;15ACK timeouts were
recovered. Initial reconnect timeout and unsuccessful faster runs remain in the
evidence.460800 failed qualification;921600 remains unqualified. Runtime stack
high-water, rails/current/waveforms and optical timing skew remain unmeasured.

Build `make general-images STACK_USAGE=1`; test `make general-test`; preview
`make general-preview`. Current `make test` passed, including43 general Python
tests and native clock/display/flash register checks. Usage/launch commands:
`firmware/general/README.txt`. Protocol: `docs/general-firmware-protocol.txt`.
Review: `docs/general-firmware-review-20261017.txt`. Physical results/limitations:
`docs/general-firmware-hardware-20261017.txt`. Summary/backups:
`build/board-readback/general-20261017/summary.json` and `revision3/`.

Frozen images/source hashes/memory: `build/general/review-candidate/manifest.json`.
Head13272 and receivers13284 image bytes;2036/2048 RAM includes256 stack, with
compiler combined-path assessment236/256. Every role reports1472 safe-program
bytes or3008 capacity-program bytes. Default/archived variants remain available;
builds do not program boards.

The user superseded the earlier manual model-switch gate by requesting automatic
Astra review/completion. Scoped Astra reviews approved the corrected native R3
and host changes before final qualification. Standing UUID, matching full backups,
programmed readback, option-byte and programmer-power safeguards still apply.

## V3.2 initial study — 17 October 2026

A separate QSOP24/CH32V006E8R6 study is saved in
[hw/ledkiv3.2](../hw/ledkiv3.2/README.md).49.6mm square/6.2mm pixels,
west-to-east and south-to-north UART, common I2C, separate LED blanking.
159footprints,4layers,0tracks/vias/zones. Native ERC0/physicalDRC0/parity0/
ignored0;307unconnected items are intentional before routing. All26v3.1
authored source hashes are unchanged. Accepted v3.1 and current v3 firmware
remain the existing baselines. [Study](v3_2-study.txt) and
[network downloader feasibility](v3_2-network-update.txt) state the limits.
Factory BOOT is USART1; custom I2C needs initial SWIO installation and new
loader implementation/qualification. No flash, option-byte, stock or order
change occurred. The reusable workflow report is in the electronics repo.


## V3.2 routing completed — 17 October 2026

[The v3.2 project](../hw/ledkiv3.2/README.md) now contains the routed QSOP24
prototype: all159 placements preserved,2015segments,299ordinarytented vias.
ERC/DRC/opens/parity/ignored0; independent76/76nets connected. FrontVCC
reinforcement and exact reviewed In1exceptions are recorded in
[routing and limitations](v3_2-routing.txt). Checked exports are in
hw/ledkiv3.2/exports/prototype/. Physical qualification and new firmware/loader
remain pending. The complete human-routing start point is preserved at
archive/hw/ledkiv3.2-unrouted-20261017/. v3.1 and active firmware were untouched
by this CAD work; no purchase, inventory, device, commit or push operation.


## V3.2 accepted routed milestone and manual editing — 17 October 2026

The user accepted [v3_2-routed-20261017](milestones/v3_2-routed-20261017.txt) as the
routed CAD milestone. Source, dependencies, check contracts and exports are
frozen at archive/hw/ledkiv3.2-routed-milestone-20261017/. The editable main
project remains hw/ledkiv3.2/ledkiv3_2.kicad_pro; the user will make manual
component/placement/routing changes there. Do not replace those edits with the
archive or route autonomously. Milestone checks apply to the frozen source;
recheck changes and review baseline-specific contracts before a new handoff.
The original unrouted checkpoint is preserved separately. No CAD bytes changed
when recording this milestone.


## V3.2 AISLER manufacturing review — 17 October 2026

The current bare-PCB quote is EUR62.42 for12 at displayed19%VAT; shipping and
destination tax remain unconfirmed. [Supplier review](v3_2-aisler-20261017.txt)
records the observed settings and three differences against current AISLER
rules: tented vias unsupported,0.250mm copper-edge clearance below0.300mm,
and one0.265685mm drill gap below0.300mm. Existing DRC0 does not certify this
supplier profile. No CAD or order changes; manual editing remains with the user.


## V3.1 PCB purchased — 17 October 2026

The user confirmed purchase/payment of the prepared5-board v3.1 batch
("kupiona możesz zapisać"). Item ledkiv3_1-gerbers_Y9, prototypeY9-10656422A.
This supersedes its earlier cart-only/unpaid status. Last observed checkout:
PCBUSD2.00 + Global Standard Direct LineUSD1.50 + displayed customs/taxesUSD4.30
= USD7.80. Invoice, actual paid amount and supplier order number were not
independently inspected. Delivery and physical receipt remain pending; no shelf
stock credited. Accepted CAD/export hashes unchanged. No agent order/payment.
[Purchase/process record](v3_1-jlc-20261017.txt) and
[structured evidence](../config/purchase/v3_1-jlc-checkout-20261017.json) retain
user-report provenance, default Plugged, blank remark and unverified supplier
engineering/production status.

## V3.2 current main version accepted — 17 October 2026

The user accepted the current board shown in the
[first robot / now comparison](https://psym.pl/zobaczadas/v3.2-comparison/)
as the main v3.2 version. The live project remains
`hw/ledkiv3.2/ledkiv3_2.kicad_pro`; the accepted saved PCB SHA256 is
`1eff241854ad1150e82d46467debfce957d2cee92d66f088e6502791e266cd22`.
The [acceptance record](milestones/v3_2-main-20261017.txt) and frozen complete
CAD context at `archive/hw/ledkiv3.2-main-milestone-20261017/` preserve this state.
There are 1,490 segments, 299 vias and 159 footprints. All 76 nets remain
connected; native checks have zero errors, opens, parity or ignored findings
and retain the existing `/ADDR0` dangling-track warning. Earlier checks of
the unchanged schematic and circuit retain their recorded scope.

The original robot milestone and unrouted checkpoint remain untouched.
Acceptance did not change CAD bytes. Existing fabrication exports still refer
to the first robot milestone; physical qualification and V006 firmware/loader
remain pending. No export, hardware, inventory, purchase, commit or push action.

## V3.2 five-board fabrication derivative — 17 October 2026

[Handoff](v3_2-fabrication-20261017.txt) and
[assembly plan](../hw/ledkiv3.2/ASSEMBLY.txt) describe the current checked
five-board prototype. The accepted main milestone remains frozen; the working
derivative removes its dangling ADDR0 stub, restores Q3/R25 branch widths and
selects six exact passive MPNs. PCB SHA256:
`bddc92364a1d159535429667e7dee44b1b360e75906d5b59d24bad622b669859`.
Fresh ERC/DRC/opens/parity/ignored0; independent76/76nets.1,489segments,
299fixedvias,159fixedplacements. `fabrication.json` identifies this derivative;
`baseline.json` continues to identify its accepted parent.

The new export is `hw/ledkiv3.2/exports/fabrication-20261017-r2/`, with Gerbers,
drills, paste, exact five-board BOM, stock/shortfall snapshot, assembly maps,
schematic, STEP, sources and checks/hashes. One147SMT plus four145SMT tiles
requires727SMT; headers are optional. Existing v3/v4.1 holds and the separate
new five-v3.1 batch remain distinct; no parts reserved/consumed or purchased.

Current logged-in JLCONE parameter quote: USD2automatic offer(no coupon)+
USD1.50GlobalStandard shipping toPoland, before checkout charges. The user approved the exact
Gerber upload to JLCONE; it is saved under Projects > Quotes and correctly
detected at4layers/49.6mm square. Four copper, two mask, two silk, outline and
drills were recognized; top/bottom reference thumbnails were inspected. No
cart/order/payment occurred. The default Plugged process still needs supplier
engineering confirmation:92vias are below the published ink-plug spacing in a
conservative audit; Tented is automatically upgraded toPlugged. Status is
HOLD_PROCESS, not a final order-ready
USD3.50 delivered price. [Quote record](../config/purchase/v3_2-jlc-quote-20261017.json).
V006 firmware/loader and physical qualification remain future work.

V3.2 DFM follow-up: [review](v3_2-dfm-20261017.txt). Currentr2 also corrects
two J2 pin1-marker silk lines; all copper/vias/pads/placements are preserved.
Its corrected GerberZIP has not been uploaded: automatic approval requires a
new approval for the changed hash. The earlier checked upload/preview remains
saved. Both corrected-upload and separate support-question permissions are
pending. SupplierDFM is not all-pass; measured findings/raw reports are retained.

V3.2 final prototype decision: the user approved the correctedr2Gerber upload,
which is complete and previewed. Correctly detected4layers/49.6mm/qty5;
quote2USD+1.50USDGlobalStandardDirectLine toPoland, before checkout charges.
User chose default fabrication options instead of the support question; no
message was sent. This supersedes the earlier process/upload holds for this
five-board prototype package. Current checked export is fabrication-20261017-r2.
Raw vendorDFM findings, unconfirmed production files and physical qualification
remain explicit limits. No cart/order/payment/stock/programming action.

## V3.2 correct Gerbers uploaded and cart saved — 17 October 2026

The user explicitly requested the correct Gerber upload again. The current
checkedr2ZIP(SHA256c25f94e4ac97441caf86c49dc6ff55ba31d15a033d6fac6600037cd6acc220df)
was reverified against current CAD and uploaded through preferred local CDP.
JLCONE detected4layers/49.6x49.6mm/qty5. Saved cart item
`ledkiv3_2-gerbers_Y10`, prototype`Y10-10656422A`, PCBUSD2.00, default
fabrication options retained. This supersedes the earlier quote-only/no-cart
status. No checkout/order/payment or support message. Debugging closed; normal
JLCONE restored. Evidence: build/hardware/v3_2-fabrication-20261017/reupload/summary.json
and cart-proof.json; current CAD and checked export bytes are unchanged.

## V3.2 fifteen-board split cart for user payment — 17 October 2026

The user selected 5+10 bare boards and asked to leave the cart for manual
payment. Original `ledkiv3_2-gerbers_Y10` remains five boards at USD2;
`ledkiv3_2-gerbers_Y11` is ten boards at USD8, using the same checked r2 ZIP.
Combined Global Standard Direct Line shipping remains USD1.50 at 0.26kg.
PRE_CAL checkout displays USD6.14 duties/taxes and USD17.64 Grand Total;
no later random discount is assumed. No Continue/Submit Order/payment action.

The USD25 engineering fee starts at a single batch of fifteen. Actual 5+5+5
cart pricing was USD2+8+8, with USD1.50 shipping; temporary third item Y12 was
removed. The shipping offer permits three uses monthly and currently shows
one remaining. [Strategy](v3_2-order-strategy-20261017.txt) and
[record](../config/purchase/v3_2-quantity-strategy-20261017.json) retain evidence.
This supersedes the earlier five-board-only cart choice, while the checked
assembly package/stock snapshot still covers five boards. No parts reservation,
CAD or firmware change. V006 firmware and physical tile qualification remain
pending; additional bare boards are prototype stock.

## V3.2 order confirmed by user — 17 October 2026

The user confirmed ordering the prepared15-board5+10 batch and requested
updating the Electronics repository. This supersedes the earlier cart-only
status. [Order record](../config/purchase/v3_2-jlc-order-20261017.json) keeps
direct-user-report provenance; last checkout preview USD17.64 is not a verified
paid amount. Order number, invoice, production/dispatch and delivery remain
unverified. No agent order/payment or physical stock credit. Correct r2 Gerber
and CAD hashes are unchanged.

The Electronics repository already records an Ali purchase of50V006QSOP24,
200AO3414,200AO3415 and2000candidate orangeLEDs, all awaiting receipt. This
covers candidate quantities for15v3.2+5v3.1 without another semiconductor/LED
purchase, conditional on receipt and qualification. TME resistors are deferred
about3weeks, not ordered. Combined resistor floors:320x1k0603,480x10k0603,
160x33R1%0805,70x1k0805 and15x47k0805. Exact LED need1280/free360/short920;
the ordered candidate LED is not exact qualified XL-2012UOC stock.

[Requirements](../config/purchase/v3_2-assembly-requirements-20261017.csv) and
[next work](v3_2-order-and-bringup.txt) cover V006 firmware, incoming-part
substitution review, one-tile bring-up,2x2 and then3x5. Shared v3/v4.1 holds
are preserved; no new reservations/consumption or firmware/CAD changes.

## Incoming-board parts reserved — 17 October 2026

The user authorized reservations for **5 v4-family boards (the existing v4.1
batch), 5 v3.1 and 15 v3.2**. This supersedes the earlier no-new-reservations
status; the earlier requirements worksheet remains a pre-reservation snapshot.
The canonical [reservation record](../config/board-reservations.json) references
live shelf/pending-order ledger entries and must not be deducted again.
Existing v4.1 shelf allocations and TME 35700057 holds were reused unchanged.

New shelf allocations cover five v3.1 V003s, twenty v3.1/v3.2 HC138 decoders,
320 exact XL-2012UOC for v3.1, the stocked capacitors and bias/I2C resistors.
One pull-up pair per revision bus is assumed. No additional optional SWIO
headers are held for v3.1/v3.2; the bare-pad method remains available.

The already confirmed AliExpress purchase was imported once into shared
parts-incoming-other.csv with original source/hash. All four lots remain
pending with zero on-hand credit. Holds: 15 CH32V006E8R6/QSOP24 for v3.2,
160 AO3414 and 160 AO3415 across v3.1/v3.2, and 960 candidate
GH-C170KFKT-08T LEDs for v3.2. MOSFET/LED identities and substitutions remain
unqualified; reservation does not approve their use as baseline CAD parts.
The last 40 exact LEDs remain free rather than mixing different unqualified
types inside one v3.2 tile.

After all holds, conservative free shelf quantities include 33 V003s,
23 HC138s, 40 exact LEDs, 175 each of the stocked 100nF/10uF capacitors,
930 stocked 10k/0805 and 926 stocked 4.7k/0805 resistors. The confirmed
ten-piece V006F8P6/V007E8R6/X033F8P6 lots remain unallocated. Pending
unreserved quantities include 35 V006E8R6, 40 of each MOSFET and 1040
candidate LEDs; these are not free physical stock.

Still unallocated/unpurchased: 320x1k/0603, 480x10k/0603,
160x33ohm1%/0805, 70x1k/0805 and 15x47k/0805. Deferred TME resistor
procurement remains a proposal. Wire, supplies, screws and printed mechanics
lack identified counted lots and are not claimed reserved.

The shared reporter now includes the four pending lots with owner,
qualification and provenance. Checked exact batch totals, unchanged receipt/
stock balances, duplicate-hold avoidance, missing quantities, invalid-ledger
rejection and partial-receipt accounting. Evidence/backups:
build/inventory/incoming-boards-20261017/. Legacy v3 estimated consumption
and hard holds were preserved without reconciliation. No receipt,
consumption, new purchase, CAD/firmware change, commit or push.
