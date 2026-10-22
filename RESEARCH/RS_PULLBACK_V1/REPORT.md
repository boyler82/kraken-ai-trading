# RS_PULLBACK_V1 — VERDICT: RESEARCH

Research only. Trading DISABLED. No existing strategies, settings, registries or execution systems changed.

## DATA

101 existing local Kraken USD hourly CSVs, frozen by SHA-256 in `manifest.json`; archive-wide coverage May 13–October 21, 2026, with heterogeneous starts and gaps. Cutoff excludes October 22 and later. No download or data repair. All 101 files pass basic OHLC, duplicate and hourly-grid validation (zero rejected rows). Missing hours remain missing; no forward filling. This validates structure, not vendor authenticity or economic plausibility.

After stablecoin exclusion, historical eligibility, warmup and continuous asset/BTC windows: **174 leadership episodes across 74 assets**, August 30 18:00–October 17 16:00 UTC. Excluded: 60 episodes without full regime warmup, 12 without complete joint history/outcomes. Per-file coverage and gaps are in the manifest. The source archive is external; Git contains definitions, code and derived evidence only.

## DEFINITIONS

Definitions were written in `spec.json` before the first run. This is a new historical leadership definition, not a replay of the production RS radar's scores. At each completed hourly close, rank eligible assets by 168h asset/BTC price-ratio return. A leader is top quintile with positive 168h and 48h relative returns. Eligibility requires continuous 169h joint history and trailing 24h approximate USD turnover (close × base volume) ≥ $1m; at least 10 eligible assets. Signals are leadership false-to-true transitions with a 168h per-asset cooldown.

A enters next hourly open. B waits up to 24h for a closing-price drawdown from the running maximum close, followed by a higher close while 168h relative strength remains positive. Three fixed bands: shallow 1–3%, deep 3–5%, and 0.5–1.5 signal-time ATR14 (ATR/close frozen at signal). A band breach invalidates that variant for the episode. B enters next open after confirmation. No stop or take-profit.

Primary comparison gives every original episode equal weight and exits A/B at the same open 72h after A's entry. Unfilled B episodes earn zero in USD cash and pay no costs. C buys BTC at A's entry and sells at the common exit. These are per-episode arithmetic EVs, not portfolio returns or CAGR. Secondary 24/48/72h measurements start at each actual entry and use matched BTC entry/exit times. EV is mean net simple return; win rate is fraction strictly positive after costs. MFE/MAE use hourly highs/lows from entry through the final held candle, excluding the exit candle; they are gross excursions. Relative return is geometric asset/BTC return, gross; net asset and net BTC means are separately reported.

Base round trip: 0.40% fees plus 0.20% slippage, following existing research defaults. Sensitivity totals: 0.30%, 0.60%, 1.00%, 1.50%, all reported. This additive percentage-point cost model assumes executable opens and does not model impact, spread variation or fee-tier eligibility.

## RESULTS A vs B

All returns below are percentages; differences are percentage points. Common-exit BTC EV is **−0.086%** on all 174 episodes.

| Entry | Fills / 174 | Common-exit policy EV | Policy B − A | Filled 48h net EV | 48h win rate | 48h MFE / MAE | 48h BTC-relative gross |
|---|---:|---:|---:|---:|---:|---:|---:|
| A immediate | 174 | +1.339 | — | −0.166 | 36.2% | +10.835 / −7.681 | +0.297 |
| B shallow | 53 | −0.472 | −1.811 | −2.063 | 30.2% | +6.050 / −7.126 | −1.198 |
| B deep | 45 | −0.340 | −1.679 | −1.449 | 33.3% | +7.646 / −7.274 | −0.507 |
| B ATR | 73 | +1.573 | +0.235 | +1.914 | 37.0% | +10.693 / −6.337 | +2.189 |

Filled 48h matched BTC net EVs: A −0.536%, shallow −0.931%, deep −0.906%, ATR −0.345%. Filled-only numbers condition on a future pullback and must not be read as an unbiased all-signal comparison.

On exactly the filled B subsets with common exits, B minus matched A is **−0.129 pp shallow, +1.476 pp deep, −0.205 pp ATR**. Thus the ATR all-episode improvement comes from which episodes are skipped, rather than better entry timing on its filled subset. Full precision, matched A EV and raw episode outcomes are in `summary.csv`, `paired.csv`, `observations.csv`.

## CLUSTERS

Signals whose original signal-to-common-exit intervals overlap are connected across assets. All episodes form **one connected exposure cluster**. Temporal separation is necessary but insufficient for independence; this sample provides no replicated independent cluster evidence. Descriptive weekly resampling uses eight occupied UTC weeks, 5,000 fixed-seed resamples; adjacent weeks are not asserted independent.

Weekly paired B−A 95% percentile intervals: shallow **[−6.546, +2.061] pp**, deep **[−7.128, +2.751] pp**, ATR **[−2.981, +3.116] pp**. Every interval spans zero. These intervals are exploratory and may understate dependence. `clusters.csv` reports the single cluster; per-asset rows are not independent observations.

## REGIME RESULTS

Regimes are known at signal: BTC above/below its 168h moving average, crossed with 168h hourly-return volatility above/below its trailing 720h median. No regime tuning or filtering was applied.

| BTC regime | Episodes | A policy EV | Shallow policy EV | Deep policy EV | ATR policy EV |
|---|---:|---:|---:|---:|---:|
| DOWN / HIGH vol | 22 | +3.701 | −0.134 | −0.854 | +4.901 |
| DOWN / LOW vol | 71 | +4.364 | +0.009 | +0.531 | +4.365 |
| UP / HIGH vol | 46 | −0.141 | −0.672 | −0.256 | −1.616 |
| UP / LOW vol | 35 | −4.337 | −1.396 | −1.894 | −1.990 |

ATR loses in both UP cells. B filled subgroup sizes range from 7 to 30; these are descriptive, overlapping evidence, not reliable regime-specific edges. All cell metrics appear in `regimes.csv`.

## ROBUSTNESS

All predefined variants, horizons and costs are in `sensitivity.csv`; none were discarded. Net filled EV at 24/48/72h: A −0.210/−0.166/+1.339%; shallow −1.857/−2.063/−1.211%; deep −1.230/−1.449/−1.875%; ATR +0.091/+1.914/+3.032%. ATR's 48h EV at total costs 0.30/0.60/1.00/1.50% is +2.214/+1.914/+1.514/+1.014%; costs alone do not remove the full-sample mean.

Chronological halves each contain 87 signals (descriptive split, not an untouched validation set). A policy EV drops from +4.301 to −1.624%; ATR drops from +3.443 to −0.297%. ATR filled 48h EV drops from +4.605 to −1.173%. Shallow/deep later-half policy EVs are −1.011/−1.123%. See `halves.csv`.

Leave-one-asset-out policy EV ranges: ATR +0.893 to +1.735%, shallow −0.624 to −0.380%, deep −0.858 to −0.152%. However removing each variant's three largest individual policy returns turns **every** mean negative: A −0.748%, shallow −0.780%, deep −0.937%, ATR −0.262%. This is an explicitly post-result outlier diagnostic, not another strategy variant or exclusion rule. A's three largest returns exceed +114% each over 72h. Those archive observations require separate source validation before relying on the positive mean. A's policy median is −2.080%; B medians are zero because most signals do not fill.

Integrity: unique paired observations, finite policy outcomes, strictly later entries and zero-cost no-fill cash pass. `verify.py` independently reconciles every filled horizon return, BTC return and MFE/MAE against source rows, plus policy returns, entry timing, and all 101 input hashes. A second offline run reproduced every CSV and manifest byte-for-byte (`integrity.json`). No network or trading API is used. Reproduce with `.venv-research/bin/python RESEARCH/RS_PULLBACK_V1/run.py`, then `verify.py`; exact replay requires the external archives matching the manifest. NumPy emits a timedelta deprecation warning; checks complete successfully.

## LIMITATIONS

Short, gappy local archive; current archive universe is not point-in-time membership and may have survivorship/acquisition bias. Cross-sectional rank depends on available history. The cooldown is applied before warmup/outcome exclusion. Complete-window conditioning excludes future-missing windows, so this is a retrospective complete-case study, not a deployable historical portfolio simulation. Outcome eligibility requires through the latest possible B 72h exit, even for A or unfilled B. Regime warmup and gaps sharply shorten effective coverage.

One connected cluster, only eight weekly blocks, no untouched multi-cycle validation, no correction for trying three variants/horizons, highly skewed outcomes and large individual archive moves. Gross ratio returns do not represent borrowable BTC-denominated execution. Open fills, fees, liquidity, slippage and zero-return cash are approximations; no order-book or capacity test. Equal-weight episode EV ignores overlapping capital, portfolio constraints, compounding and drawdown. Structural data checks do not establish source provenance beyond the available Kraken-labelled archive; acquisition timestamps and historical membership are unavailable.

## VERDICT: RESEARCH

The hypothesis is **not established**. Fixed-percentage pullbacks fail this sample; the ATR rule deserves only further independent research. Its small all-episode advantage lacks statistical separation, fails later-half profitability, disappears after removal of three extreme outcomes, and does not improve matched filled-subset entry timing. It is not a CANDIDATE. Next evidence should come from a prospectively frozen specification and independent, source-validated history; no parameter refinement is justified by these results. Trading remains DISABLED.
