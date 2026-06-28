import pandas as pd


def clean(value):
    if value is None or pd.isna(value):
        return None
    return float(round(value, 2))


def trade_metrics(returns_pct):
    """
    returns_pct: list/Series of trade returns in percent, e.g. [1.2, -0.5, 3.0]
    """

    s = pd.Series(returns_pct).dropna()

    if s.empty:
        return {
            "trades": 0,
            "win_rate_pct": None,
            "avg_return_pct": None,
            "median_return_pct": None,
            "avg_win_pct": None,
            "avg_loss_pct": None,
            "profit_factor": None,
            "expected_value_pct": None,
            "worst_return_pct": None,
            "best_return_pct": None,
            "quality_score": None,
        }

    wins = s[s > 0]
    losses = s[s < 0]

    win_rate = float((s > 0).mean())
    loss_rate = float((s < 0).mean())

    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0

    gross_profit = float(wins.sum())
    gross_loss = abs(float(losses.sum()))

    profit_factor = None
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss

    expected_value = (win_rate * avg_win) + (loss_rate * avg_loss)

    quality_score = calculate_quality_score(
        expected_value_pct=expected_value,
        profit_factor=profit_factor,
        win_rate_pct=win_rate * 100,
        median_return_pct=float(s.median()),
    )

    return {
        "trades": int(len(s)),
        "win_rate_pct": clean(win_rate * 100),
        "avg_return_pct": clean(float(s.mean())),
        "median_return_pct": clean(float(s.median())),
        "avg_win_pct": clean(avg_win),
        "avg_loss_pct": clean(avg_loss),
        "profit_factor": clean(profit_factor),
        "expected_value_pct": clean(expected_value),
        "worst_return_pct": clean(float(s.min())),
        "best_return_pct": clean(float(s.max())),
        "quality_score": clean(quality_score),
    }


def calculate_quality_score(
    expected_value_pct,
    profit_factor,
    win_rate_pct,
    median_return_pct=0,
):
    """
    Composite research score for historical edge quality.
    Higher is better.

    Inputs are expected in percent where applicable.
    """

    if expected_value_pct is None or pd.isna(expected_value_pct):
        return 0

    if profit_factor is None or pd.isna(profit_factor):
        profit_factor = 0

    if win_rate_pct is None or pd.isna(win_rate_pct):
        win_rate_pct = 0

    if median_return_pct is None or pd.isna(median_return_pct):
        median_return_pct = 0

    score = (
        expected_value_pct * 40
        + profit_factor * 20
        + win_rate_pct * 0.4
    )

    if median_return_pct > 0:
        score += 10

    return score
