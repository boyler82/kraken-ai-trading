def max_drawdown(equity_series):
    peak = equity_series.cummax()
    dd = equity_series / peak - 1
    return dd.min() * 100