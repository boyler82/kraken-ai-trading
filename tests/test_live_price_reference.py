from __future__ import annotations
import copy
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import live_price_reference as live

def packet():
    return {"candidates":[{"asset":"ATOM","identity":{"kraken_pair":"ATOMUSD"},"current_data":{"analysis_price":1.5384,"analysis_price_timestamp":"2026-09-05T05:00:00+00:00","current_price":1.5384},"decision_metrics":{"decision_impact_score":42},"momentum":{"stage":"NO_MOMENTUM","confirmation_closes":0},"consolidation":{"range_low":1.4}}],"tactical_opportunities":{"daily":[{"asset":"ATOM","analysis_price":1.5384,"current_price":1.5384}],"weekly":[],"avoid":[]}}

def test_live_quote_is_additive_and_drift_is_correct():
    original=packet();before=copy.deepcopy(original)
    live.attach_live_references(original,lambda pairs:{"ATOMUSD":{"price":1.6,"timestamp":"2026-09-05T06:00:00Z"}},"2026-09-05T06:00:10Z")
    row=original["candidates"][0];data=row["current_data"]
    assert data["analysis_price"] == before["candidates"][0]["current_data"]["analysis_price"]
    assert data["current_price"] == 1.5384
    assert data["live_reference_price"] == 1.6
    assert data["live_price_age_seconds"] == 10
    assert abs(data["price_drift_pct"] - (1.6/1.5384-1)*100) < 1e-12
    assert row["decision_metrics"] == before["candidates"][0]["decision_metrics"]
    assert row["momentum"] == before["candidates"][0]["momentum"]
    assert row["consolidation"] == before["candidates"][0]["consolidation"]

def test_stale_quote_is_never_exposed_as_live_or_fallback():
    value=packet();live.attach_live_references(value,lambda pairs:{"ATOMUSD":{"price":1.6,"timestamp":"2026-09-05T05:58:00Z"}},"2026-09-05T06:00:00Z",60)
    data=value["candidates"][0]["current_data"]
    assert data["live_price_status"] == "LIVE_PRICE_STALE"
    assert data["live_reference_price"] is None and data["price_drift_pct"] is None
    assert data["live_reference_price"] != data["analysis_price"]

def test_unavailable_quote_has_no_silent_analysis_fallback():
    for fetcher in (lambda pairs:{}, lambda pairs:(_ for _ in ()).throw(OSError("offline"))):
        value=packet();live.attach_live_references(value,fetcher,"2026-09-05T06:00:00Z")
        data=value["candidates"][0]["current_data"]
        assert data["live_price_status"] == "LIVE_PRICE_UNAVAILABLE"
        assert data["live_reference_price"] is None and data["price_drift_pct"] is None
        assert value["tactical_opportunities"]["daily"][0]["live_reference_price"] is None

def test_only_public_ticker_market_data_capability_exists():
    source=Path(live.__file__).read_text().lower()
    assert live.PUBLIC_TICKER_ENDPOINT == "https://api.kraken.com/0/public/Ticker"
    assert "/private/" not in source
    assert "addorder" not in source and "cancelorder" not in source
    assert "api-key" not in source and "api-sign" not in source


def test_legacy_ticker_keys_preserve_real_x_prefix_and_do_not_guess():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'error': [], 'result': {
                key: {'b': ['100'], 'a': ['102']} for key in
                ('XXLMZUSD', 'XXRPZUSD', 'XXMRZUSD', 'XXBTZUSD', 'XETHZUSD')
            }}).encode()
    quotes = live.fetch_public_mid_prices(
        ['XLMUSD', 'XRPUSD', 'XMRUSD', 'XBTUSD', 'ETHUSD', 'WRONGUSD'],
        opener=lambda *args, **kwargs: Response())
    assert set(quotes) == {'XLMUSD', 'XRPUSD', 'XMRUSD', 'XBTUSD', 'ETHUSD'}
    assert all(q['price'] == 101 for q in quotes.values())
    class Unrelated(Response):
        def read(self):
            return json.dumps({'error': [], 'result': {'ETHUSD': {'b': ['100'], 'a': ['102']}}}).encode()
    assert live.fetch_public_mid_prices(['XLMUSD'], opener=lambda *a, **k: Unrelated()) == {}
