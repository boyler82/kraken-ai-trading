from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

from lib.config import symbol_to_file  # noqa: E402
from lib.data_loader import load_ohlc  # noqa: E402


INPUT_CSV = ROOT / "journal" / "portfolio_positions.csv"
REPORT_DIR = ROOT / "DAILY_REPORTS"
MARKET_REGIME = ROOT / "BACKTESTS" / "market_regime.csv"
OPPORTUNITY_RANKING = None
if (REPORT_DIR / f"{pd.Timestamp.today().strftime('%Y-%m-%d')}_crypto_opportunity_ranking.csv").exists():
    OPPORTUNITY_RANKING = REPORT_DIR / f"{pd.Timestamp.today().strftime('%Y-%m-%d')}_crypto_opportunity_ranking.csv"
else:
    ranking_files = sorted(REPORT_DIR.glob("*_crypto_opportunity_ranking.csv"))
    OPPORTUNITY_RANKING = ranking_files[-1] if ranking_files else None

PRICE_FILE_MAP = {
    "BTCUSD": "DATASETS/market_raw/BTCUSD_D1.json",
    "BTCEUR": "DATASETS/market_raw/BTCEUR_D1.json",
    "BTC": "DATASETS/market_raw/BTCUSD_D1.json",
    "ETH": "DATASETS/market_raw/ETHUSD_D1.json",
    "SOL": "DATASETS/market_raw/SOLUSD_D1.json",
    "ADA": "DATASETS/market_raw/ADAUSD_D1.json",
    "XRP": "DATASETS/market_raw/XRPUSD_D1.json",
    "LINK": "DATASETS/market_raw/LINKUSD_D1.json",
    "LTC": "DATASETS/market_raw/LTCUSD_D1.json",
    "DOGE": "DATASETS/market_raw/DOGEUSD_D1.json",
    "AVAX": "DATASETS/market_raw/AVAXUSD_D1.json",
    "SPY": "DATASETS/market_raw/SPYx_USD_D1.json",
    "QQQ": "DATASETS/market_raw/QQQx_USD_D1.json",
    "GLD": "DATASETS/market_raw/GLDx_USD_D1.json",
    "NVDA": "DATASETS/market_raw/NVDAx_USD_D1.json",
}
TARGET_CURRENCY = {
    "BTC": "EUR",
}


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_asset(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().upper()
    return text or None


def _load_current_price(asset: str) -> tuple[float | None, str | None]:
    asset = _normalize_asset(asset)
    if asset is None:
        return None, None

    candidates = []
    if asset == "BTC":
        candidates.extend(
            [
                ("EUR", ROOT / PRICE_FILE_MAP["BTCEUR"], "BTCEUR"),
                ("USD", ROOT / PRICE_FILE_MAP["BTCUSD"], "BTCUSD"),
            ]
        )
    else:
        path_text = PRICE_FILE_MAP.get(asset)
        if path_text is not None:
            candidates.append(("USD", ROOT / path_text, asset))

    for source, path, load_symbol in candidates:
        if not path.exists():
            continue
        df = load_ohlc(path)
        if df.empty:
            continue
        last = df.iloc[-1]
        return _to_float(last["close"]), str(pd.Timestamp(last["date"]).date())

    return None, None


def _load_atr_pct_map() -> dict[str, float]:
    if not MARKET_REGIME.exists():
        return {}

    regime = pd.read_csv(MARKET_REGIME)
    if "asset" not in regime.columns or "atr_pct" not in regime.columns:
        return {}

    result = {}
    for _, row in regime.iterrows():
        asset = _normalize_asset(row.get("asset"))
        atr_pct = _to_float(row.get("atr_pct"))
        if asset and atr_pct is not None:
            result[asset] = atr_pct
    return result


def _load_research_map() -> dict[str, dict]:
    if OPPORTUNITY_RANKING is None or not OPPORTUNITY_RANKING.exists():
        return {}

    ranking = pd.read_csv(OPPORTUNITY_RANKING)
    needed = {"asset", "expected_value_pct", "profit_factor", "confidence_score"}
    if not needed.issubset(set(ranking.columns)):
        return {}

    result = {}
    for _, row in ranking.iterrows():
        asset = _normalize_asset(row.get("asset"))
        if not asset:
            continue
        result[asset] = {
            "expected_value_pct": _to_float(row.get("expected_value_pct")),
            "profit_factor": _to_float(row.get("profit_factor")),
            "confidence_score": _to_float(row.get("confidence_score")),
        }
    return result


def _scenario_targets(entry_price: float, ev_pct: float | None, pf: float | None, atr_pct: float | None) -> dict[str, float]:
    atr_pct = atr_pct or 0.0
    edge_boost = max(0.0, (ev_pct or 0.0)) * 0.5
    pf_boost = max(0.0, (pf or 1.0) - 1.0) * 4.0
    base_buffer = max(atr_pct * 0.5, 1.0)

    conservative_pct = max(base_buffer, edge_boost + 0.5)
    base_pct = max(conservative_pct + 1.0, edge_boost + pf_boost + 1.5)
    optimistic_pct = max(base_pct + 1.5, base_pct + atr_pct)

    conservative_target = entry_price * (1 + conservative_pct / 100.0)
    base_target = entry_price * (1 + base_pct / 100.0)
    optimistic_target = entry_price * (1 + optimistic_pct / 100.0)

    return {
        "conservative_target": conservative_target,
        "base_target": base_target,
        "optimistic_target": optimistic_target,
        "conservative_pct": conservative_pct,
        "base_pct": base_pct,
        "optimistic_pct": optimistic_pct,
        "current_gap_to_base_pct": None,
    }


def _position_currency(row: pd.Series) -> str | None:
    currency = _normalize_asset(row.get("currency"))
    return currency


def build_exit_plan() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        return pd.DataFrame()

    positions = pd.read_csv(INPUT_CSV)
    if positions.empty:
        return pd.DataFrame()

    positions["asset"] = positions["asset"].apply(_normalize_asset)
    positions["quantity"] = pd.to_numeric(positions["quantity"], errors="coerce")
    positions["cost_basis"] = pd.to_numeric(positions["cost_basis"], errors="coerce")
    positions["entry_price"] = pd.to_numeric(positions["entry_price"], errors="coerce")

    grouped = (
        positions.groupby("asset", dropna=True)
        .agg(
            quantity=("quantity", "sum"),
            cost_basis=("cost_basis", "sum"),
            currency=("currency", "first"),
        )
        .reset_index()
    )
    grouped["average_entry_price"] = grouped.apply(
        lambda row: row["cost_basis"] / row["quantity"] if row["quantity"] else None,
        axis=1,
    )

    atr_map = _load_atr_pct_map()
    research_map = _load_research_map()

    rows = []
    for _, row in grouped.iterrows():
        asset = row["asset"]
        entry_price = _to_float(row["average_entry_price"])
        current_price, market_date = _load_current_price(asset)
        currency = _position_currency(row)
        current_price_source = "EUR" if asset == "BTC" and (ROOT / PRICE_FILE_MAP["BTCEUR"]).exists() else "USD"
        research = research_map.get(asset, {})
        atr_pct = atr_map.get(asset)
        if atr_pct is None:
            atr_pct = _to_float(research.get("atr_pct"))

        position_currency = TARGET_CURRENCY.get(asset, currency)
        fx_required = position_currency == "EUR" and asset == "BTC" and current_price_source != "EUR"

        targets = None
        if entry_price is not None and current_price is not None:
            targets = _scenario_targets(
                entry_price,
                research.get("expected_value_pct"),
                research.get("profit_factor"),
                atr_pct,
            )

        notes = []
        if research.get("confidence_score") is not None:
            notes.append(f"confidence_score={research['confidence_score']}")
        if research.get("expected_value_pct") is not None:
            notes.append(f"expected_value_pct={research['expected_value_pct']}")
        if research.get("profit_factor") is not None:
            notes.append(f"profit_factor={research['profit_factor']}")
        if atr_pct is not None:
            notes.append(f"atr_pct={atr_pct}")

        if targets is None:
            notes.append("insufficient data for target scenarios")
        else:
            notes.append("research-only exit plan")
        if fx_required:
            notes.append("FX conversion required")

        current_profit = None
        current_return_pct = None
        if not fx_required and current_price is not None and row["cost_basis"] not in (None, 0):
            current_value = float(row["quantity"]) * float(current_price)
            current_profit = current_value - float(row["cost_basis"])
            current_return_pct = (current_profit / float(row["cost_basis"])) * 100

        target_currency = position_currency or currency or "USD"
        target_pnl = None
        target_return_pct = None
        if targets is not None and row["cost_basis"] not in (None, 0):
            target_value = float(row["quantity"]) * float(targets["base_target"])
            target_pnl = target_value - float(row["cost_basis"])
            target_return_pct = (target_pnl / float(row["cost_basis"])) * 100

        rows.append(
            {
                "asset": asset,
                "quantity": round(float(row["quantity"]), 8) if pd.notna(row["quantity"]) else None,
                "average_entry_price": round(float(entry_price), 8) if entry_price is not None else None,
                "current_price": round(float(current_price), 8) if current_price is not None else None,
                "market_date": market_date,
                "currency": target_currency,
                "current_price_source": current_price_source,
                "status": "FX_REQUIRED" if fx_required else "OK",
                "expected_value_pct": research.get("expected_value_pct"),
                "profit_factor": research.get("profit_factor"),
                "atr_pct": atr_pct,
                "cost_basis": round(float(row["cost_basis"]), 8) if pd.notna(row["cost_basis"]) else None,
                "conservative_target": None if targets is None else round(float(targets["conservative_target"]), 8),
                "base_target": None if targets is None else round(float(targets["base_target"]), 8),
                "optimistic_target": None if targets is None else round(float(targets["optimistic_target"]), 8),
                "conservative_target_pnl": None if targets is None or row["cost_basis"] in (None, 0) else round((float(row["quantity"]) * float(targets["conservative_target"])) - float(row["cost_basis"]), 8),
                "base_target_pnl": None if targets is None or row["cost_basis"] in (None, 0) else round((float(row["quantity"]) * float(targets["base_target"])) - float(row["cost_basis"]), 8),
                "optimistic_target_pnl": None if targets is None or row["cost_basis"] in (None, 0) else round((float(row["quantity"]) * float(targets["optimistic_target"])) - float(row["cost_basis"]), 8),
                "conservative_target_return_pct": None if targets is None or row["cost_basis"] in (None, 0) else round((((float(row["quantity"]) * float(targets["conservative_target"])) - float(row["cost_basis"])) / float(row["cost_basis"])) * 100, 4),
                "base_target_return_pct": None if targets is None or row["cost_basis"] in (None, 0) else round((((float(row["quantity"]) * float(targets["base_target"])) - float(row["cost_basis"])) / float(row["cost_basis"])) * 100, 4),
                "optimistic_target_return_pct": None if targets is None or row["cost_basis"] in (None, 0) else round((((float(row["quantity"]) * float(targets["optimistic_target"])) - float(row["cost_basis"])) / float(row["cost_basis"])) * 100, 4),
                "current_pnl": None if current_profit is None else round(float(current_profit), 8),
                "current_return_pct": None if current_return_pct is None else round(float(current_return_pct), 4),
                "commentary": "; ".join(notes),
            }
        )

    return pd.DataFrame(rows)


def render_report(report: pd.DataFrame) -> str:
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    lines = [
        "# Exit Planner",
        "",
        f"Date: {today}",
        "",
        "Research only. No transactions are executed.",
        "",
    ]

    if report.empty:
        lines.append("No positions found.")
        return "\n".join(lines)

    for _, row in report.iterrows():
        lines.append(f"## {row['asset']}")
        lines.append("")
        lines.append(f"- Quantity: {row['quantity']}")
        lines.append(f"- Average entry price: {row['average_entry_price']}")
        lines.append(f"- Current price: {row['current_price']}")
        lines.append(f"- Cost basis: {row['cost_basis']}")
        lines.append(f"- Status: {row['status']}")
        lines.append(f"- Current price source: {row['current_price_source']}")
        lines.append(f"- Expected value: {row['expected_value_pct']}")
        lines.append(f"- Profit factor: {row['profit_factor']}")
        lines.append(f"- ATR %: {row['atr_pct']}")
        lines.append("")
        lines.append("### Conservative Target")
        lines.append(f"- Target price: {row['conservative_target']}")
        lines.append(f"- Potential profit: {row['conservative_target_pnl']}")
        lines.append(f"- Potential return: {row['conservative_target_return_pct']}%")
        lines.append("")
        lines.append("### Base Target")
        lines.append(f"- Target price: {row['base_target']}")
        lines.append(f"- Potential profit: {row['base_target_pnl']}")
        lines.append(f"- Potential return: {row['base_target_return_pct']}%")
        lines.append("")
        lines.append("### Optimistic Target")
        lines.append(f"- Target price: {row['optimistic_target']}")
        lines.append(f"- Potential profit: {row['optimistic_target_pnl']}")
        lines.append(f"- Potential return: {row['optimistic_target_return_pct']}%")
        lines.append("")
        lines.append(f"- Research commentary: {row['commentary']}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.today().strftime("%Y-%m-%d")

    report = build_exit_plan()
    csv_out = REPORT_DIR / f"{today}_exit_planner.csv"
    md_out = REPORT_DIR / f"{today}_exit_planner.md"

    report.to_csv(csv_out, index=False)
    md_out.write_text(render_report(report))

    print("\nEXIT PLANNER\n")
    print(report.to_string(index=False) if not report.empty else "No positions found.")
    print(f"\nSaved: {csv_out}")
    print(f"Saved: {md_out}")


if __name__ == "__main__":
    main()
