import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from vol_wheel import data, earnings, scan
from conftest import ASOF, earnings_term_iv, make_chain_payload, make_history

EDATE = ASOF + timedelta(days=12)  # 2026-10-14, a Wednesday


def test_parse_nasdaq_shapes():
    p = {"data": {"announcement": "Earnings announcement* for NVDA: Nov 19, 2026",
                  "reportText": "NVIDIA is estimated to report earnings on 11/19/2026 after market close."}}
    assert earnings.parse_nasdaq(p) == {"date": "2026-11-19", "timing": "amc", "estimated": True}
    p2 = {"data": {"announcement": "", "reportText": "AMZN will report on 10/29/2026 before market open"}}
    assert earnings.parse_nasdaq(p2)["timing"] == "bmo"
    assert earnings.parse_nasdaq({"data": {"announcement": "N/A"}}) is None
    assert earnings.parse_nasdaq({}) is None


def test_reaction_date():
    assert earnings.reaction_date(date(2026, 10, 14), "bmo") == date(2026, 10, 14)
    assert earnings.reaction_date(date(2026, 10, 14), "amc") == date(2026, 10, 15)
    assert earnings.reaction_date(date(2026, 10, 16), None) == date(2026, 10, 19)  # Friday -> Monday


def test_implied_move_recovers_jump(rules):
    ch = data.parse_chain(make_chain_payload(price=100.0, term_iv=earnings_term_iv(ASOF, EDATE, 0.30, 0.06)))
    im = earnings.implied_move(ch["options"], 100.0, EDATE, "amc", ASOF, 0.35, rules["earnings"])
    assert im["feasible"]
    assert im["move"] == pytest.approx(0.06, abs=0.006)
    assert im["base_iv"] == pytest.approx(0.30, abs=0.02)
    # iv30 0.35 with a 6% jump inside 30 days -> ex-earnings sqrt(0.35^2 - 0.06^2 * 365/30)
    assert im["iv30_ex"] == pytest.approx(np.sqrt(0.35 ** 2 - 0.06 ** 2 * 365 / 30), abs=0.02)
    assert im["straddle_move"] > im["move"]  # the straddle also carries base vol


def test_implied_move_infeasible_flat_term(rules):
    # Downward-sloping term structure (no earnings bump) -> e^2 <= 0 -> not feasible
    ch = data.parse_chain(make_chain_payload(price=100.0, term_iv=lambda e: 0.45 if (e - ASOF).days < 20 else 0.30))
    im = earnings.implied_move(ch["options"], 100.0, EDATE, "amc", ASOF, 0.35, rules["earnings"])
    assert not im["feasible"] and im["iv30_ex"] is None


def test_trend_and_post_gap(rules):
    close = pd.Series([100.0] * 30 + [100, 101, 102, 103, 104, 108],
                      index=pd.bdate_range(end="2026-10-02", periods=36))
    tr = earnings.trend(close, 5, 0.20)
    assert tr["ret"] == pytest.approx(0.08)
    assert tr["z"] == pytest.approx(0.08 / (0.20 * np.sqrt(5 / 252)))
    # AMC report on Thu 10-01 -> reaction Fri 10-02: +3.85% vs implied 2% -> 1.9x -> spike
    last = {"date": "2026-10-01", "timing": "amc", "implied_move": 0.02}
    g = earnings.post_gap(close, last, date(2026, 10, 2), rules["earnings"])
    assert g and g["dir"] == "up" and g["ratio"] == pytest.approx((108 / 104 - 1) / 0.02)
    assert earnings.post_gap(close, {**last, "implied_move": 0.05}, date(2026, 10, 2), rules["earnings"]) is None
    # too long ago: reaction more than 3 sessions back
    assert earnings.post_gap(close, {**last, "date": "2026-09-24"}, date(2026, 10, 2), rules["earnings"]) is None


def test_refresh_moves_past_report_to_last_and_survives_failures(rules, tmp_path):
    cfg = {**rules["earnings"], "cache_path": str(tmp_path / "earn.json")}
    (tmp_path / "earn.json").write_text(json.dumps({
        "NVDA": {"next": {"date": "2026-10-01", "timing": "amc"}, "implied_move": 0.07, "fetched": "2026-10-01"},
        "TSLA": {"next": {"date": "2026-10-21", "timing": "amc"}, "fetched": "2026-10-01"}}))

    def fetch(sym):
        if sym == "TSLA":
            raise ConnectionError("blocked")
        return {"date": "2026-11-19", "timing": "amc", "estimated": True, "source": "nasdaq"}

    cache, notes = earnings.refresh(["NVDA", "TSLA"], date(2026, 10, 2), cfg, fetch)
    assert cache["NVDA"]["last"]["date"] == "2026-10-01" and cache["NVDA"]["last"]["implied_move"] == 0.07
    assert cache["NVDA"]["next"]["date"] == "2026-11-19"
    assert cache["TSLA"]["next"]["date"] == "2026-10-21"  # kept from cache
    assert any("TSLA" in n and "fetch failed" in n for n in notes)


def test_earnings_context_etf_and_window(rules):
    ch = data.parse_chain(make_chain_payload(price=100.0))
    assert earnings.earnings_context("SPY", {}, ch["options"], 100, 0.3, ASOF, None, rules["earnings"]) == {"applies": False}
    cache = {"NVDA": {"next": {"date": EDATE.isoformat(), "timing": "amc"}}}
    ctx = earnings.earnings_context("NVDA", cache, ch["options"], 100, 0.3, ASOF, date(2026, 11, 20), rules["earnings"])
    assert ctx["days_to"] == 12 and ctx["in_window"] and ctx["in_iv_window"]


def _dec(rules, ivr=60, down=0.0, up=0.0, iv_hv=1.3, earn=None, regime="Mid"):
    return scan.decide_action(ivr, {"down": down, "up": up}, regime, False, 0.5, True, "core", rules, iv_hv, earn)


def test_iv_hv_filter(rules):
    assert _dec(rules, down=2.0, iv_hv=1.20)["action"] == "SELL_PUT"
    d = _dec(rules, down=2.0, iv_hv=1.10)
    assert d["action"] == "WATCH" and "IV/HV 1.10 < 1.15" in d["reasons"][0]
    assert _dec(rules, up=2.0, iv_hv=1.10)["action"] == "WATCH"
    assert _dec(rules, down=2.0, iv_hv=None)["action"] == "SELL_PUT"  # no HV: filter can't apply


def test_earnings_mode_blocks_normal_and_plays(rules):
    d = _dec(rules, down=2.0, earn={"in_window": True, "date": "2026-10-14", "days_to": 12})
    assert d["action"] == "WATCH" and "earnings mode" in d["reasons"][0]
    d = _dec(rules, down=2.0, earn={"inflated": True, "date": "2026-10-14"})
    assert d["action"] == "WATCH" and any("earnings-inflated" in r for r in d["reasons"])
    play = {"side": "C", "ret": 0.08, "z": 1.9}
    d = _dec(rules, ivr=20, earn={"in_window": True, "date": "2026-10-14", "days_to": 12, "play": play})
    assert d["action"] == "EARNINGS_PLAY" and "call after a run-up" in d["reasons"][0]


def test_post_earnings_gap_counts_as_spike(rules):
    spk = {"down": 0.8, "up": 0.0, "earnings_gap": {"dir": "down", "move": -0.09, "ratio": 1.8, "implied_move": 0.05}}
    spk["down"] = max(spk["down"], rules["thresholds"]["spike_sigma"])
    d = scan.decide_action(60, spk, "Mid", False, 0.5, True, "core", rules, 1.3, {})
    assert d["action"] == "SELL_PUT" and "Post-earnings gap" in d["reasons"][0]


def _ticker_inputs(trend_up=True, edate=EDATE):
    hist = make_history(n=800, start=60, vol=0.012, seed=11, end=date(2026, 10, 1))
    if trend_up:
        f = np.r_[np.ones(len(hist) - 5), np.linspace(1.01, 1.07, 5)]
        for c in ("open", "high", "low", "close"):
            hist[c] = hist[c] * f
    price = round(float(hist["close"].iloc[-1]) * 1.01, 2)
    ch = data.parse_chain(make_chain_payload(sym="TST", price=price, oi=500, spread_frac=0.02,
                                             term_iv=earnings_term_iv(ASOF, edate, 0.30, 0.06)))
    ch["iv30"] = 0.36  # a real iv30 carries the earnings bump
    return hist, ch, price


def test_scan_ticker_earnings_play_end_to_end(rules, tmp_path, monkeypatch):
    from vol_wheel import ivhistory
    monkeypatch.setattr(ivhistory, "DIR", tmp_path)
    hist, ch, price = _ticker_inputs()
    cache = {"TST": {"next": {"date": EDATE.isoformat(), "timing": "amc"}}}
    t = {"symbol": "TST", "bucket": "Test", "role": "core", "cap": 10}
    r = scan.scan_ticker(t, rules, {"on": True}, {}, append=True, chain=ch, hist=hist, earn_cache=cache, today=ASOF)
    assert r["earnings"]["in_window"] and r["earnings"]["days_to"] == 12
    assert r["ivr_flag"] == "ex-earnings" and r["iv30_ex"] < r["iv30"]
    assert r["iv30_ex"] == pytest.approx(0.30, abs=0.03)
    assert r["action"] == "EARNINGS_PLAY" and r["earnings"]["play"]["side"] == "C"
    ep = r["earnings_play"]
    assert ep["side"] == "C" and ep["size_frac"] == 0.5
    lim = price * (1 + 1.5 * ep["move"])
    assert ep["calls"]["candidates"]
    for c in ep["calls"]["candidates"]:
        assert c["strike"] >= lim - 1e-6 and 10 <= c["delta"] * 100 <= 15
    assert cache["TST"]["implied_move"] == pytest.approx(ep["move"])
    # IV history keeps raw iv30 and the ex-earnings value
    row = (tmp_path / "TST.csv").read_text().splitlines()
    assert row[0] == "date,iv30,price,iv30_ex" and row[1].split(",")[3] != ""


def test_scan_ticker_leap_variants(rules, tmp_path, monkeypatch):
    from vol_wheel import ivhistory
    monkeypatch.setattr(ivhistory, "DIR", tmp_path)
    hist, ch, _ = _ticker_inputs(trend_up=False)
    t = {"symbol": "SPY", "bucket": "Index", "role": "core", "cap": 25}
    r = scan.scan_ticker(t, rules, {"on": True}, {}, append=False, chain=ch, hist=hist, earn_cache={}, today=ASOF)
    assert r["earnings"] is None  # ETF
    ira, tax = r["leaps"]["ira"], r["leaps"]["taxable"]
    assert ira["found"] and 365 <= ira["dte"] <= 548
    assert tax["found"] and 487 <= tax["dte"] <= 548
    assert "don't sell calls" in tax["variant_note"]
    assert r["leap"] == ira


def test_session_date():
    utc = lambda *a: datetime(*a, tzinfo=timezone.utc)
    assert data.session_date(utc(2026, 10, 6, 1, 51)) == date(2026, 10, 5)    # 21:51 ET Monday
    assert data.session_date(utc(2026, 10, 6, 15, 0)) == date(2026, 10, 6)    # 11:00 ET Tuesday
    assert data.session_date(utc(2026, 10, 6, 12, 0)) == date(2026, 10, 5)    # 08:00 ET: pre-open
    assert data.session_date(utc(2026, 10, 4, 18, 0)) == date(2026, 10, 2)    # Sunday -> Friday
    assert data.session_date(utc(2026, 10, 5, 12, 0)) == date(2026, 10, 2)    # Monday pre-open -> Friday


def test_flat_term_structure_means_no_bump(rules):
    ch = data.parse_chain(make_chain_payload(price=100.0, atm_iv=0.30))
    im = earnings.implied_move(ch["options"], 100.0, EDATE, "amc", ASOF, 0.30, rules["earnings"])
    assert im["feasible"] and im["move"] is None and im["iv30_ex"] == pytest.approx(0.30)
    # far-away first post-earnings expiry: the straddle is mostly base vol, so no fallback
    far = ASOF + timedelta(days=40)
    im2 = earnings.implied_move(ch["options"], 100.0, far, "amc", ASOF, 0.30, rules["earnings"])
    assert im2["straddle_move"] is None and earnings.move_for_strikes(im2) is None


def test_ex_earnings_iv_never_below_base(rules):
    # iv30 that holds little of the jump: plain subtraction would collapse it; floor at base vol
    ch = data.parse_chain(make_chain_payload(price=100.0, term_iv=earnings_term_iv(ASOF, EDATE, 0.30, 0.06)))
    im = earnings.implied_move(ch["options"], 100.0, EDATE, "amc", ASOF, 0.31, rules["earnings"])
    assert im["iv30_ex"] == pytest.approx(min(im["base_iv"], 0.31), abs=1e-9)
