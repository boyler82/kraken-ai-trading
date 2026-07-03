# Episode Flow Audit

Date: 2026-07-03

Scope:
- `scripts/rsi2_episode_tracker.py`
- `DAILY_REPORTS/*_rsi2_episode_status.csv`
- `scripts/opportunity_ranking.py`

Goal:
- Trace how oversold episode state moves from the tracker into the daily ranking.
- Confirm where `current_oversold_duration` is set and how it affects recommendation output.
- Identify the exact decision point for `DAY1` / `DAY2` / `DAY3`.

## 1) Data Flow Overview

The flow is:

1. `scripts/rsi2_episode_tracker.py`
2. `DAILY_REPORTS/YYYY-MM-DD_rsi2_episode_status.csv`
3. `scripts/opportunity_ranking.py`

The tracker computes the current RSI(2) episode state from local OHLC data and writes a daily snapshot per asset.  
The ranking script loads that daily snapshot, merges it with research edge data, computes scores, bucket classification, and the final recommendation string.

## 2) Where `current_oversold_duration` Is Set

The value is created in `scripts/rsi2_episode_tracker.py` inside `current_episode_status()`.

Logic:
- `current_rsi = last["rsi2"]`
- if `current_rsi < RSI_THRESHOLD`:
  - count how many consecutive rows at the end of the series remain below `RSI_THRESHOLD`
  - set `duration` to that consecutive count
  - set `current_phase = f"OVERSOLD_DAY_{duration}"`
- else if `current_rsi < NEAR_THRESHOLD`:
  - set `current_phase = "NEAR_OVERSOLD"`
- else:
  - set `current_phase = "NO_OVERSOLD"`

The daily snapshot includes:
- `current_phase`
- `current_oversold_duration`
- `episode_start_date`
- `episode_start_close`
- `episode_drawdown_pct`

So `current_oversold_duration` is not inferred later by the ranking layer. It is already present in the episode status CSV.

## 3) Is `current_oversold_duration` Passed Correctly?

Yes.

In `scripts/opportunity_ranking.py`, `build_ranking()` does:

- `status = pd.read_csv(latest_episode_status())`
- `edge = pd.read_csv(BEST_EDGE)`
- `df = status.merge(edge, on="asset", how="left")`

The `current_oversold_duration` column comes directly from the status CSV and remains available downstream.

This is confirmed by the daily output file:
- `DAILY_REPORTS/2026-07-03_crypto_opportunity_ranking.csv`

For current rows, it contains:
- `ADA`, `LINK`, `DOGE`, `AVAX` -> `current_phase = OVERSOLD_DAY_1`, `current_oversold_duration = 1`
- `BTC`, `ETH`, `SOL`, `LTC`, `XRP` -> `NO_OVERSOLD`, `current_oversold_duration = 0`

## 4) Why Recommendation Stays `DAY1_OBSERVE_ONLY`

The final recommendation is decided in `scripts/opportunity_ranking.py` inside `recommendation(row)`.

Relevant rule:

- if `bucket == "ACTIVE_OPPORTUNITY"` and `duration == 1`:
  - return `"DAY1_OBSERVE_ONLY"`

That is the only explicit `DAY1` label in the file.

After that, the function does not map day numbers to `DAY2` or `DAY3`.  
Instead it uses:

- `HIGH_PRIORITY_REVIEW`
- `MANUAL_REVIEW`
- `WATCH_CLOSELY`
- `HISTORICALLY_STRONG_NO_SIGNAL`
- `NO_ACTION`

So the recommendation stays `DAY1_OBSERVE_ONLY` because that string is hard-coded for any active opportunity with `current_oversold_duration == 1`.

## 5) Is There a Path to `DAY2` / `DAY3`?

Not in the current `recommendation()` logic.

What the code does today:
- `current_oversold_duration` influences `opportunity_score`
- `current_phase` influences `bucket`
- `entry_alignment_score`, `opportunity_score`, and `confidence_score` influence whether the recommendation becomes:
  - `HIGH_PRIORITY_REVIEW`
  - `MANUAL_REVIEW`
  - `WATCH_CLOSELY`
  - `HISTORICALLY_STRONG_NO_SIGNAL`
  - `NO_ACTION`

What it does not do:
- it does not return `"DAY2_*"` or `"DAY3_*"`
- it does not branch on `current_oversold_duration == 2` or `== 3`

So the answer is:
- `DAY2` / `DAY3` states can exist in `current_phase`
- but they are not represented as recommendation labels in the current implementation

## 6) Exact Decision Point

The decision point is:

- `scripts/opportunity_ranking.py`
- function: `recommendation(row)`

This is where the system decides the final recommendation string after bucket and score calculations.

The most important branch for the current audit is:

```python
if bucket == "ACTIVE_OPPORTUNITY" and duration == 1:
    return "DAY1_OBSERVE_ONLY"
```

There is no analogous branch for `duration == 2` or `duration == 3`.

## 7) Audit Conclusion

### Current oversold duration
Passed correctly from the tracker into the daily episode status CSV and then into opportunity ranking.

### Why recommendation remains DAY1
Because `recommendation()` explicitly returns `DAY1_OBSERVE_ONLY` for `ACTIVE_OPPORTUNITY` when `current_oversold_duration == 1`.

### Can it move to DAY2 / DAY3?
`current_phase` can reflect `OVERSOLD_DAY_2` or `OVERSOLD_DAY_3` when the tracker sees consecutive oversold closes, but the ranking layer does not currently emit `DAY2` or `DAY3` recommendation labels.

### Where the decision is made
`scripts/opportunity_ranking.py -> recommendation(row)`

