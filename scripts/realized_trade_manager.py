from __future__ import annotations

from pathlib import Path

import pandas as pd

from lib.trading_costs import default_fee_pct


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "journal" / "realized_trades.csv"
REPORT_DIR = ROOT / "DAILY_REPORTS"
REPORT_DATE = pd.Timestamp.today().date()
REPORT_DATE_TS = pd.Timestamp(REPORT_DATE).normalize()
REPORT_DATE_TEXT = REPORT_DATE_TS.strftime("%Y-%m-%d")
OUT_CSV = REPORT_DIR / f"{REPORT_DATE_TEXT}_realized_trades.csv"
OUT_MD = REPORT_DIR / f"{REPORT_DATE_TEXT}_realized_trades.md"

OUTPUT_COLUMNS = [
    "date",
    "asset",
    "side",
    "quantity",
    "entry_price",
    "exit_price",
    "cost_basis",
    "currency",
    "proceeds",
    "realized_pnl",
    "realized_pnl_pct",
    "fees",
    "estimated_fee",
    "notes",
]


def _ensure_input_file() -> None:
    if INPUT_CSV.exists():
        return
    INPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    INPUT_CSV.write_text(",".join(OUTPUT_COLUMNS) + "\n")


def _to_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.upper() in {"FX_REQUIRED", "NULL", "N/A"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _load_trades() -> pd.DataFrame:
    _ensure_input_file()
    df = pd.read_csv(INPUT_CSV)
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    for column in OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = None

    df = df[OUTPUT_COLUMNS].copy()
    df["asset"] = df["asset"].apply(lambda v: _normalize_text(v).upper() if _normalize_text(v) else None)
    df["side"] = df["side"].apply(lambda v: _normalize_text(v).upper() if _normalize_text(v) else None)
    df["currency"] = df["currency"].apply(lambda v: _normalize_text(v).upper() if _normalize_text(v) else None)
    df["date"] = df["date"].apply(_normalize_text)
    df["quantity"] = df["quantity"].apply(_to_float)
    df["entry_price"] = df["entry_price"].apply(_to_float)
    df["exit_price"] = df["exit_price"].apply(_to_float)
    df["cost_basis"] = df["cost_basis"].apply(_to_float)
    df["proceeds"] = df["proceeds"].apply(_to_float)
    df["realized_pnl"] = df["realized_pnl"].apply(_to_float)
    df["realized_pnl_pct"] = df["realized_pnl_pct"].apply(_to_float)
    df["fees"] = df["fees"].apply(_to_float)
    df["estimated_fee"] = df["estimated_fee"].apply(_to_float)
    df["notes"] = df["notes"].apply(_normalize_text)
    return df


def _status_for_row(row: pd.Series) -> str:
    notes = str(row.get("notes") or "").upper()
    if "FX_REQUIRED" in notes or row.get("realized_pnl") is None or row.get("realized_pnl_pct") is None:
        return "FX_REQUIRED"
    return "REALIZED"


def _estimated_fee_for_row(row: pd.Series) -> float | None:
    proceeds = row.get("proceeds")
    if proceeds is None or pd.isna(proceeds):
        return None
    return float(proceeds) * default_fee_pct() / 100.0


def _resolved_fee_for_row(row: pd.Series) -> float | None:
    fees = row.get("fees")
    if fees not in (None, 0) and not pd.isna(fees):
        return float(fees)
    if row.get("status") == "FX_REQUIRED":
        return None
    return _estimated_fee_for_row(row)


def _round_4(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def _display_value(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _display_4dp(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def build_report() -> pd.DataFrame:
    trades = _load_trades()
    if trades.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS + ["status"])

    report = trades.copy()
    report["status"] = report.apply(_status_for_row, axis=1)
    report["estimated_fee"] = report.apply(_estimated_fee_for_row, axis=1).apply(_round_4)
    report["fees"] = report.apply(_resolved_fee_for_row, axis=1)
    fx_mask = report["status"] == "FX_REQUIRED"
    report.loc[fx_mask, "realized_pnl"] = None
    report.loc[fx_mask, "realized_pnl_pct"] = None
    report = report.sort_values(["date", "asset", "side"], ascending=[False, True, True], na_position="last").reset_index(drop=True)
    return report[OUTPUT_COLUMNS + ["status"]]


def render_markdown(report: pd.DataFrame) -> str:
    lines = [
        "# Realized Trade Journal",
        "",
        f"Date: {REPORT_DATE_TEXT}",
        "",
        "## Summary",
        "",
    ]

    if report.empty:
        lines.append("- Total realized P/L: 0")
        lines.append("- Total proceeds: 0")
        lines.append("- Trades count: 0")
        lines.append("- Total estimated fee: 0")
        lines.append("")
        lines.append("## Per Asset Realized P/L")
        lines.append("")
        lines.append("No realized trades.")
        return "\n".join(lines)

    realized_pnl = pd.to_numeric(report["realized_pnl"], errors="coerce")
    proceeds = pd.to_numeric(report["proceeds"], errors="coerce")
    total_realized_pnl = realized_pnl.fillna(0).sum()
    total_proceeds = proceeds.fillna(0).sum()
    estimated_fee = pd.to_numeric(report["estimated_fee"], errors="coerce")
    total_estimated_fee = round(estimated_fee.fillna(0).sum(), 4)
    trades_count = len(report)

    lines.append(f"- Total realized P/L: {total_realized_pnl}")
    lines.append(f"- Total proceeds: {total_proceeds}")
    lines.append(f"- Trades count: {trades_count}")
    lines.append(f"- Total estimated fee: {_display_4dp(total_estimated_fee)}")
    lines.append("")
    lines.append("## Per Asset Realized P/L")
    lines.append("")

    asset_summary = (
        report.assign(realized_pnl_numeric=realized_pnl)
        .groupby("asset", dropna=True)["realized_pnl_numeric"]
        .sum(min_count=1)
        .reset_index()
    )
    if asset_summary.empty:
        lines.append("No numeric realized P/L available.")
    else:
        for _, row in asset_summary.iterrows():
            lines.append(f"- {row['asset']}: {_display_value(row['realized_pnl_numeric'])}")

    lines.append("")
    lines.append("## Transactions")
    lines.append("")
    for _, row in report.iterrows():
        lines.append(
            f"- {row['date']} | {row['asset']} | {row['side']} | qty {_display_value(row['quantity'])} | entry {_display_value(row['entry_price'])} | exit {_display_value(row['exit_price'])} | cost_basis {_display_value(row['cost_basis'])} | currency {_display_value(row['currency'])} | proceeds {_display_value(row['proceeds'])} | realized_pnl {_display_value(row['realized_pnl'])} | realized_pnl_pct {_display_value(row['realized_pnl_pct'])} | fees {_display_value(row['fees'])} | estimated_fee {_display_4dp(row['estimated_fee'])} | status {row['status']} | notes {_display_value(row['notes'])}"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- FX-mixed trades are kept as `FX_REQUIRED` and excluded from realized P/L calculations.")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    report.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(report))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if report.empty:
        print("No realized trades.")
    else:
        print(report.to_string(index=False))


if __name__ == "__main__":
    main()
