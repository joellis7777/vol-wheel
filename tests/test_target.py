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
