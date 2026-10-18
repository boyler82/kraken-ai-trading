from __future__ import annotations

from pathlib import Path

import pandas as pd


OPEN_POSITION_STATUS = "OPEN"
NO_OPEN_POSITIONS = "No open positions"


def active_positions(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only officially open portfolio rows; blank/unknown statuses are inactive."""
    if frame.empty or "status" not in frame.columns:
        return frame.iloc[0:0].copy()
    statuses = frame["status"].fillna("").astype(str).str.strip().str.upper()
    return frame.loc[statuses.eq(OPEN_POSITION_STATUS)].copy()


def load_active_positions(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return active_positions(pd.read_csv(path))
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def open_position_assets(frame: pd.DataFrame) -> list[str]:
    open_frame = active_positions(frame)
    if open_frame.empty:
        return []
    column = next((name for name in ("asset", "symbol", "ticker", "pair") if name in open_frame.columns), None)
    if column is None:
        return []
    return sorted({str(value).strip().upper() for value in open_frame[column].dropna() if str(value).strip()})


def open_position_summary(frame: pd.DataFrame) -> str:
    assets = open_position_assets(frame)
    if not assets:
        return NO_OPEN_POSITIONS
    return f"Open positions ({len(assets)}): {', '.join(assets)}"


def open_position_count(frame: pd.DataFrame) -> int:
    return len(open_position_assets(frame))
