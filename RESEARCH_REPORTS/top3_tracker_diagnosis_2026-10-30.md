# Top-3 Ranking Outcome Tracker — diagnoza i minimalna naprawa

Kontekst: `6c9bb76`, cutoff analizy `2026-10-30 15:00 UTC` (początek świecy), zapis trackera `2026-10-30 16:10:41.465134 UTC`. Stan dojrzałości poniżej dotyczy chwili tego zapisu. Trading DISABLED. Nie uruchamiano nowego skanu ani transakcji.

## Dane i dowody

- [Pełny audyt JSON](top3_tracker_audit_2026-10-30.json): wszystkie 52 obserwacje, ceny i pochodzenie dostępnych danych, powody nierozliczenia.
- [Tabela CSV](top3_tracker_audit_2026-10-30.csv): po jednym wierszu na obserwację, również każda z 43 nierozliczonych.
- [Dowód integralności i publicznego mapowania XLM](top3_tracker_integrity_2026-10-30.json): hashe tabel, SHA-256 produkcyjnego pliku SQLite, wynik dwóch rozliczeń na kopii oraz klucze odpowiedzi Kraken.

Audyt czyta produkcyjny SQLite w transakcji tylko do odczytu. Dostępność lokalnych świec została sprawdzona podczas audytu i jest oddzielona od zamrożonych referencji zapisanych przy skanie. Obecność ceny w dzisiejszym archiwum nie dowodzi, że była dostępna podczas historycznego zapisu. Nie użyto jej do uzupełniania historycznych nulli.

## Podział obserwacji

| Data skanu UTC | Obserwacje | Ukończone +24h | Niedojrzałe | Dojrzałe z brakami immutable T0 | Brak T0 aktywa | Brak BTC T0 |
|---|---:|---:|---:|---:|---:|---:|
| 2026-10-24 | 9 | 9 | 0 | 0 | 0 | 0 |
| 2026-10-25 | 9 | 0 | 0 | 9 | 0 | 9 |
| 2026-10-26 | 9 | 0 | 0 | 9 | 9 | 9 |
| 2026-10-28 | 7 | 0 | 0 | 7 | 7 | 7 |
| 2026-10-29 | 9 | 0 | 9 | 0 | 0 | 0 |
| 2026-10-30 | 9 | 0 | 9 | 0 | 0 | 9 |
| **Razem** | **52** | **9** | **18** | **25** | **16** | **34** |

Tożsamości kontrolne: `52 = 9 + 18 + 25`, `43 pending = 18 + 25`, `34 reference_missing = 25 dojrzałych + 9 niedojrzałych`. Nie ma dojrzałej nierozliczonej obserwacji z kompletnym zamrożonym T0 aktywa i BTC. Żadna z tych liczb nie jest liczbą niezależnych sygnałów/klastrów.

Wszystkie 25 dojrzałych obserwacji blokuje null `btc_reference_price`; 16 blokuje również null `reference_price`. Poza PENDLE lokalne okna aktywa i BTC dla tych obserwacji są dziś kompletne. PENDLE, REVERSAL #2 z 25 października, ma dodatkowo 19 brakujących/odrzuconych godzin w oknie, w tym świecę ceny T+24h; ich dokładne timestampy są w JSON. Nawet pobranie tych godzin nie naprawiłoby jego immutable BTC T0.

Dziewięć obserwacji z 29 października ma oba zamrożone T0, ale termin ceny +24h przypada dopiero 30 października o **17:00 UTC**. W chwili skanu 16:10 było za wcześnie, a lokalne archiwum nie zawierało końcowej świecy 16:00–17:00. Dziewięć obserwacji z 30 października osiągnie termin 31 października o **16:00 UTC**; brak cen przyszłych jest prawidłowy. Te ostatnie mają dodatkowo brak immutable BTC T0, którego upływ czasu nie naprawi.

Istniejąca definicja +24h liczy od `price_timestamp` (zamknięcie poprzedniej pełnej świecy godzinowej), a nie od sekundowego czasu skanu. CSV/JSON pokazują obie daty i obie flagi dojrzałości. Dla skanu z 29 października pełne 24h czasu ściennego upłynie o 17:50:21 UTC; nie zmieniono istniejącej semantyki pomiaru.

## Przyczyna

1. `track_daily` zapisuje T0 z lokalnego archiwum godzinowego i trwale pozostawia null przy braku referencji. `mature` słusznie nie uzupełnia tych nulli po fakcie.
2. W `orchestrate` Top-3 był uruchamiany **przed** `extend_handoff`, które dopiero odświeża godzinowe BTC przez `refresh_hourly_btc`. Standardowy skan dla BTC korzysta z osobnego pliku operacyjnego 15m; nie gwarantuje aktualności `XBTUSD_1H.csv`. Przy Top-3 brakowało więc bieżącego BTC T0, mimo że późniejszy hook V2 mógł już dysponować tą świecą. Zamrożone braki potwierdza ledger; dokładnego stanu dawnych plików nie da się odtworzyć wyłącznie z ich obecnej zawartości.
3. Skany 26 i 28 października przekroczyły granicę pełnej godziny po przygotowaniu pakietu: odpowiednio 17:57 → 18:00 i 05:58 → 06:00 UTC. T0 wymagało nowszej zamkniętej godziny niż archiwum przygotowane wcześniej. Stąd również null T0 aktywów. Nie cofnięto ich T0 do wcześniejszej godziny.
4. Stare agregaty podawały jedynie `price_pending` i `reference_missing` bez rozdzielenia dojrzałości. Brak przyszłego endpointu nie powinien być interpretowany jako zaległy wynik.

## XLM

Historyczny pakiet ma `LIVE_PRICE_UNAVAILABLE`, a nie `LIVE_PRICE_STALE`: cena, timestamp i wiek live są null. W trackerze wszystkie trzy obserwacje XLM mają natomiast poprawnie zamrożone **T0 aktywa = 0.17257**, z godzinowej świecy zaczynającej się o 15:00. Brak quote live nie jest brakiem ceny wejściowej trackera.

Jednoznaczny błąd mapowania: stare `_canonical_pair('XLMUSD')` dawało `LMUSD`, a `_canonical_pair('XXLMZUSD')` dawało `XLMUSD`; klucze nie pasowały. Publiczne `Ticker` i `AssetPairs`, odczytane podczas audytu bez uwierzytelnienia, potwierdziły klucz `XXLMZUSD` i `altname=XLMUSD`, `wsname=XLM/USD`. Poprawka usuwa techniczny prefiks X tylko z legacy kluczy zakończonych `ZUSD`; zachowuje rzeczywiste X w nowoczesnych symbolach. Usunięto także zgadywanie pary na podstawie pojedynczego obcego wyniku. Historyczny pakiet/quote pozostawiono bez zmian.

## Minimalne zmiany

- Istniejący publiczny refresh godzinowego BTC uruchamia się także **przed** prospektywnym zapisem Top-3, wyłącznie w bieżącym trybie online. Nie zmieniono T0, rankingów ani zasad rozliczeń. Błąd odświeżenia jest widoczny w health; lokalna walidacja nadal odrzuca niedostępne/niewiarygodne referencje.
- Dodano rozdzielenie liczników niedojrzałych, dojrzałych bez immutable T0 i dojrzałych oczekujących na wynik przy obecnym T0; dotychczasowe agregaty zwrotów nie zmieniły definicji.
- Dodano narzędzie diagnostyczne tylko do odczytu i poprawiono mapowanie XLM.

**Odzyskane wyniki +24h: 0.** Brakujących immutable T0 nie można naprawić zgodnie z wymaganiami. Poprawka zapobiega przyczynie w przyszłych zapisach i ujawnia prawidłowy podział pending; nie stanowi historycznego backfillu.

## Weryfikacja

`68 passed` dla:

```
.venv-research/bin/python -m pytest -q \
  tests/test_top3_ranking_tracker.py tests/test_live_price_reference.py \
  tests/test_daily_quant_system.py tests/test_daily_prerequisites.py \
  tests/test_market_memory_opportunity.py tests/test_relative_strength_radar.py
```

Przypadki obejmują niedojrzałość, kompletne rozliczenie z benchmarkiem, brak T0 aktywa/BTC, brak końcowej ceny aktywa/BTC, luki i wadliwe świece, zakaz późniejszego uzupełniania T0, idempotencję, blokady immutable, zgodność liczników z rekordami, kolejność refresh → capture, tryb offline i błąd odświeżenia oraz poprawne mapowanie XLM bez zgadywania.

Na spójnej kopii rzeczywistego SQLite uruchomiono `mature` dwukrotnie na czas badanego skanu. Hashe wszystkich trzech tabel pozostały identyczne, wszystkie **9 ukończonych payloadów PRICE_24H** pozostało identycznych, `integrity_check=ok`. Sam produkcyjny plik SQLite zachował identyczny SHA-256. Nie zmieniono historycznych raportów dziennych ani niezwiązanych zmian working tree.

## Ograniczenia

Historyczne null T0 pozostają trwałe. Brak danych po granicy godziny nadal może dać jawny null, zwłaszcza przy przekroczeniu godziny przez skan; nie wprowadzono fallbacku do wcześniejszych świec, estymacji ani pobierania danych przez sam tracker. Niedojrzałe wyniki mogą zostać rozliczone dopiero po terminie i przy pełnym oknie; dziewięć obserwacji z 30 października pozostanie zablokowanych przez BTC T0. Lokalne ledger i archiwa są poza Git; audyt zawiera ich hashe i wyniki inspekcji, nie kopię całego SQLite. Raport dotyczy stanu badanego skanu, a nie bieżącej rekomendacji inwestycyjnej.
