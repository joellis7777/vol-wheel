"""Multi-asset core rebalanced with options or stock, synthetic paths."""
import copy

import numpy as np
import pandas as pd
import pytest

from vol_wheel import multi as M


@pytest.fixture
def rules(rules):
    r = copy.deepcopy(rules)
    r["backtest"]["costs"] = {"per_contract": 0.0, "slippage_pct_index": 0, "slippage_pct_stock": 0}
    return r


def _frame(closes, iv=0.25):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"close": closes, "iv": iv, "regime": "Mid", "up": 0.0, "down": 0.0}, index=idx)


def _run(rules, frames, **v):
    idx = next(iter(frames.values())).index
    rates = pd.Series(0.0, index=idx)
    variant = {"name": "t", "weights": {"A": 50, "B": 50}, **v}
    return M.Multi(variant, frames, rates, rules, idx[0], idx[-1], {"A": 0.3, "B": 0.3}, set()).run()


def test_starts_at_target_weights(rules):
    f = {"A": _frame(np.full(30, 100.0)), "B": _frame(np.full(30, 50.0))}
    s = _run(rules, f, exec="stock")
    assert s.weights_hist[0]["A"] == pytest.approx(0.5, abs=1e-3)
    assert s.weights_hist[0]["B"] == pytest.approx(0.5, abs=1e-3)


def test_stock_rebalances_drift(rules):
    f = {"A": _frame(np.linspace(100, 200, 120)), "B": _frame(np.full(120, 100.0))}
    s = _run(rules, f, exec="stock", band_pct=2)
    assert s.stats["stock_trades"] > 2
    assert abs(s.weights_hist[-1]["A"] - 0.5) < 0.03


def test_options_rebalance_with_puts_and_calls(rules):
    f = {"A": _frame(np.linspace(100, 160, 200)), "B": _frame(np.linspace(100, 80, 200))}
    # puts need cash: with 20% held back (SGOV) the underweight side is bought through puts
    s = _run(rules, f, exec="options", band_pct=2, slice_pct=5, invested_pct=80)
    assert s.stats["calls_sold"] >= 1 and s.stats["puts_sold"] >= 1
    assert s.cash > -1e-6 and min(s.shares.values()) >= -1e-9
    assert s.premium > 0


def test_fully_invested_options_cannot_sell_puts_without_cash(rules):
    f = {"A": _frame(np.full(60, 100.0)), "B": _frame(np.linspace(100, 70, 60))}
    s = _run(rules, f, exec="options", band_pct=2, slice_pct=5)
    assert s.stats["puts_sold"] == 0                  # no cash to secure them
