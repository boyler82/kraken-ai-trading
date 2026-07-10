from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "DAILY_REPORTS"
TODAY = pd.Timestamp.today().strftime("%Y-%m-%d")


def _latest(pattern: str) -> Path | None:
    files = sorted(REPORT_DIR.glob(pattern))
    return files[-1] if files else None


def _load_csv(pattern: str) -> pd.DataFrame:
    path = _latest(pattern)
    if path is None:
        return pd.DataFrame()
    return pd.read_csv(path)


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_alerts() -> pd.DataFrame:
    position_manager = _load_csv("*_position_manager.csv")
    exit_planner = _load_csv("*_exit_planner.csv")

    if position_manager.empty:
        return pd.DataFrame(
            columns=[
                "asset",
                "current_price",
                "cost_basis",
                "current_pnl",
                "current_return_pct",
                "base_target",
                "optimistic_target",
                "distance_to_base_target_pct",
                "distance_to_optimistic_target_pct",
                "alert_status",
            ]
        )

    pm = position_manager.copy()
    ep = exit_planner.copy()

    if "asset" not in pm.columns:
        return pd.DataFrame()

    if not ep.empty and "asset" in ep.columns:
        ep = ep[
            [
                "asset",
                "current_price",
                "cost_basis",
                "current_pnl",
                "current_return_pct",
                "base_target",
                "optimistic_target",
            ]
        ].copy()
        merged = pm.merge(ep, on="asset", how="left", suffixes=("_pm", "_ep"))
    else:
        merged = pm.copy()
        for col in [
            "current_price",
            "cost_basis",
            "current_pnl",
            "current_return_pct",
            "base_target",
            "optimistic_target",
        ]:
            if col not in merged.columns:
                merged[col] = None

    rows = []
    for _, row in merged.iterrows():
        asset = str(row.get("asset", "")).strip().upper()
        current_price = _to_float(row.get("current_price_ep", row.get("current_price")))
        cost_basis = _to_float(row.get("cost_basis_ep", row.get("cost_basis")))
        current_pnl = _to_float(row.get("current_pnl_ep", row.get("current_pnl")))
        current_return_pct = _to_float(row.get("current_return_pct_ep", row.get("current_return_pct")))
        base_target = _to_float(row.get("base_target"))
        optimistic_target = _to_float(row.get("optimistic_target"))

        distance_to_base_target_pct = (
            ((base_target / current_price) - 1) * 100
            if base_target is not None and current_price not in (None, 0)
            else None
        )
        distance_to_optimistic_target_pct = (
            ((optimistic_target / current_price) - 1) * 100
            if optimistic_target is not None and current_price not in (None, 0)
            else None
        )

        if current_price is not None and optimistic_target is not None and current_price >= optimistic_target:
            alert_status = "TAKE_PROFIT_REVIEW"
        elif current_price is not None and base_target is not None and current_price >= base_target:
            alert_status = "BASE_TARGET_REACHED"
        elif current_return_pct is not None and current_return_pct < -5:
            alert_status = "RISK_REVIEW"
        else:
            alert_status = "HOLD_MONITOR"

        rows.append(
            {
                "asset": asset,
                "current_price": current_price,
                "cost_basis": cost_basis,
                "current_pnl": current_pnl,
                "current_return_pct": current_return_pct,
                "base_target": base_target,
                "optimistic_target": optimistic_target,
                "distance_to_base_target_pct": (
                    round(distance_to_base_target_pct, 4)
                    if distance_to_base_target_pct is not None
                    else None
                ),
                "distance_to_optimistic_target_pct": (
                    round(distance_to_optimistic_target_pct, 4)
                    if distance_to_optimistic_target_pct is not None
                    else None
                ),
                "alert_status": alert_status,
            }
        )

    return pd.DataFrame(rows)


def render_report(report: pd.DataFrame) -> str:
    lines = [
        "# Research Stop Alert",
        "",
        f"Date: {TODAY}",
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
        lines.append(f"- Current price: {row['current_price']}")
        lines.append(f"- Cost basis: {row['cost_basis']}")
        lines.append(f"- Current P/L: {row['current_pnl']}")
        lines.append(f"- Current return %: {row['current_return_pct']}")
        lines.append(f"- Base target: {row['base_target']}")
        lines.append(f"- Optimistic target: {row['optimistic_target']}")
        lines.append(f"- Distance to base target %: {row['distance_to_base_target_pct']}")
        lines.append(f"- Distance to optimistic target %: {row['distance_to_optimistic_target_pct']}")
        lines.append(f"- Alert status: {row['alert_status']}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_alerts()

    csv_out = REPORT_DIR / f"{TODAY}_research_stop_alert.csv"
    md_out = REPORT_DIR / f"{TODAY}_research_stop_alert.md"

    report.to_csv(csv_out, index=False)
    md_out.write_text(render_report(report))

    print("\nRESEARCH STOP ALERT\n")
    print(report.to_string(index=False) if not report.empty else "No positions found.")
    print(f"\nSaved: {csv_out}")
    print(f"Saved: {md_out}")


if __name__ == "__main__":
    main()
