"""Poor man's covered call simulator on synthetic paths."""
import copy

import numpy as np
import pandas as pd
import pytest

from vol_wheel import pmcc as P


@pytest.fixture
def rules(rules):
    r = copy.deepcopy(rules)
    r["backtest"]["costs"] = {"per_contract": 0.0, "slippage_pct_index": 0, "slippage_pct_stock": 0}
    r["backtest"]["pmcc"]["slippage_pct_leap"] = 0.0
    return r


def _frame(closes, iv=0.20, ivr=30.0, up=0.0, regime="Mid"):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"close": closes, "iv": iv, "ivr": ivr, "up": up, "regime": regime}, index=idx)


def _run(rules, frame, variant):
    rates = pd.Series(0.0, index=frame.index)
    v = {"name": "t", "symbols": ["TEST"], "mode": "pmcc", **variant}
    return P.PMCC(v, frame, rates, rules, frame.index[0], frame.index[-1]).run()


def test_trend_and_rsi():
    up = pd.Series(np.linspace(100, 150, 300))
    tf = P.trend_frame(up, {})
    assert tf["trend"].iloc[-1] == "up" and tf["rsi"].iloc[-1] > 90
    dn = pd.Series(np.linspace(150, 100, 300))
    assert P.trend_frame(dn, {})["trend"].iloc[-1] == "down"
    flat = pd.Series(np.full(300, 100.0))
    assert P.trend_frame(flat, {})["trend"].iloc[-1] == "neutral"


def test_leap_alone_loses_time_value_when_flat(rules):
    f = _frame(np.full(120, 100.0))
    s = _run(rules, f, {"long": "leap", "calls": "none"})
    assert s.stats["entries"] == 1
    assert s.equity[-1] < 500000                      # theta, no interest at r=0
    assert s.equity[-1] > 500000 * 0.9


def test_weekly_calls_harvest_premium_when_flat(rules):
    f = _frame(np.full(120, 100.0))
    s = _run(rules, f, {"long": "leap", "calls": "trend"})
    assert s.stats["calls_sold"] >= 8
    assert s.call_pnl > 0
    bare = _run(rules, f, {"long": "leap", "calls": "none"})
    assert s.equity[-1] > bare.equity[-1]


def test_calls_cost_upside_in_a_rally(rules):
    # +5% jumps every week: realized vol far above the 20% IV the calls were sold at
    f = _frame(100 * 1.05 ** (np.arange(120) // 5))
    with_calls = _run(rules, f, {"long": "shares", "calls": "trend"})
    without = _run(rules, f, {"long": "shares", "calls": "none"})
    assert with_calls.call_pnl < 0
    assert with_calls.equity[-1] < without.equity[-1]


def test_stop_and_target_exits(rules):
    crash = _frame(np.r_[np.full(5, 100.0), np.linspace(100, 85, 10), np.full(20, 85.0)])
    s = _run(rules, crash, {"long": "leap", "calls": "none", "exits": {"target_pct": 100, "stop_pct": -30}})
    assert s.stats["exit_stop"] >= 1
    rally = _frame(np.r_[np.full(5, 100.0), np.linspace(100, 125, 20), np.full(5, 125.0)])
    s2 = _run(rules, rally, {"long": "leap", "calls": "none", "exits": {"target_pct": 100, "stop_pct": -30}})
    assert s2.stats["exit_target"] + s2.stats["exit_half"] >= 1


def test_entry_filter_waits_for_uptrend(rules):
    closes = np.r_[np.linspace(120, 90, 250), np.linspace(90, 130, 150)]
    f = _frame(closes)
    s = _run(rules, f, {"long": "leap", "calls": "none", "entry_filter": "tom"})
    first_in = next(i for i, x in enumerate(s.exposure) if x > 0)
    assert first_in > 250                             # not while below the 200-day / in a downtrend
