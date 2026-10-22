# Daily Top-3 Ranking Outcome Tracker

Trading DISABLED. This is prospective measurement, not a strategy or an execution engine. Existing ranking functions, ordering, eligibility thresholds and strategy settings are unchanged.

## Integration and persistence

The canonical `./daily` workflow records observations after it builds the existing continuation/reversal opportunity lists. Relative Strength consumes the current successful radar's published candidate order, rather than deriving another ranking. Normal current scans, including `--no-network`, are eligible; explicit `--as-of`, `--reuse-existing-data`, custom/test runners and failed scans do not create prospective observations. No historical backfill is performed. Collection starts on the next eligible daily scan.

The append-only SQLite store is `DATASETS/TOP3_RANKING_OUTCOMES/tracker.sqlite`. It contains:

- `scans`: timestamp, ranking type, regime, availability, and published Top-10 membership, including explicit empty lists.
- `observations`: the first three published entries (or fewer if the list is shorter), with rank, asset, pair, scan timestamp, reference timestamp/price, BTC reference price, regime and source provenance.
- `outcomes`: separate immutable `PRICE_24H` and `NEXT_DAY_RANK` events referencing the observation.

Transactions use an immediate write lock and durable commits. Stable upstream packet timestamp/type identities deduplicate retries; repeated processing never edits stored payloads. New scans with distinct upstream identities create additional observations. Database triggers block updates, deletes and replacement writes. Mature outcomes are inserted once and never revised, including when the market archive is subsequently corrected. Schema and code are versioned; runtime evidence stays outside Git and must be backed up separately. Use SQLite's backup API for a consistent copy.

The latest derived report is `DAILY_REPORTS/TOP3_RANKING_OUTCOMES/latest_summary.json`; it is rebuildable and is allowed to change. The canonical JSON/Markdown daily handoff also contains `TOP3_RANKING_OUTCOME_TRACKER`, including its status and warnings. Tracker failure is reported in this section without blocking the rest of the daily workflow.

## Measurement semantics

References use the **latest completed hourly boundary at scan time**, consistently for asset and BTC. For a scan at 07:05 UTC, the price timestamp is 07:00 and the reference is the 06:00–07:00 candle close. Thus +24h means reference-price-to-reference-price, not exactly 24 hours after the scan's wall-clock timestamp. The price timestamp and scan timestamp are stored separately.

Only existing local Kraken USD hourly CSVs are read. There is no network fetch, forward filling, quote interpolation or BTC benchmark substitution. Missing/invalid references are stored as null with a warning, permanently; an observation is never assigned a reference later using hindsight. Incomplete outcome windows remain pending and can mature on a subsequent daily run when data arrives. Duplicates, off-grid timestamps, nonfinite/nonpositive prices, negative volume and inconsistent OHLC bars are rejected. Source-file SHA-256 and candle references are retained.

Once 24 complete hourly bars after the reference boundary are available and their closing time has passed:

- Asset return: `100 × (24h close / frozen reference − 1)`.
- BTC return: the same calculation using aligned BTC bars and its frozen reference.
- BTC-relative return: `100 × ((1 + asset_return/100) / (1 + BTC_return/100) − 1)`.
- MFE/MAE: maximum high / minimum low of those 24 held candles relative to the frozen reference. The reference candle and candles beyond the horizon are excluded.

Returns and excursions are **gross**. No trade is simulated, so fees, slippage and execution profits are not implied. Both price and rank outcomes can mature independently.

Next-day rank means the **first available scan of that ranking type on the next UTC calendar date**. Unavailable scans are skipped; a successful empty ranking is valid evidence of absence. Membership booleans refer to that next-day endpoint, not uninterrupted membership during the day. Its actual timestamp is stored: the elapsed interval can differ from 24 hours when scan times vary. A missed next date stays pending; a later date is never substituted.

Exact next rank is available only inside the published Top 10. Absence is recorded as `remained_top3=false`, `remained_top10=false`, `rank_censored=true`, and a null exact rank/change. It can mean below Top 10 or not ranked. Rank change is **original rank minus next rank**, so positive means improvement. There is no invented rank 11. The original regime remains attached to the observation regardless of later regime changes.

Chief/RS packet freshness checks are tracker input-integrity guards (at most two hours, no future timestamps), not changes to ranking thresholds. Failed, stale or unavailable RS output is explicitly unavailable, never an empty ranking or a fabricated rank loss. Continuation and reversal still record when RS is unavailable.

## Aggregates

Reports group by ranking type, type/rank, type/regime and type/rank/regime. Each group includes observation and scan counts, completed/pending price and rank counts, missing-reference count, mean return, gross win rate, BTC and relative returns, MFE/MAE, Top-3/Top-10 retention, and mean known rank change with its denominator.

Price means use completed price outcomes only. Retention uses completed rank outcomes only. Rank-change means use exact known next ranks only. Null metrics mean no applicable matured sample, not zero performance. Multiple scans, shared assets and overlapping horizons are dependent; aggregates do not establish predictive edge or provide independent confidence intervals.

## Validation and historical state

Focused checks:

```
.venv-research/bin/python -m pytest -q \
  tests/test_top3_ranking_tracker.py \
  tests/test_daily_quant_system.py \
  tests/test_market_memory_opportunity.py \
  tests/test_relative_strength_radar.py \
  tests/test_daily_prerequisites.py
```

Result: **55 passed**, no warnings. Tests use temporary synthetic archives and databases with network access blocked. They cover immutable/replacement protection, transactional rollback, retry deduplication, concurrent writers, persistence after reopen, exact outcome windows, delayed/gappy data, missing references, BTC-relative arithmetic, next-day membership/censoring, aggregate denominators, source rejection, unchanged input ranking lists and daily failure/replay gates.

No existing historical observations, market data, outcomes or strategy artifacts were rewritten. No production daily scan or retrospective collection was run during implementation. Runtime ledger/report files are ignored by Git. Trading remains DISABLED.
