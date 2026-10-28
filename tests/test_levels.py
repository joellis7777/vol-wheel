from datetime import timedelta

import numpy as np
import pandas as pd

from vol_wheel import alerts, data, levels
from conftest import ASOF, make_chain_payload


def _hist(closes, lows=None, highs=None):
    idx = pd.bdate_range(end=pd.Timestamp(ASOF), periods=len(closes))
    c = np.asarray(closes, float)
    lo = np.asarray(lows, float) if lows is not None else c * 0.995
    hi = np.asarray(highs, float) if highs is not None else c * 1.005
    return pd.DataFrame({"open": c, "high": hi, "low": lo, "close": c, "volume": 1e6},
                        index=pd.DatetimeIndex(idx, name="date"))


def _swing_low_hist():
    """Flat at 100, a swing low of 90 twenty bars ago, a swing high of 110 forty bars ago, now 95."""
    c = np.full(130, 100.0)
    c[-20], c[-40], c[-12:] = 90.5, 109.5, np.linspace(97.0, 95.0, 12)  # drifting down: no new swing low
    lows, highs = c * 0.995, c * 1.005
    lows[-20], highs[-40] = 90.0, 110.0
    return _hist(c, lows, highs)


def _opts(price, iv):
    exps = [ASOF + timedelta(days=d) for d in (7, 14, 49)]
    return data.parse_chain(make_chain_payload(price=price, atm_iv=iv, expiries=exps))["options"]


def test_put_just_above_a_near_swing_low(rules):
    cfg = rules["level_trades"]
    lt = levels.level_trades(_opts(95.0, 0.5), _swing_low_hist(), 95.0, 0.5, cfg)
    assert lt["dte"] == 7 and lt["note"] is None
    p = lt["put"]
    assert p["level"] == 90.0 and p["near"] and p["active"]
    assert abs(p["limit"] - 90.45) < 1e-9
    ks = [c["strike"] for c in p["candidates"]]
    assert ks == [94.0, 93.0, 92.0]                    # highest first, inside 90-94.5, below the price
    assert all(c["yield_pct"] >= cfg["min_yield_pct"] for c in p["candidates"])
    c = lt["call"]                                       # nearest swing high: the old 100 plateau (highs 100.5)
    assert c["mode"] == "resistance" and abs(c["level"] - 100.5) < 1e-9 and c["near"] and c["active"]
    assert [k["strike"] for k in c["candidates"]] == [96.0, 97.0, 98.0]  # zone 95.5-100.5, above the price


def test_far_swing_low_is_not_near(rules):
    cfg = {**rules["level_trades"], "near_em": 0.5}      # 5 points away vs a ~6.6-point weekly move
    lt = levels.level_trades(_opts(95.0, 0.5), _swing_low_hist(), 95.0, 0.5, cfg)
    assert not lt["put"]["near"] and not lt["put"]["active"] and lt["put"]["candidates"] == []


def test_expiry_spanning_earnings_skips(rules):
    report = (ASOF + timedelta(days=5)).isoformat()
    lt = levels.level_trades(_opts(95.0, 0.5), _swing_low_hist(), 95.0, 0.5, rules["level_trades"], report, "amc")
    assert lt["put"] is None and "spans earnings" in lt["note"]
    # AMC on expiry day settles first: allowed
    same_day = (ASOF + timedelta(days=7)).isoformat()
    assert not levels.spans_report(same_day, "amc", ASOF + timedelta(days=7))
    assert levels.spans_report(same_day, None, ASOF + timedelta(days=7))


def test_price_discovery_calls(rules):
    c = np.concatenate([np.full(120, 100.0), np.linspace(103, 130, 10)])
    hist = _hist(c, highs=c * 1.001)
    lt = levels.level_trades(_opts(130.0, 0.4), hist, 130.0, 0.4, rules["level_trades"])
    call = lt["call"]
    assert call["mode"] == "discovery" and call["stretch_em"] >= 2 and call["active"]
    assert all(k["strike"] >= call["strike_min"] > 130 for k in call["candidates"])
    assert [k["strike"] for k in call["candidates"]] == sorted(k["strike"] for k in call["candidates"])


def test_scope_single_stocks(rules):
    assert levels.in_scope("HOOD", rules) and not levels.in_scope("QQQ", rules)
    assert levels.in_scope("SPY", {**rules, "level_trades": {**rules["level_trades"], "symbols": ["SPY"]}})


def _ticker(level):
    cand = {"strike": 94.0, "expiry": "2026-10-09", "dte": 7, "delta": -0.3, "mid": 1.2, "yield_pct": 1.28,
            "iv": 0.5, "spread_pct": 4.0}
    return {"symbol": "HOOD", "action": "NO_SHORT", "price": 95.0, "regime": "Mid", "ivr": 20, "ivr_source": "proxy",
            "level_trades": {"expiry": "2026-10-09", "dte": 7, "em_week": 6.6,
                             "put": {"level": level, "kind": "swing low", "dist_pct": 5.5, "dist_em": 0.8,
                                     "near": True, "active": True, "limit": level * 1.005, "candidates": [cand]}}}


def test_level_alert_once_per_level(rules):
    msgs, st = alerts.evaluate({"tickers": [_ticker(90.0)]}, {}, "2026-10-02", rules)
    assert [m["trigger"] for m in msgs] == ["LEVEL_PUT"]
    m = msgs[0]
    assert m["title"] == "LEVEL PUT · HOOD" and m["priority"] == "default"
    assert "→ Sell HOOD" in m["body"] and "limit buy at $90.45" in m["body"]
    sym, trig, rec = m["apply"]
    st["tickers"][sym]["alerts"][trig] = rec
    assert rec["level"] == 90.0
    # Next day, same level: quiet. A week later: alerts again. A new level: alerts.
    assert alerts.evaluate({"tickers": [_ticker(90.0)]}, st, "2026-10-05", rules)[0] == []
    assert len(alerts.evaluate({"tickers": [_ticker(90.0)]}, st, "2026-10-09", rules)[0]) == 1
    assert len(alerts.evaluate({"tickers": [_ticker(88.0)]}, st, "2026-10-05", rules)[0]) == 1
