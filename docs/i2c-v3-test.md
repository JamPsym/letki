# Test I2C dwóch płytek v3

Wynik 14 października 2026: 20 kolejnych fizycznych odpowiedzi CRC przeszło,
bez błędów kontrolera. Automatyczne liczenie włączone; szczegóły i ograniczenia
w sekcji wyniku poniżej. Jeden WCH-LinkE wystarczył.

| Płytka | Rola | Obraz |
| --- | --- | --- |
| Pierwsza, UUID `d7-73-ab-cd-41-3f-bd-ff` | master/kontroler | `build/interface-demo-controller/letki.bin` |
| Druga, UUID `d7-6e-ab-cd-41-3a-bd-ff` | odbiornik, adres `0x32` | `build/interface-demo-target/letki.bin` |

Budowanie obu ról: `make interface-demos -j4`. Programowanie jest osobnym
krokiem: przed każdą płytką sprawdzić UUID i zachować dwa zgodne odczyty całego
flash oraz option bytes. Najpierw wgrać odbiornik, potem master. Od 2026-10-14 użytkownik udzielił stałej zgody na firmware i testy obu
zidentyfikowanych płytek v3; nie pytać ponownie przy kolejnym obrazie testowym. Obie płytki mają PD7 jako GPIO.
Zachować istniejące option bytes i zasilanie programatora.

Aktualizacja 2026-10-14: użytkownik potwierdził wlutowanie **R11/R12 na lewej,
pierwszej płytce** (`d7-73-ab-cd-41-3f-bd-ff`). Jedna para obsługuje wspólną
magistralę obu płytek; prawej pary nie trzeba dodawać do tej próby. Wartości:

- **R11: 4,7 kΩ, SCL → VCC.**
- **R12: 4,7 kΩ, SDA → VCC.**

Połączenia brzegowe są wlutowane; fizyczny UART przez oba moduły przeszedł
20 sprawdzonych pakietów. Użytkownik potwierdził wspólne zasilanie WCH-LinkE
3V3/GND. I2C następnie przeszło 20 kolejnych odpowiedzi CRC; patrz wynik poniżej. Łączymy SDA z SDA
(J1/J3 pin 3, PC1), SCL z SCL (pin 4, PC2) i GND z GND (pin 6/7).
Sprawdzić brak zwarć i ciągłość po lutowaniu. Obie płytki muszą mieć zasilanie;
układ jednego wspólnego źródła trzeba ustalić przed próbą. Sam przewód SWIO
nie zasila odbiornika. Na oryginalnym v3 zachować naprawę GND C1–C3.

Po uruchomieniu odbiornika uruchomić master. Master automatycznie wysyła
kolejny licznik co sekundę przy 100 kHz i sprawdza odpowiedź CRC. Nie jest
potrzebne połączenie UART ani drugi programator. WCH-LinkE zostaje przy masterze;
odbiornik działa samodzielnie.

Od frontu, strony LED:

- Górny lewy piksel: firmware działa.
- Druga kolumna: jeden górny piksel oznacza master, dwa oznaczają odbiornik.
- Pierwsza kolumna, trzeci wiersz: była udana transmisja.
- Pierwsza kolumna, czwarty wiersz: wystąpił błąd od startu/zmiany roli.
- Dwa dolne wiersze: ostatni poprawny licznik, najmłodszy bit od lewej.

Na obu matrycach dolne wiersze powinny zmieniać się zgodnie. Po błędzie
ostatni poprawny licznik pozostaje; wskaźnik błędu nie gaśnie sam.
Zapisać zgodność liczników oraz logi przed wyzerowaniem statystyk.

Opcjonalne logi przez SWIO: `python3 scripts/swio_terminal.py`. Otwarcie
terminala restartuje podłączony master; jego rola wraca do kontrolera i tryb
automatyczny jest włączony. Polecenia wysyłać z Enter:

```text
status
auto off
send 42
auto on
```

Oczekiwana odpowiedź mastera: `I2C OK counter=42 reason=reply CRC`.
`I2C ERR ... reason=NACK/timeout/bus error` oznacza nieudaną próbę.
Odbiornik pokazuje licznik dopiero po poprawnym pakiecie; master dopiero po
potwierdzeniu odpowiedzi. Nie uznawać samych świecących wskaźników roli za test I2C.

Test akceptacyjny: przynajmniej 20 kolejnych poprawnych potwierdzeń CRC,
zgodne liczniki na obu matrycach, bez nowych błędów I2C i bez błędów/dropów
UART, jeśli UART jest używany. Zachować UUID, hash obu obrazów, sposób
zasilania, zamontowane podciąganie i surowe logi. Pomiary elektryczne pozostają
osobnym sprawdzeniem; wyniki hosta nie potwierdzają fizycznej magistrali.

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
