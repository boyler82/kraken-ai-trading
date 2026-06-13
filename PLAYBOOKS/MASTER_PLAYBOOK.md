# KRAKEN AI TRADING — DAILY OPERATIONS PLAYBOOK

## Cel projektu

Budowa przewagi statystycznej poprzez:

- Research
- Analizę rynku
- Zarządzanie ryzykiem
- Dokumentowanie decyzji
- Ciągłe doskonalenie procesu

Priorytet:

Proces > Wynik pojedynczej transakcji
Przewaga statystyczna > Intuicja
Ochrona kapitału > Maksymalizacja zysku

## STRUKTURA PROJEKTU

analysis/            Raporty i analizy
data/                Dane ze skanów
journal/             Historia decyzji i transakcji
plans/               Aktywne plany transakcyjne
scripts/             Automatyzacje Kraken CLI
templates/           Szablony raportów
DAILY_REPORTS/       Raporty dzienne

RISK_MANAGEMENT.md
STRATEGIES.md
MARKET_THESIS.md
WATCHLIST.md
MACRO.md
LESSONS_LEARNED.md

## CODZIENNY WORKFLOW

1. Uruchom:

scripts/daily_workflow.sh

2. Sprawdź najnowsze dane:

ls -lt data/btc
ls -lt data/market

3. Otwórz najnowszy BTC scan.

4. Otwórz najnowszy market scan.

5. Przekaż dane do ChatGPT.

6. Wygeneruj:
- DAILY_REPORT
- MARKET_THESIS update
- WATCHLIST update
- Trade Plan lub NO TRADE

7. Zapisz decyzję.

## PRZED OTWARCIEM POZYCJI

□ Trend znany
□ Poziomy znane
□ Hipoteza zapisana
□ Stop Loss ustawiony
□ R/R >= 2
□ Ryzyko <= 1%
□ Powód wejścia zapisany
□ Warunek unieważnienia zapisany

Jeżeli choć jeden punkt nie jest spełniony:

NO TRADE

## PO ZAMKNIĘCIU TRANSAKCJI

Aktualizuj:

journal/trades.md
LESSONS_LEARNED.md

Pytania:

- Czy wykonałem plan?
- Czy złamałem zasady?
- Czy decyzja była dobra niezależnie od wyniku?
- Czego nauczył mnie rynek?

## ZŁOTA ZASADA

Codziennie odpowiedz:

"Czy dzisiejsza decyzja zwiększa moją przewagę statystyczną?"

Jeżeli odpowiedź brzmi:

"nie wiem"

to:

NIE OTWIERAJ POZYCJI
EOF

---

# SPECJALNA ZASADA BTC 15M

Główna krótkoterminowa strategia BTC:

BTC 15M Pullback Mean Reversion.

Nie kupuję wybicia na lokalnym szczycie.

Preferowany proces:

1. BTC jest lokalnie wysoko.
2. Czekam na spadek do strefy wartości.
3. Dla obecnego modelu strefa obserwacji to 61500-62000.
4. Szukam reakcji popytowej.
5. Kupuję tylko jeśli Stop Loss jest blisko.
6. Cel podstawowy to powrót do 63000.
7. Minimalne R/R to 2.0.
8. Poziom 64333 to opór obserwacyjny, nie obowiązkowy target.

Jeżeli cena jest w strefie 63000-64000:

NO BUY.

Jeżeli cena jest w środku zakresu:

WAIT.

Jeżeli cena schodzi do 61500-62000 i pojawia się reakcja:

PREPARE PLAN.

Jeżeli cena traci 61500 bez reakcji:

SETUP INVALID.
