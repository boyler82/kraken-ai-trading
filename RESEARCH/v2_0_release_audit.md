# v2.0 Release Audit

Date: 2026-07-10
Final status: PASS

## Summary

- PIPELINE: OK=17 WARNING=0 FAIL=0
- DATA: OK=4 WARNING=0 FAIL=0
- SIGNALS: OK=8 WARNING=0 FAIL=0
- PORTFOLIO: OK=2 WARNING=0 FAIL=0
- COSTS: OK=4 WARNING=0 FAIL=0
- REPORTS: OK=4 WARNING=0 FAIL=0

## Findings

- PIPELINE | OK | module exists: scripts/opportunity_ranking.py | scripts/opportunity_ranking.py
- PIPELINE | OK | module exists: scripts/project_memory.py | scripts/project_memory.py
- PIPELINE | OK | module exists: scripts/signal_exit_calendar.py | scripts/signal_exit_calendar.py
- PIPELINE | OK | module exists: scripts/signal_outcome_engine.py | scripts/signal_outcome_engine.py
- PIPELINE | OK | module exists: scripts/morning_brief.py | scripts/morning_brief.py
- PIPELINE | OK | module exists: scripts/daily_decision_dashboard.py | scripts/daily_decision_dashboard.py
- PIPELINE | OK | module exists: scripts/project_health_check.py | scripts/project_health_check.py
- PIPELINE | OK | module exists: scripts/position_manager.py | scripts/position_manager.py
- PIPELINE | OK | module exists: scripts/realized_trade_manager.py | scripts/realized_trade_manager.py
- PIPELINE | OK | module exists: scripts/run_research.py | scripts/run_research.py
- PIPELINE | OK | research_pipeline STEPS loaded | 28 steps
- PIPELINE | OK | project_memory.py runs exactly once | count=1
- PIPELINE | OK | opportunity_ranking before project_memory | ranking=6, memory=7
- PIPELINE | OK | project_memory before signal_exit_calendar | memory=7, exit_calendar=19
- PIPELINE | OK | project_memory before signal_outcome_engine | memory=7, outcome=20
- PIPELINE | OK | project_health_check last | health=27, last=27
- PIPELINE | OK | final_v2_audit.log pipeline completed | SUCCESS found
- DATA | OK | latest crypto data_age_days <= 1 | max_crypto_age=0
- DATA | OK | ETF/stock stale rows have STALE_DATA | rows=4
- DATA | OK | no NaN in critical OPEN signal fields | missing_rows=0
- DATA | OK | entry_price not truncated versus ranking close | rounded_assets=none
- SIGNALS | OK | SQLite database exists | /Users/tron/kraken-ai-trading/journal/project_memory.sqlite
- SIGNALS | OK | signal_id is unique | rows=15 unique=15
- SIGNALS | OK | OPEN signal has date, entry_price, planned_exit_date | missing_rows=0
- SIGNALS | OK | planned_exit_date >= signal date | bad_rows=0
- SIGNALS | OK | planned_exit_date not recalculated for existing signal_id | existing OPEN update does not set planned_exit_date; migration only fills NULLs
- SIGNALS | OK | signal_exit_calendar and SQLite have same OPEN dates | db=4 calendar=4
- SIGNALS | OK | CLOSED signals do not appear as OPEN | overlap=none
- SIGNALS | OK | dashboard OPEN signal assets match SQLite | db=['ADA', 'AVAX', 'DOGE', 'LINK'] dashboard=['ADA', 'AVAX', 'DOGE', 'LINK']
- PORTFOLIO | OK | portfolio_positions.csv empty means No open positions | portfolio_empty=True, position_manager_rows=0
- PORTFOLIO | OK | position_manager, dashboard and morning_brief agree | portfolio_empty=True, dashboard_no_positions=True, brief_no_positions=True
- COSTS | OK | config/trading_costs.json exists | /Users/tron/kraken-ai-trading/config/trading_costs.json
- COSTS | OK | default_fee_pct = 0.20 | default_fee_pct=0.2
- COSTS | OK | realized_trade_manager shows estimated_fee | estimated_fee token present
- COSTS | OK | FX_REQUIRED does not calculate false realized P/L | FX_REQUIRED rows null realized_pnl fields
- REPORTS | OK | today daily_decision_dashboard exists | 2026-07-10_daily_decision_dashboard.md
- REPORTS | OK | morning_brief runs | Date: 2026-07-10
- REPORTS | OK | project_health_check = OK | summary_statuses=['OK', 'OK']
- REPORTS | OK | no old report references when today's reports exist | old_refs=none
