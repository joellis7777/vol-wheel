import json
import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from vol_wheel import data, ivhistory, scan
from conftest import ASOF, make_chain_payload, make_history


def test_parse_occ():
    assert data.parse_occ("SPY261120P00550000") == ("SPY", date(2026, 11, 20), "P", 550.0)
    assert data.parse_occ("BRKB261120C00412500")[3] == 412.5
    assert data.parse_occ("garbage") is None


def test_parse_chain_units():
    p = make_chain_payload(price=50.0, atm_iv=0.4)
    ch = data.parse_chain(p)
    assert ch["price"] == 50.0
    assert ch["iv30"] == pytest.approx(0.4)
    assert ch["asof"] == ASOF
    o = ch["options"]
    assert set(o["type"]) == {"C", "P"}
    assert o["iv"].median() < 3
    assert (o["dte"] > 0).all()
    # percent-unit IV/delta get normalized
    for opt in p["data"]["options"]:
        opt["iv"] *= 100
        opt["delta"] *= 100
    o2 = data.parse_chain(p)["options"]
    assert o2["iv"].median() < 3 and o2["delta"].abs().max() <= 1.0


def test_parse_history_strings():
    payload = {"symbol": "X", "data": [
        {"date": "2026-10-01", "open": "10", "high": "11", "low": "9", "close": "10.5", "volume": "100"},
        {"date": "2026-10-02", "open": 10.5, "high": 12, "low": 10, "close": 11.5, "volume": 200},
        {"date": "bad", "close": 1},
    ]}
    h = data.parse_history(payload)
    assert list(h["close"]) == [10.5, 11.5]
    assert h.index[-1] == pd.Timestamp("2026-10-02")


def test_with_today_appends_and_skips_weekend():
    h = make_history(n=50, end=date(2026, 10, 1))
    ch = data.parse_chain(make_chain_payload(price=123.0, asof=date(2026, 10, 2)))
    h2 = data.with_today(h, ch)
    assert len(h2) == 51 and h2["close"].iloc[-1] == 123.0
    # Saturday fetch maps to Friday, already present -> no extra bar
    ch_sat = data.parse_chain(make_chain_payload(price=123.0, asof=date(2026, 10, 3)))
    assert len(data.with_today(h2, ch_sat)) == 51


def test_ivhistory_roundtrip(tmp_path):
    ivhistory.append("ABC", date(2026, 10, 1), 0.25, 100, base=tmp_path)
    ivhistory.append("ABC", date(2026, 10, 2), 0.30, 101, base=tmp_path)
    ivhistory.append("ABC", date(2026, 10, 2), 0.31, 101, base=tmp_path)  # same day replaces
    s = ivhistory.load("ABC", base=tmp_path)
    assert len(s) == 2 and s.iloc[-1] == pytest.approx(0.31)


def test_compute_ivr_sources(rules):
    close = make_history(n=400)["close"]
    short = pd.Series([0.2] * 10)
    assert scan.compute_ivr("X", 0.3, short, close, rules)["source"] == "proxy"
    vix = pd.Series(np.linspace(12, 30, 300))
    r = scan.compute_ivr("SPY", 0.3, short, close, rules, vix, "_VIX")
    assert r["source"] == "VIX" and r["ivr"] == pytest.approx(100)
    hist = pd.Series(np.linspace(0.2, 0.4, 100))
    r = scan.compute_ivr("X", 0.3, hist, close, rules)
    assert r["source"] == "partial" and r["ivr"] == pytest.approx(50, abs=1)
    full = pd.Series(np.linspace(0.2, 0.4, 300))
    assert scan.compute_ivr("X", 0.3, full, close, rules)["source"] == "true"


def _dec(rules, ivr, down=0.0, up=0.0, regime="Mid", cons=False, rpos=0.5, gate=True, role="core"):
    return scan.decide_action(ivr, {"down": down, "up": up}, regime, cons, rpos, gate, role, rules)


def test_decide_action(rules):
    assert _dec(rules, 60, down=2.0)["action"] == "SELL_PUT"
    assert _dec(rules, 60, up=2.0)["action"] == "SELL_CALL"
    assert _dec(rules, 60, down=1.0)["action"] == "WATCH"
    assert _dec(rules, 40)["action"] == "NEUTRAL"
    assert _dec(rules, 20)["action"] == "NO_SHORT"
    assert _dec(rules, 20, cons=True, rpos=0.2)["action"] == "LEAP_BUY"
    assert _dec(rules, 20, cons=True, rpos=0.2, regime="High")["action"] == "NO_SHORT"
    assert _dec(rules, 20, cons=True, rpos=0.2, gate=False)["action"] == "NO_SHORT"
    assert _dec(rules, 20, cons=True, rpos=0.2, role="opportunistic")["action"] == "NO_SHORT"
    assert _dec(rules, 20, cons=True, rpos=0.5)["action"] == "NO_SHORT"
    both = _dec(rules, 75, down=2.0, regime="Mid")
    assert both["both_sides"]
    assert not _dec(rules, 75, down=2.0, regime="Low")["both_sides"]
    assert _dec(rules, float("nan"))["action"] == "NO_DATA"


def test_scan_ticker_end_to_end(rules, tmp_path, monkeypatch):
    monkeypatch.setattr(ivhistory, "DIR", tmp_path)
    hist = make_history(n=800, start=60, vol=0.012, seed=5, end=date(2026, 10, 1), shocks={1: -0.05})
    price = float(hist["close"].iloc[-1]) * 0.97
    ch = data.parse_chain(make_chain_payload(sym="TST", price=round(price, 2), atm_iv=0.35))
    t = {"symbol": "TST", "bucket": "Test", "role": "core", "cap": 10}
    gate = {"on": True}
    r = scan.scan_ticker(t, rules, gate, {}, append=True, chain=ch, hist=hist)
    assert r["ivr_source"] == "proxy"
    assert r["regime"] in ("Low", "Mid", "High")
    assert r["dte"] and 35 <= r["dte"] <= 50
    assert len(r["puts"]["candidates"]) <= 3 and r["puts"]["candidates"]
    assert r["calls"]["candidates"]
    assert r["leap"]["found"]
    assert r["ladder"][0]["strike"] == r["puts"]["candidates"][0]["strike"]
    assert (tmp_path / "TST.csv").exists()
    # JSON-safe after cleaning
    json.dumps(scan.clean(r), allow_nan=False)


def test_scan_ticker_no_append(rules, tmp_path, monkeypatch):
    monkeypatch.setattr(ivhistory, "DIR", tmp_path)
    hist = make_history(n=400, end=date(2026, 10, 1))
    ch = data.parse_chain(make_chain_payload(sym="TST", price=float(hist["close"].iloc[-1])))
    t = {"symbol": "TST", "bucket": "Test", "role": "opportunistic", "cap": 10}
    r = scan.scan_ticker(t, rules, {"on": False}, {}, append=False, chain=ch, hist=hist)
    assert r["iv_history_days"] == 1 and not (tmp_path / "TST.csv").exists()


def test_coverage_reports_missing_and_failed(rules):
    results = [{"symbol": "SPY", "action": "WATCH", "notes": []},
               {"symbol": "HOOD", "action": "ERROR", "reasons": ["CBOE history failed: 403"], "notes": []},
               {"symbol": "CEG", "action": "NO_SHORT", "notes": ["option chain unavailable: timeout"]}]
    cov = scan.coverage(rules, results)
    assert cov["expected"] == 15 and cov["present"] == 3
    assert "GLD" in cov["missing"] and "SPY" not in cov["missing"]
    assert cov["failed"] == {"HOOD": "CBOE history failed: 403"}
    assert cov["no_chain"] == ["CEG"]


def test_iv_hv_uses_realized_vol_from_before_the_move(rules, tmp_path, monkeypatch):
    """CEG 2026-10-06: a +13% day inflates HV20 and would fail IV/HV against itself."""
    monkeypatch.setattr(ivhistory, "DIR", tmp_path)
    hist = make_history(n=400, start=60, vol=0.01, seed=31, end=date(2026, 10, 1), shocks={1: 0.13})
    ch = data.parse_chain(make_chain_payload(sym="TST", price=round(float(hist["close"].iloc[-1]), 2), atm_iv=0.30))
    t = {"symbol": "TST", "bucket": "Test", "role": "core", "cap": 10}
    r = scan.scan_ticker(t, rules, {"on": True}, {}, append=False, chain=ch, hist=hist, earn_cache={})
    assert r["hv20_ref"] < 0.25 < r["hv20"]               # pre-move HV ~16%, with the spike ~47%
    assert r["iv_hv"] == pytest.approx(r["iv30"] / r["hv20_ref"])
    assert r["iv_hv_ok"] and r["spike"]["dir"] == "up" and r["spike"]["is_spike"]
    off = {**rules, "thresholds": {**rules["thresholds"], "iv_hv_pre_move": False}}
    r2 = scan.scan_ticker(t, off, {"on": True}, {}, append=False, chain=ch, hist=hist, earn_cache={})
    assert r2["iv_hv"] == pytest.approx(r2["iv30"] / r2["hv20"]) and not r2["iv_hv_ok"]
