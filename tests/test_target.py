"""Target-allocation scaling on synthetic paths."""
import copy

import numpy as np
import pandas as pd
import pytest

from vol_wheel import target as T


@pytest.fixture
def rules(rules):
    r = copy.deepcopy(rules)
    r["backtest"]["costs"] = {"per_contract": 0.0, "slippage_pct_index": 0, "slippage_pct_stock": 0}
    return r


ALLOC = [[0, 40], [10, 55], [20, 70], [30, 80], [50, 100]]


def _frame(closes, iv=0.25):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"close": closes, "iv": iv, "regime": "Mid", "up": 0.0, "down": 0.0}, index=idx)


def _run(rules, f, **v):
    rates = pd.Series(0.0, index=f.index)
    return T.Target({"name": "t", "symbols": ["X"], "alloc": ALLOC, **v}, f, rates, rules,
                    f.index[0], f.index[-1]).run()


def test_target_fraction_interpolates():
    assert T.target_fraction(0, ALLOC) == pytest.approx(0.40)
    assert T.target_fraction(5, ALLOC) == pytest.approx(0.475)
    assert T.target_fraction(40, ALLOC) == pytest.approx(0.90)
    assert T.target_fraction(80, ALLOC) == pytest.approx(1.00)


def test_stock_execution_follows_drawdown(rules):
    closes = np.r_[np.full(10, 100.0), np.linspace(100, 60, 40), np.full(10, 60.0)]
    s = _run(rules, _frame(closes), exec="stock")
    assert s.in_shares[5] == pytest.approx(0.40, abs=0.06)
    assert s.in_shares[-1] > 0.85                     # 40% down -> ~90% target


def test_options_execution_scales_in_through_assignment(rules):
    closes = np.r_[np.full(10, 100.0), np.linspace(100, 60, 60), np.full(60, 60.0)]
    s = _run(rules, _frame(closes), exec="options")
    assert s.stats["puts_sold"] >= 3 and s.stats["assigned"] >= 1
    assert s.in_shares[-1] > s.in_shares[15]
    assert s.premium > 0


def test_options_calls_only_on_excess(rules):
    closes = np.r_[np.full(10, 100.0), np.linspace(100, 60, 60), np.full(30, 60.0), np.linspace(60, 110, 60),
                   np.full(40, 110.0)]
    s = _run(rules, _frame(closes), exec="options")
    assert s.stats["calls_sold"] >= 1
    assert s.shares >= -1e-9 and s.cash > -1e-6       # never short shares, never borrows


def test_trend_cap_limits_scaling_in_a_falling_market(rules):
    closes = np.r_[np.linspace(60, 100, 260), np.linspace(100, 50, 120)]
    f = _frame(closes)
    free = _run(rules, f, exec="stock")
    capped = _run(rules, f, exec="stock", trend_cap_pct=40)
    assert free.in_shares[-1] > 0.8
    assert capped.in_shares[-1] <= 0.45


def test_core_calls_at_lows(rules):
    closes = np.r_[np.full(10, 100.0), np.linspace(100, 50, 40), np.full(120, 50.0)]
    f = _frame(closes)
    f["regime"] = "Low"
    s = _run(rules, f, exec="options", core_calls={"delta": 10, "max_pct": 25, "regimes": ["Low"]})
    assert s.stats.get("core_calls", 0) >= 1
    assert "2020-03" in s.result()["shares_monthly"]


def test_alloc_gain_scales_out_as_the_bull_matures(rules):
    import numpy as np
    from vol_wheel import target as T
    rules = __import__("copy").deepcopy(rules)
    rules["backtest"]["costs"] = {"per_contract": 0.0, "slippage_pct_index": 0, "slippage_pct_stock": 0}
    idx = pd.bdate_range("2020-01-01", periods=600)
    closes = np.linspace(100, 400, 600)                      # a long rally: +300% from the low
    f = pd.DataFrame({"close": closes, "iv": 0.2, "regime": "Mid", "down": 0.0, "up": 0.0}, index=idx)
    rates = pd.Series(0.0, index=idx)
    base = {"symbols": ["X"], "mode": "target", "exec": "stock", "alloc": [[0, 100], [50, 100]]}
    full = T.Target(base, f, rates, rules, idx[0], idx[-1]).run()
    capped = T.Target({**base, "alloc_gain": [[0, 100], [100, 70], [300, 30]]}, f, rates, rules,
                      idx[0], idx[-1]).run()
    assert full.in_shares[-1] > 0.9 and capped.in_shares[-1] < 0.4
