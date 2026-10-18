"""Explicit public hourly BTC dependency for production measurement."""
from pathlib import Path
from .outcomes import load_bars
from .lifecycle import preflight


def refresh_hourly_btc(root, as_of):
    from weekly_intraday_market_backfill import update_pair, INTRADAY_DIR
    expected = Path(root) / 'DATASETS/market_intraday_weekly'
    if expected.resolve() != Path(INTRADAY_DIR).resolve():
        raise ValueError('BTC_HOURLY_REFRESH_ROOT_MISMATCH')
    # update_pair uses unauthenticated /0/public/OHLC, interval=60.
    update_pair('XBTUSD', as_of, no_network=False)
    return preflight([], load_bars(expected/'XBTUSD_1H.csv'), as_of)
