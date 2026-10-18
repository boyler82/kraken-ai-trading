from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pandas as pd

from lib.universe import report_dir


REPORT_DIR = report_dir()
TODAY = pd.Timestamp.today().normalize()
OUT_CSV = REPORT_DIR / f"{TODAY:%Y-%m-%d}_crypto_research_radar.csv"
OUT_MD = REPORT_DIR / f"{TODAY:%Y-%m-%d}_crypto_research_radar.md"
ACTIVE_STATUSES = {"ACTIONABLE", "DEVELOPING"}
SNAPSHOT_SUFFIXES = (
    "trade_candidate_dashboard",
    "research_score",
)


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _date_from_name(path: Path) -> pd.Timestamp | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})_", path.name)
    if not match:
        return None
    value = pd.to_datetime(match.group(1), errors="coerce")
    return None if pd.isna(value) else pd.Timestamp(value).normalize()


def available_dates(directory: Path, through: pd.Timestamp = TODAY) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    for suffix in SNAPSHOT_SUFFIXES:
        for path in directory.glob(f"*_{suffix}.csv"):
            snapshot_date = _date_from_name(path)
            if snapshot_date is not None and snapshot_date <= through:
                dates.add(snapshot_date)
    return sorted(dates)


def _derived_setup_status(row: pd.Series) -> str:
    status = str(row.get("current_setup_status", "")).upper()
    if status in {
        "ACTIONABLE",
        "DEVELOPING",
        "HISTORICAL_ONLY",
        "NO_SETUP",
        "STALE_DATA",
    }:
        return status
    recommendation = str(row.get("recommendation", "")).upper()
    if recommendation in {"DAY2_ENTRY", "DAY3_ENTRY", "ENTRY_READY", "BUY", "BUY_NOW"}:
        return "ACTIONABLE"
    if "DAY1" in recommendation or "DAY2" in recommendation or "DAY3" in recommendation:
        return "DEVELOPING"
    if recommendation == "HISTORICALLY_STRONG_NO_SIGNAL":
        return "HISTORICAL_ONLY"
    return "NO_SETUP"


def load_snapshot(directory: Path, snapshot_date: pd.Timestamp) -> pd.DataFrame:
    date_text = snapshot_date.strftime("%Y-%m-%d")
    candidate_path = directory / f"{date_text}_trade_candidate_dashboard.csv"
    research_path = directory / f"{date_text}_research_score.csv"
    candidates = _read_csv(candidate_path) if candidate_path.exists() else pd.DataFrame()
    research = _read_csv(research_path) if research_path.exists() else pd.DataFrame()

    columns = ["asset", "research_score", "readiness_pct", "current_setup_status", "recommendation"]
    if candidates.empty and research.empty:
        return pd.DataFrame(columns=["snapshot_date", *columns])

    if not candidates.empty and "asset" in candidates.columns:
        snapshot = candidates[[c for c in columns if c in candidates.columns]].copy()
    else:
        snapshot = pd.DataFrame(columns=["asset"])

    if not research.empty and "asset" in research.columns:
        research_columns = [
            c for c in ["asset", "research_score", "recommendation"] if c in research.columns
        ]
        supplement = research[research_columns].copy()
        if snapshot.empty:
            snapshot = supplement
        else:
            snapshot = snapshot.merge(
                supplement, on="asset", how="outer", suffixes=("", "_research")
            )
            for column in ("research_score", "recommendation"):
                fallback = f"{column}_research"
                if fallback in snapshot.columns:
                    if column not in snapshot.columns:
                        snapshot[column] = snapshot[fallback]
                    else:
                        snapshot[column] = snapshot[column].combine_first(
                            snapshot[fallback]
                        )
                    snapshot = snapshot.drop(columns=fallback)

    snapshot["asset"] = snapshot["asset"].astype(str).str.upper()
    for column in ("research_score", "readiness_pct"):
        if column not in snapshot.columns:
            snapshot[column] = pd.NA
        snapshot[column] = pd.to_numeric(snapshot[column], errors="coerce")
    if "recommendation" not in snapshot.columns:
        snapshot["recommendation"] = pd.NA
    if "current_setup_status" not in snapshot.columns:
        snapshot["current_setup_status"] = pd.NA
    snapshot["current_setup_status"] = snapshot.apply(_derived_setup_status, axis=1)
    snapshot.insert(0, "snapshot_date", date_text)
    return snapshot[
        [
            "snapshot_date",
            "asset",
            "research_score",
            "readiness_pct",
            "current_setup_status",
            "recommendation",
        ]
    ].drop_duplicates("asset", keep="first")


def compare_snapshots(today: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "asset",
        "research_score_today",
        "research_score_previous",
        "research_score_delta",
        "readiness_today",
        "readiness_previous",
        "readiness_delta",
        "current_setup_status",
        "previous_setup_status",
        "newly_emerging",
        "disappearing",
    ]
    if today.empty and previous.empty:
        return pd.DataFrame(columns=columns)

    current = today.drop(columns=["snapshot_date"], errors="ignore").copy()
    prior = previous.drop(columns=["snapshot_date"], errors="ignore").copy()
    snapshot_columns = [
        "asset",
        "research_score",
        "readiness_pct",
        "current_setup_status",
        "recommendation",
    ]
    for frame in (current, prior):
        for column in snapshot_columns:
            if column not in frame.columns:
                frame[column] = pd.NA
    merged = current.merge(prior, on="asset", how="outer", suffixes=("_today", "_previous"))
    for column in ("research_score", "readiness_pct"):
        current_col = f"{column}_today"
        previous_col = f"{column}_previous"
        merged[f"{column}_delta"] = (
            pd.to_numeric(merged.get(current_col), errors="coerce")
            - pd.to_numeric(merged.get(previous_col), errors="coerce")
        ).round(2)

    current_status = merged.get(
        "current_setup_status_today", pd.Series("NO_SETUP", index=merged.index)
    ).fillna("NO_SETUP").astype(str).str.upper()
    previous_status = merged.get(
        "current_setup_status_previous", pd.Series("NO_SETUP", index=merged.index)
    ).fillna("NO_SETUP").astype(str).str.upper()
    merged["newly_emerging"] = current_status.isin(ACTIVE_STATUSES) & ~previous_status.isin(ACTIVE_STATUSES)
    merged["disappearing"] = previous_status.isin(ACTIVE_STATUSES) & ~current_status.isin(ACTIVE_STATUSES)
    merged["current_setup_status"] = current_status
    merged["previous_setup_status"] = previous_status
    merged = merged.rename(
        columns={
            "readiness_pct_today": "readiness_today",
            "readiness_pct_previous": "readiness_previous",
            "readiness_pct_delta": "readiness_delta",
        }
    )
    for column in columns:
        if column not in merged.columns:
            merged[column] = pd.NA
    return merged[columns].sort_values(
        ["research_score_delta", "asset"],
        ascending=[False, True],
        na_position="last",
    ).reset_index(drop=True)


def seven_day_history(
    directory: Path, through: pd.Timestamp = TODAY
) -> pd.DataFrame:
    start = through - timedelta(days=6)
    frames = [
        load_snapshot(directory, snapshot_date)
        for snapshot_date in available_dates(directory, through)
        if snapshot_date >= start
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(
            columns=["snapshot_date", "asset", "research_score", "readiness_pct"]
        )
    return pd.concat(frames, ignore_index=True).sort_values(
        ["snapshot_date", "asset"]
    ).reset_index(drop=True)


def market_rotation_observations(comparison: pd.DataFrame) -> list[str]:
    if comparison.empty:
        return ["Insufficient history for market rotation observations."]
    deltas = pd.to_numeric(comparison["research_score_delta"], errors="coerce")
    valid = comparison[deltas.notna()].copy()
    if valid.empty:
        return ["No comparable Research Score history is available."]

    valid["research_score_delta"] = pd.to_numeric(
        valid["research_score_delta"], errors="coerce"
    )
    improving = int((valid["research_score_delta"] > 0).sum())
    deteriorating = int((valid["research_score_delta"] < 0).sum())
    unchanged = int((valid["research_score_delta"] == 0).sum())
    observations = [
        f"Score breadth: {improving} improving, {deteriorating} deteriorating, {unchanged} unchanged."
    ]
    positive = valid[valid["research_score_delta"] > 0]
    negative = valid[valid["research_score_delta"] < 0]
    if positive.empty:
        observations.append("No asset recorded positive Research Score rotation.")
    else:
        top = positive.sort_values(
            ["research_score_delta", "asset"], ascending=[False, True]
        ).iloc[0]
        observations.append(
            f"Rotation leader: {top['asset']} ({top['research_score_delta']:+.2f} Research Score)."
        )
    if negative.empty:
        observations.append("No asset recorded negative Research Score rotation.")
    else:
        bottom = negative.sort_values(
            ["research_score_delta", "asset"], ascending=[True, True]
        ).iloc[0]
        observations.append(
            f"Rotation laggard: {bottom['asset']} ({bottom['research_score_delta']:+.2f} Research Score)."
        )
    emerging = comparison.loc[comparison["newly_emerging"], "asset"].tolist()
    disappearing = comparison.loc[comparison["disappearing"], "asset"].tolist()
    if emerging:
        observations.append(f"Candidate participation expanded through: {', '.join(emerging)}.")
    if disappearing:
        observations.append(f"Candidate participation contracted through: {', '.join(disappearing)}.")
    return observations


def build_radar(
    directory: Path = REPORT_DIR, through: pd.Timestamp = TODAY
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp | None]:
    dates = available_dates(directory, through)
    today = load_snapshot(directory, through)
    previous_dates = [date for date in dates if date < through]
    previous_date = previous_dates[-1] if previous_dates else None
    previous = (
        load_snapshot(directory, previous_date)
        if previous_date is not None
        else pd.DataFrame()
    )
    return compare_snapshots(today, previous), seven_day_history(directory, through), previous_date


def _fmt(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _trend_lines(history: pd.DataFrame, column: str) -> list[str]:
    if history.empty or column not in history.columns:
        return []
    rows = []
    for asset, group in history.groupby("asset"):
        values = [
            f"{row['snapshot_date']}={_fmt(row[column])}"
            for _, row in group.iterrows()
            if pd.notna(row[column])
        ]
        if values:
            rows.append(f"{asset} | " + " → ".join(values))
    return sorted(rows)


def render_markdown(
    comparison: pd.DataFrame,
    history: pd.DataFrame,
    previous_date: pd.Timestamp | None,
    through: pd.Timestamp = TODAY,
) -> str:
    lines = [
        "# Crypto Research Radar",
        "",
        f"Date: {through:%Y-%m-%d}",
        f"Previous available snapshot: {previous_date:%Y-%m-%d}" if previous_date is not None else "Previous available snapshot: none",
        "",
        "Research reporting only. Existing scores, signals, and thresholds are unchanged.",
    ]

    def add_ranked(title: str, frame: pd.DataFrame, empty: str) -> None:
        lines.extend(["", f"## {title}", ""])
        if frame.empty:
            lines.append(empty)
            return
        for _, row in frame.head(10).iterrows():
            lines.append(
                f"- {row['asset']} | Research Score {_fmt(row['research_score_today'])} | "
                f"previous {_fmt(row['research_score_previous'])} | "
                f"change {_fmt(row['research_score_delta'])}"
            )

    comparable = comparison[
        pd.to_numeric(comparison.get("research_score_delta"), errors="coerce").notna()
    ] if not comparison.empty else comparison
    add_ranked(
        "Fastest Improving Assets",
        comparable[comparable["research_score_delta"] > 0].sort_values(
            ["research_score_delta", "asset"], ascending=[False, True]
        ),
        "No improving assets in the comparable snapshots.",
    )
    add_ranked(
        "Fastest Deteriorating Assets",
        comparable[comparable["research_score_delta"] < 0].sort_values(
            ["research_score_delta", "asset"], ascending=[True, True]
        ),
        "No deteriorating assets in the comparable snapshots.",
    )
    add_ranked(
        "Newly Emerging Candidates",
        comparison[comparison["newly_emerging"]] if not comparison.empty else comparison,
        "No newly emerging current candidates.",
    )
    add_ranked(
        "Disappearing Candidates",
        comparison[comparison["disappearing"]] if not comparison.empty else comparison,
        "No candidates disappeared from the current radar.",
    )

    for title, column in (
        ("Research Score Trend — Last 7 Days", "research_score"),
        ("Readiness Trend — Last 7 Days", "readiness_pct"),
    ):
        lines.extend(["", f"## {title}", ""])
        trends = _trend_lines(history, column)
        if trends:
            lines.extend(f"- {trend}" for trend in trends)
        else:
            lines.append("No historical observations available.")

    lines.extend(["", "## Market Rotation Observations", ""])
    lines.extend(
        f"- {observation}"
        for observation in market_rotation_observations(comparison)
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    comparison, history, previous_date = build_radar()
    comparison.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(render_markdown(comparison, history, previous_date))
    print(f"Saved: {OUT_CSV}")
    print(f"Saved: {OUT_MD}")
    if comparison.empty:
        print("No current or historical research snapshots available.")
    else:
        print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
