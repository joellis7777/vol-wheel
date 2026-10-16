"""Long-call convexity sleeve on synthetic paths."""
import copy

import numpy as np
import pandas as pd
import pytest

from vol_wheel import sleeve as SL


@pytest.fixture
def rules(rules):
    r = copy.deepcopy(rules)
    r["backtest"]["costs"] = {"per_contract": 0.0, "slippage_pct_index": 0, "slippage_pct_stock": 0}
    return r


def _frame(closes, iv=0.6):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"close": closes, "iv": iv}, index=idx)


def _run(rules, frame, **variant):
    rates = pd.Series(0.0, index=frame.index)
    v = {"name": "t", "symbols": ["TEST"], "mode": "sleeve", "entry_filter": [], "max_runup_pct": None, **variant}
    return SL.Sleeve(v, frame, rates, rules, frame.index[0], frame.index[-1], 0.3).run()


def test_rally_pays_and_half_comes_off(rules):
    closes = np.r_[np.full(10, 100.0), np.linspace(100, 300, 120)]
    s = _run(rules, _frame(closes))
    res = s.result()
    assert res["sleeve"]["payoff_multiple"] > 1.5
    assert s.stats["exit_half"] >= 1
    # the sleeve is premium-sized: never more than the debit at risk at entry
    assert res["max_dd_pct"] > -6


def test_flat_market_bleeds_at_most_the_debit(rules):
    s = _run(rules, _frame(np.full(400, 100.0)))
    res = s.result()
    assert res["sleeve"]["payoff_multiple"] < 1
    assert s.stats["exit_dte"] >= 1                     # rolled out at 90 DTE, not held to expiry
    assert res["final"] > 0.9 * rules["backtest"]["account"]


def test_entry_filter_waits_for_trend(rules):
    closes = np.r_[np.linspace(200, 100, 300), np.full(50, 100.0)]
    s = _run(rules, _frame(closes), entry_filter=["sma200"])
    assert s.stats["entries"] == 0


def test_spread_caps_the_payoff(rules):
    closes = np.r_[np.full(10, 100.0), np.linspace(100, 400, 150)]
    single = _run(rules, _frame(closes), half_off_pct=None, exit_delta=None).result()
    spread = _run(rules, _frame(closes), short_delta=20, half_off_pct=None, exit_delta=None,
                  short_exit_delta=None).result()
    assert spread["sleeve"]["best_multiple"] < single["sleeve"]["best_multiple"]


def test_strike_solver_handles_upside_skew(rules):
    s = _run(rules, _frame(np.full(30, 100.0)), entry_delta=15, call_skew=-0.3)
    K = s._strike(100.0, 456, 0.6, 0.15, 0.0)
    assert K > 100 and s._delta(100.0, K, 456, 0.6, 0.0) == pytest.approx(0.15, abs=0.01)


def test_hhhl_has_no_lookahead():
    c = pd.Series(np.r_[np.linspace(100, 110, 20), np.linspace(110, 105, 10), np.linspace(105, 120, 20),
                        np.linspace(120, 112, 10), np.linspace(112, 130, 20)])
    full = SL.hhhl_series(c, 3)
    for t in range(30, len(c)):
        assert SL.hhhl_series(c.iloc[:t + 1], 3).iloc[-1] == full.iloc[t]
    assert full.iloc[-1]
