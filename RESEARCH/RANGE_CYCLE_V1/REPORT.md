# RANGE_CYCLE_V1 — VERDICT: RESEARCH

Research only. Trading DISABLED. No existing strategy, configuration, registry or trading system changed.

## DATA

101 existing Kraken-labelled USD hourly CSVs from `DATASETS/market_intraday_weekly`, using XBTUSD for BTC. The archive has heterogeneous starts and gaps (archive-wide May 13–October 21, 2026). Cutoff: October 22 00:00 UTC, exclusive. `manifest.json` records full-file SHA-256, coverage and missing hours for every input. Zero duplicate, off-grid or structurally invalid OHLC rows were found before the cutoff. No downloads, data repair or filling.

After stablecoin exclusions, continuous joint BTC/asset history and trailing 24h approximate USD turnover ≥ $1m: 1,310 accepted event/variant/side rows before outcome checks; 44 excluded for incomplete future windows. Final **1,266 rows, 1,206 distinct asset/signal timestamps, 70 assets**, July 31 16:00–October 19 19:00 UTC. These are overlapping observations, not independent trades. There are only **six distinct support cycle signal timestamps across five assets**, with duplication between variants; the 48h touch and rejection signals are four hours apart in the same XMR episode.

## DEFINITIONS

`spec.json` was written before the first test. All six predefined variants and both event sides are reported; no thresholds were changed after inspecting results. This is a standalone historical definition, not a replay of the existing consolidation engine's live classifications.

For each 48h or 96h window ending immediately before the signal candle, freeze support=min(low), resistance=max(high). Require 3–15% amplitude, close endpoint displacement divided by summed absolute hourly close changes ≤0.30, and each chronological third's high-low span ≥50% of the whole range. The last condition rejects ranges dominated by a localized spike. Boundaries and cycle counts use only information preceding the signal.

Map past closes to the lower/upper 20% of that frozen range; ignore middle closes and repeated visits to the same side. A cycle requires at least four alternating boundary transitions (two complete back-and-forth cycles), with median time between alternating visits 2–24 hours. This deliberately requires repeated oscillation rather than simply low net drift.

For both windows, test:

| Rule | Requirement |
|---|---|
| BASE_TOUCH | Range and current boundary event; no cycle requirement |
| CYCLE_TOUCH | Same event plus repeated-cycle requirement |
| CYCLE_REJECT | Cycle event plus higher close at support / lower close at resistance |

A support event has signal low ≤support+20% width and close inside the bottom 20% of the range. A resistance event has high ≥resistance−20% width and close inside the top 20%. All qualifying bars are considered, with a 48h per-asset/window/rule/side cooldown, applied before future-completeness exclusion. A rejection is a same-candle close-direction condition, not proof that price will reverse. Different rule cooldowns can select different timestamps.

Enter long at the next open; primary exit is the open 24h later, with 12h/48h sensitivities. **Support is the proposed long strategy. Resistance long returns are diagnostic controls, not a short strategy.** No stop, target or dynamic execution rule is simulated. Ten entry opens fall outside the frozen range; these are retained as specified, not filtered with hindsight. Historical completeness requires the past 169 joint hours and all 49 subsequent hours, even for shorter-horizon outcomes.

EV=arithmetic mean return after costs; win rate=fraction of net returns >0. Base round trip is 0.40% fees+0.20% slippage, following existing research defaults; report 0.30/0.60/1.00/1.50% total costs. MFE/MAE are gross high/low excursions over held candles, excluding the exit candle. BTC uses identical entry/exit times and costs. BTC-relative return is gross geometric asset/BTC ratio return; equal-cost net excess in percentage points is separately available in the CSVs. These are episode EVs, not portfolio returns, CAGR or Sharpe ratios.

Risk diagnostics over the first 24 held hours: opposite-boundary touch versus failure beyond the near boundary by 10% of range width. At support this is resistance versus support−10% width; at resistance, support versus resistance+10% width. Record either touch and which occurs first; same-bar ties are ambiguous. These thresholds are diagnostic and do not change fixed-horizon trade exits. Failure means a wick touch, not necessarily a sustained closing-price breakdown.

## RESULTS

Primary support results, all percentages, base 0.60% round trip:

| Window / rule | n | Net EV | Win rate | MFE | MAE | BTC net EV | BTC-relative gross | Failure touch |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 48h baseline | 417 | −0.171 | 42.0% | +3.924 | −3.565 | −0.409 | +0.222 | 65.2% |
| 48h cycle touch | 1 | +2.183 | 100% | +4.984 | −0.460 | +7.064 | −4.533 | 0% |
| 48h cycle rejection | 1 | +0.296 | 100% | +5.589 | −0.207 | +7.493 | −6.658 | 0% |
| 96h baseline | 240 | +0.170 | 48.8% | +3.468 | −2.827 | −0.284 | +0.436 | 47.5% |
| 96h cycle touch | 4 | +2.372 | 50.0% | +6.857 | −2.511 | −0.737 | +3.074 | 50.0% |
| 96h cycle rejection | 3 | −0.464 | 33.3% | +4.571 | −3.231 | −1.107 | +0.629 | 66.7% |

Baseline resistance was touched after support entries in 17.3% (48h range) / 8.3% (96h range) of cases; it was reached before failure in only 13.7% / 6.7%. Baseline failures were first in 65.2% / 47.5%. The cycle samples are too small to infer a safer next support reaction. Full counts, medians, net BTC excess and risk ordering are in `summary.csv` and `observations.csv`.

All resistance controls are below; returns remain **long** returns after a resistance event. Positive EV therefore does not support a bearish rejection thesis. No borrowing, short fees or short trade returns are claimed.

| Window / rule | n | Long net EV | Long win rate | Long MFE / MAE | Upper failure touch | Lower target first |
|---|---:|---:|---:|---:|---:|---:|
| 48h baseline | 384 | +0.015 | 38.8% | +4.878 / −3.684 | 67.2% | 9.1% |
| 48h cycle touch | 5 | +0.157 | 60.0% | +6.815 / −5.867 | 60.0% | 40.0% |
| 48h cycle rejection | 2 | +0.739 | 50.0% | +12.081 / −9.833 | 50.0% | 50.0% |
| 96h baseline | 202 | +0.080 | 37.1% | +4.284 / −3.132 | 60.4% | 6.9% |
| 96h cycle touch | 4 | −0.100 | 25.0% | +4.935 / −3.876 | 50.0% | 0% |
| 96h cycle rejection | 3 | +0.859 | 33.3% | +6.321 / −3.832 | 66.7% | 0% |

Cycle versus baseline EV differences are selection comparisons, not paired treatment effects. `comparisons.csv` includes sample sizes and exact shared signals; most cycle events do not coincide with baseline events because of cooldown timing. Returns on shared identical signals are identical, as expected. No causal claim is made from the unpaired mean difference.

## CLUSTERS

Using all variants and both sides, connected components of overlapping signal-to-48h-exit intervals produce **one global exposure cluster**. It would be incorrect to treat 1,266 rows as independent evidence. The sparse support-cycle events alone occur in five temporally disconnected groups: XMR August 19, VVV August 28, ZEC September 22, RENDER October 2, STX October 7. They are separated in time but remain observations on one market path; independence is not established. The two XMR signals and repeated rule/window measurements must not count as additional independent episodes.

Weekly mean-return bootstrap uses 5,000 fixed-seed resamples, descriptive only. Baseline support occupied weeks: 13 (48h range), 12 (96h). Their 95% percentile intervals are [−1.059,+0.945]% and [−1.004,+1.293]%. The four-event 96h cycle-touch interval is [−2.666,+7.917]%. The single-event 48h samples produce degenerate intervals equal to their observed return; these are **not meaningful confidence intervals**. Leave-one-asset-out/top-three removal is undefined when nothing remains; blanks in `robustness.csv` mean unavailable, not passed checks. Week blocks are not certified independent and variant multiplicity is unadjusted.

## REGIMES

BTC trend is close above/below its 168h mean; volatility is 168h hourly-return standard deviation above/below its trailing 720h median, known at signal. Missing history is retained as UNKNOWN (321 of 1,266 rows), rather than removed. Context is descriptive and does not filter entries.

| BTC regime | 48h baseline support n / EV | 96h baseline support n / EV |
|---|---:|---:|
| DOWN / HIGH vol | 77 / −1.202% | 67 / −0.319% |
| DOWN / LOW vol | 129 / −0.552% | 68 / −0.342% |
| UP / HIGH vol | 62 / +2.267% | 16 / +3.420% |
| UP / LOW vol | 47 / −1.024% | 24 / +0.865% |
| UNKNOWN | 102 / −0.001% | 65 / +0.154% |

Both 48h cycle signals are XMR in UNKNOWN regime and underperform matched BTC. The four 96h cycle touches are VVV UNKNOWN −0.969%, ZEC UP/HIGH +10.879%, RENDER UP/LOW +3.941%, and STX DOWN/LOW −4.364%. Each regime cell has one event; this cannot validate a regime edge. Rejection retains VVV, RENDER and STX and excludes ZEC under the frozen rule. All resistance and cycle regime rows are in `regimes.csv`.

Volume context uses signal volume / previous-24h mean: LOW<0.75, NORMAL 0.75–1.5, HIGH>1.5. Baseline support EVs (LOW/NORMAL/HIGH): 48h +0.234/−0.715/−0.151%; 96h +0.616/+0.182/−0.139%. The cycle sample's sole high-volume support event is ZEC's +10.879%; the apparent volume effect is one observation. `volume.csv` reports every populated context cell; absent cells have no observations.

Amplitude and median alternating-visit duration are reported for every observation, with all populated predefined bins in `amplitude.csv` and `duration.csv`. The only 48h cycle occurs at 3.095% amplitude, with median transition times 9h (touch) and 8h (rejection). The 96h cycles have 8.123–14.597% amplitude and 19.5–21.5h transition times. Window length is the range age proxy; median transition time is swing duration. These are not estimates of the true beginning or lifetime of a consolidation. There are too few qualifying cycles to distinguish amplitude or duration effects.

## ROBUSTNESS

All 144 side/window/rule/horizon/cost combinations are reported in `sensitivity.csv`; none were selected or discarded. Support net EV at 12h/24h/48h, base costs:

| Variant | 12h | 24h | 48h |
|---|---:|---:|---:|
| 48h baseline | −0.656% | −0.171% | +0.732% |
| 48h cycle touch | +0.177% | +2.183% | +0.800% |
| 48h cycle rejection | +1.404% | +0.296% | +1.368% |
| 96h baseline | −0.324% | +0.170% | +1.140% |
| 96h cycle touch | −0.197% | +2.372% | +3.454% |
| 96h cycle rejection | −1.935% | −0.464% | +3.256% |

At 1.00% round-trip cost, both baselines lose at 24h (−0.571% / −0.230%). At 1.50%, they lose −1.071% / −0.730%. The 96h cycle-touch mean remains +1.472% at 1.50% costs, but four events cannot establish robustness. The 48h rejection event turns negative at 1.00% cost; the 96h rejection mean is negative even at 0.30% costs.

Chronological midpoint halves are descriptive, not untouched validation. Baseline support EV early→late: 48h +0.135→−0.350%; 96h +0.444→−0.010%. The 48h cycle rules have no later-half observations. The 96h touch splits into one early event (−0.969%) and three late (+3.485% mean). Rejection's two late events average −0.212%. These counts cannot validate temporal stability (`halves.csv`).

Removing one asset at a time leaves 96h cycle-touch EV between −0.464 and +4.617%; removing ZEC makes the mean negative. Its return after removing the largest three events is −4.364%, leaving one loss. Baseline 96h support EV becomes −0.044% after removing its three largest observations. Baseline 48h is already negative and becomes −0.327%. These are predefined concentration diagnostics, not alternate entry rules. Per-asset results are in `assets.csv`.

Integrity checks: unique rows, finite outcomes, next-open timing and minimum transition counts; independent reconciliation of all horizon returns, BTC returns, geometric relative returns, MFE/MAE, frozen historical boundaries and 24h first-touch diagnostics against source rows; source/spec/code hashes; synthetic oscillation and one-way-drift cases; prefix and future-mutation feature checks. A second offline run reproduced all CSVs and the manifest byte-for-byte (`integrity.json`). Reproduce with `.venv-research/bin/python RESEARCH/RANGE_CYCLE_V1/run.py` and then `.venv-research/bin/python RESEARCH/RANGE_CYCLE_V1/verify.py`. Exact replay requires external source files matching the manifest. The installed NumPy version emits timedelta deprecation warnings; these do not fail reconciliation.

## LIMITATIONS

Very sparse repeated-cycle sample, one global overlapping market cluster, no independent multi-cycle validation, and overlapping variants/sides. Basic candle checks do not prove venue provenance or validate economic anomalies; acquisition timestamps and point-in-time universe membership are unavailable. Current archive coverage may carry survivorship/acquisition bias. USD turnover is approximate; no historical spreads, executable-depth or capacity tests.

Complete-case conditioning uses future window availability and cannot be presented as an executable historical portfolio replay. Requiring a full 48h outcome for every horizon may introduce additional selection. Cooldowns are rule-specific and applied before outcome exclusion. Wick-defined full-window boundaries and the two-cycle criterion are strict; this result neither validates looser variants nor justifies relaxing them after seeing sparse results.

Fixed-window consolidation, range thirds and duration bins are proxies. No adaptive boundary forecasting, true range inception estimate or dynamic volume model is tested. Touch-based failure is not the probability of permanent range failure; hourly bars cannot resolve intrabar ordering. Fixed-open fills and additive costs omit execution uncertainty, compounding, concurrent capital, portfolio drawdowns, cash allocation and tax. MFE/MAE are gross path diagnostics, not realizable exit profits. No significance adjustment for multiple variants, horizons or contexts. Tiny-cell bootstrap intervals and 100% single-event win rates are not useful evidence of predictability.

## VERDICT: RESEARCH

The hypothesis remains **unproven**. Baseline boundary reactions show high failure-touch risk and weak cost-sensitive 24h EV. Strict repeated cycles are too rare in this archive to assess predictability, and the strongest mean depends on one asset. Rejection confirmation does not show a consistent benefit. No variant is a CANDIDATE; the data are insufficient to reject the broader hypothesis. Further work should use additional independent, source-validated history with these definitions frozen, rather than tuning boundaries or cycle counts to increase this sample. Trading remains DISABLED.
