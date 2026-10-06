import pandas as pd
import pytest

from vol_wheel import alerts, data, scan, strikes
from conftest import make_chain_payload
from datetime import date, timedelta
from conftest import ASOF


def test_hedge_puts_picks_otm_targets(rules):
    exps = [ASOF + timedelta(days=d) for d in (45, 75, 104, 140)]
    ch = data.parse_chain(make_chain_payload(price=500.0, expiries=exps))
    hp = strikes.hedge_puts(ch["options"], 500.0, rules["hedge"])
    assert hp["found"]
    assert [p["otm_target"] for p in hp["puts"]] == [10, 15]
    for p in hp["puts"]:
        assert p["dte"] == 104
        assert abs(p["otm_pct"] - p["otm_target"]) <= 1.0


def test_hedge_card_off_by_default_and_conditions(rules):
    assert scan.hedge_card(rules, [], {}, {"regime": "High"}) is None
    on = {**rules, "hedge_alerts": True}
    res = [{"symbol": "SPY", "hedge_puts": {"found": True, "puts": []}}]
    h = scan.hedge_card(on, res, {"_VIX": pd.Series([13.2])}, {"regime": "High"})
    assert h["active"] and "SPY" in h["candidates"]
    assert not scan.hedge_card(on, res, {"_VIX": pd.Series([16.0])}, {"regime": "High"})["active"]
    assert not scan.hedge_card(on, res, {"_VIX": pd.Series([13.0])}, {"regime": "Mid"})["active"]


def test_hedge_alert_once_per_episode(rules, tmp_path):
    sent = []
    rec = lambda m, t, s: sent.append(m) or True
    h = {"enabled": True, "active": True, "vix": 13.1, "vix_max": 14, "spy_regime": "High", "dte": [90, 120],
         "candidates": {"SPY": {"puts": [{"strike": 450.0, "expiry": "2027-01-15", "dte": 104, "otm_pct": 10.0,
                                          "mid": 4.1, "cost": 410.0}]}}}
    r = {"scan_date": "2026-10-05", "tickers": [], "hedge": h}
    path = tmp_path / "s.json"
    assert alerts.process(r, "intraday", rules, path, "t", rec)["sent"] == ["HEDGE · SPY/QQQ puts"]
    assert "SPY $450 put" in sent[0]["body"] and sent[0]["tags"] == ["shield"]
    assert alerts.process(r, "intraday", rules, path, "t", rec)["sent"] == []
    alerts.process({**r, "hedge": {**h, "active": False}, "scan_date": "2026-10-06"}, "close", rules, path, "t", rec)
    assert alerts.process({**r, "scan_date": "2026-10-07"}, "intraday", rules, path, "t", rec)["sent"] == ["HEDGE · SPY/QQQ puts"]
