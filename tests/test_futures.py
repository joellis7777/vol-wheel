"""Index futures in an IRA (backtest mode: futures) on synthetic paths."""
import numpy as np
import pandas as pd

from vol_wheel.futures import Futures


def _frame(closes, vol=0.15):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    return pd.DataFrame({"close": closes, "iv_raw": vol}, index=idx)


def _run(rules, frame, rate=0.0, **variant):
    rates = pd.Series(rate, index=frame.index)
    v = {"name": "t", "symbols": ["SPY"], "mode": "futures", "cost_per_contract": 0.0, "roll_cost_per_contract": 0.0,
         "div_yield_pct": 0.0, "account": 100000, **variant}
    return Futures(v, frame, rates, rules, frame.index[0], frame.index[-1]).run()


def test_one_x_tracks_the_index(rules):
    closes = 100 * np.cumprod(np.r_[1.0, np.full(99, 1.002)])
    f = _run(rules, _frame(closes), lev=1.0)
    assert abs(f.equity[-1] / 100000 - closes[-1] / closes[0]) < 1e-6


def test_carry_costs_the_rate_and_cash_earns_it(rules):
    flat = np.full(253, 100.0)
    f = _run(rules, _frame(flat), rate=0.05, lev=1.0, margin_earns=True)
    assert abs(f.equity[-1] / 100000 - 1) < 0.002           # futures pay ~5%, cash earns ~5%: a wash
    g = _run(rules, _frame(flat), rate=0.05, lev=2.0, margin_earns=True)
    assert g.equity[-1] / 100000 < 0.96                      # each extra 1x of leverage costs the rate


def test_leverage_scales_moves(rules):
    closes = np.r_[np.full(5, 100.0), 90.0]
    f = _run(rules, _frame(closes), lev=1.5)
    assert abs(f.equity[-1] / 100000 - 0.85) < 1e-6


def test_margin_call_forces_a_cut(rules):
    closes = np.r_[np.full(5, 100.0), 90.0, 90.0]          # 5x and a 10% fall: equity halves, leverage ~9x
    vol = np.r_[np.full(5, 0.15), 0.9, 0.9]                  # ... while margin jumps with the vol index
    f = _run(rules, _frame(closes, vol), lev=5.0)
    assert f.stats["forced_cuts"] == 1
    assert f.levs[-1] <= 1 / f.req_frac(len(closes) - 1) + 1e-9 and f.equity[-1] > 0


def test_whole_contracts_on_100k(rules):
    closes = np.full(30, 770.0)                              # one MES ~ $38.5k
    f = _run(rules, _frame(closes), lev=1.5, whole_contracts=True)
    assert f.n == 3                                          # 1.5 x $100k / $38.5k = 3.9 -> 3 contracts


def test_dip_ladder_adds_on_the_way_down(rules):
    closes = np.r_[np.full(5, 100.0), np.linspace(100, 60, 40)]
    f = _run(rules, _frame(closes), alloc=[[0, 0.6], [-20, 1.0], [-40, 1.5]])
    assert f.levs[2] < 0.7 and f.levs[-1] > 1.3
