import pandas as pd


def clean(value):
    if value is None:
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
    }