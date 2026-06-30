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
PRICE_FILE_MAP = {
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
OUTPUT_COLUMNS = [
    "asset",
    "quantity",
    "average_entry_price",
    "current_price",
    "market_value",
    "cost_basis",
    "unrealized_pnl_value",
    "unrealized_pnl_pct",
    "status",
    "research_stop",
    "target_1",
    "target_2",
    "research_status",
    "probability_target_before_stop",
    "notes",
]


def _first_present(row: pd.Series, candidates: list[str]):
    for column in candidates:
        if column in row and pd.notna(row[column]):
            value = row[column]
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return None


def _to_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_latest_price(symbol: str) -> tuple[float | None, str | None]:
    normalized = str(symbol).strip().upper()
    candidates = []

    mapped_path = PRICE_FILE_MAP.get(normalized)
    if mapped_path is not None:
        candidates.append(ROOT / mapped_path)

    candidates.append(ROOT / symbol_to_file(normalized))

    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        return None, None

    df = load_ohlc(path)
    if df.empty:
        return None, None

    last = df.iloc[-1]
    return _to_float(last["close"]), str(pd.Timestamp(last["date"]).date())


def _resolve_symbol(row: pd.Series) -> str | None:
    value = _first_present(row, ["symbol", "asset", "ticker", "pair"])
    if value is None:
        return None
    symbol = str(value).strip().upper()
    if not symbol:
        return None
    return symbol.replace("/", "").replace("-", "")


def _resolve_units(row: pd.Series) -> float | None:
    return _to_float(
        _first_present(row, ["units", "qty", "quantity", "amount", "size"])
    )


def _resolve_entry_price(row: pd.Series, units: float | None) -> float | None:
    entry_price = _to_float(
        _first_present(row, ["average_entry_price", "avg_entry_price", "entry_price", "buy_price", "price"])
    )
    if entry_price is not None:
        return entry_price

    cost_basis = _to_float(
        _first_present(row, ["cost_basis", "entry_value", "position_cost", "total_cost"])
    )
    if cost_basis is not None and units not in (None, 0):
        return cost_basis / units

    return None


def build_position_report() -> pd.DataFrame:
    if not INPUT_CSV.exists():
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    positions = pd.read_csv(INPUT_CSV)
    if positions.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    positions["asset"] = positions.apply(_resolve_symbol, axis=1)
    positions["quantity"] = positions.apply(_resolve_units, axis=1)
    positions["cost_basis"] = positions.apply(
        lambda row: _to_float(
            _first_present(row, ["cost_basis", "entry_value", "position_cost", "total_cost"])
        ),
        axis=1,
    )
    positions["notes"] = positions.apply(
        lambda row: _first_present(row, ["notes", "comment", "comments", "memo"]),
        axis=1,
    )
    positions["currency"] = positions.apply(
        lambda row: _first_present(row, ["currency", "ccy", "quote_currency"]),
        axis=1,
    )

    aggregated_rows = []
    for asset, group in positions.groupby("asset", dropna=True):
        if pd.isna(asset) or asset is None:
            continue

        quantity = group["quantity"].dropna().sum()
        cost_basis = group["cost_basis"].dropna().sum()
        average_entry_price = (cost_basis / quantity) if quantity else None
        current_price, _market_date = _load_latest_price(str(asset))
        currency = (
            str(group["currency"].dropna().iloc[0]).strip().upper()
            if not group["currency"].dropna().empty
            else None
        )
        price_file_name = PRICE_FILE_MAP.get(str(asset).strip().upper())
        price_file_is_usd = bool(price_file_name and "USD" in Path(price_file_name).name.upper())

        fx_required = currency == "EUR" and price_file_is_usd

        if fx_required:
            market_value = None
            unrealized_pnl_value = None
            unrealized_pnl_pct = None
        else:
            market_value = (quantity * current_price) if quantity is not None and current_price is not None else None
            unrealized_pnl_value = (
                market_value - cost_basis
                if market_value is not None and cost_basis is not None
                else None
            )
            unrealized_pnl_pct = (
                (unrealized_pnl_value / cost_basis) * 100
                if unrealized_pnl_value is not None and cost_basis not in (None, 0)
                else None
            )

        notes_values = [
            str(note).strip()
            for note in group["notes"].tolist()
            if note is not None and not pd.isna(note) and str(note).strip()
        ]
        notes_text = "aggregated position"
        if notes_values:
            notes_text = f"aggregated position; {'; '.join(notes_values)}"

        aggregated_rows.append(
            {
                "asset": str(asset),
                "quantity": round(float(quantity), 8) if quantity is not None else None,
                "average_entry_price": round(float(average_entry_price), 8) if average_entry_price is not None else None,
                "current_price": round(float(current_price), 8) if current_price is not None else None,
                "market_value": round(float(market_value), 8) if market_value is not None else None,
                "cost_basis": round(float(cost_basis), 8) if cost_basis is not None else None,
                "unrealized_pnl_value": round(float(unrealized_pnl_value), 8) if unrealized_pnl_value is not None else None,
                "unrealized_pnl_pct": round(float(unrealized_pnl_pct), 4) if unrealized_pnl_pct is not None else None,
                "status": "FX_REQUIRED" if fx_required else ("OK" if current_price is not None and quantity is not None else "INCOMPLETE"),
                "research_stop": "TBD",
                "target_1": "TBD",
                "target_2": "TBD",
                "research_status": "TBD",
                "probability_target_before_stop": "TBD",
                "notes": f"{notes_text}; FX conversion required" if fx_required else notes_text,
            }
        )

    report = pd.DataFrame(aggregated_rows)
    return report.reindex(columns=OUTPUT_COLUMNS)

def render_report(report: pd.DataFrame) -> str:
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    total_value = report["market_value"].fillna(0).sum() if not report.empty else 0.0
    total_pnl = report["unrealized_pnl_value"].fillna(0).sum() if not report.empty else 0.0
    invested = report["quantity"].fillna(0).mul(report["average_entry_price"].fillna(0)).sum() if not report.empty else 0.0
    total_pnl_pct = (total_pnl / invested * 100) if invested else None
    quote_currency_note = "quote currency from local market data"

    lines = []
    lines.append("# Position Manager")
    lines.append("")
    lines.append(f"Date: {today}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Positions: {len(report)}")
    lines.append(f"- Total value: {round(float(total_value), 2)} {quote_currency_note}")
    lines.append(f"- Total P/L: {round(float(total_pnl), 2)} {quote_currency_note}")
    lines.append(
        f"- Total P/L %: {round(float(total_pnl_pct), 4)}%"
        if total_pnl_pct is not None
        else "- Total P/L %: n/a"
    )
    lines.append("")
    lines.append("## Positions")
    lines.append("")

    if report.empty:
        lines.append("No positions found.")
    else:
        for _, row in report.iterrows():
            lines.append(f"### {row['asset'] or 'UNKNOWN'}")
            lines.append("")
            lines.append(f"- Status: {row['status']}")
            lines.append(f"- Quantity: {row['quantity']}")
            lines.append(f"- Average entry price: {row['average_entry_price']}")
            lines.append(f"- Current price: {row['current_price']}")
            lines.append(f"- Market value: {row['market_value']}")
            lines.append(f"- Cost basis: {row['cost_basis']}")
            lines.append(f"- Unrealized P/L: {row['unrealized_pnl_value']} {quote_currency_note}")
            lines.append(f"- Unrealized P/L %: {row['unrealized_pnl_pct']}%")
            lines.append(f"- Research stop: {row['research_stop']}")
            lines.append(f"- Target 1: {row['target_1']}")
            lines.append(f"- Target 2: {row['target_2']}")
            lines.append(f"- Research status: {row['research_status']}")
            lines.append(f"- Probability target before stop: {row['probability_target_before_stop']}")
            lines.append(f"- Notes: {row['notes']}")
            lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- No transactions are executed.")
    lines.append("- Strategy logic is unchanged.")
    lines.append("- Prices are sourced from local market data only.")
    lines.append("- Monetary values are reported in the quote currency of the local data.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    today = pd.Timestamp.today().strftime("%Y-%m-%d")

    report = build_position_report()

    csv_out = REPORT_DIR / f"{today}_position_manager.csv"
    md_out = REPORT_DIR / f"{today}_position_manager.md"

    report.to_csv(csv_out, index=False)
    md_out.write_text(render_report(report))

    print("\nPOSITION MANAGER\n")
    print(report.to_string(index=False) if not report.empty else "No positions found.")
    print(f"\nSaved: {csv_out}")
    print(f"Saved: {md_out}")


if __name__ == "__main__":
    main()
