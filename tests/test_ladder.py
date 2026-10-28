"""Ladder: limit orders fill on a touch, puts at the same level only if price is below it at expiry."""
import numpy as np
import pandas as pd

from vol_wheel.config import load_rules
from vol_wheel.ladder import Ladder

V = {"buy_rungs": [[10, 20]], "scale_out": [], "base_pct": 50, "dte": 30}


def _frame(closes, lows=None):
    idx = pd.bdate_range("2022-01-03", periods=len(closes))
    c = pd.Series(np.asarray(closes, float), index=idx)
    lo = pd.Series(np.asarray(lows if lows is not None else closes, float), index=idx)
    return pd.DataFrame({"close": c, "open": c, "high": c, "low": lo, "iv": 0.5, "down": 0.0}), \
        pd.Series(0.0, index=idx)


def _run(exec_, closes, lows=None, **kw):
    f, rates = _frame(closes, lows)
    return Ladder({**V, "exec": exec_, "index": False, **kw}, f, rates, load_rules(), f.index[0], f.index[-1]).run()


def test_touch_and_recover_fills_limit_not_put():
    closes = [100.0] * 5 + [95.0] * 41                     # day 6 trades down to 88 intraday, closes at 95
    lows = [100.0] * 5 + [88.0] + [95.0] * 40
    lim = _run("limit", closes, lows)
    opt = _run("options", closes, lows)
    assert lim.stats["buy_fills"] == 1 and lim.shares > opt.shares
    assert opt.stats["buy_fills"] == 0 and opt.stats["puts_expired"] >= 1 and opt.premium > 0


def test_put_assigned_when_below_level_at_expiry():
    closes = [100.0] * 5 + list(np.linspace(100, 80, 10)) + [80.0] * 40
    opt = _run("options", closes)
    assert opt.stats["buy_fills"] == 1 and 0 in opt.lots
    lim = _run("limit", closes)
    assert lim.stats["buy_fills"] == 1 and lim.lots[0]["exit"] == 100.0


def test_limit_trims_one_rung_up():
    closes = [100.0] * 5 + [90.0] * 5 + [101.0] * 5
    lim = _run("limit", closes)
    assert lim.stats["buy_fills"] == 1 and lim.stats["trims"] == 1 and not lim.lots
