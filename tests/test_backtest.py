"""Backtest engine on synthetic data: pricing, signals, position lifecycle, accounting."""
import copy
import math

import numpy as np
import pandas as pd
import pytest

from conftest import bs, make_history
from vol_wheel import backtest as B
from vol_wheel import signals


@pytest.fixture
def rules(rules):
    r = copy.deepcopy(rules)
    r["backtest"]["costs"] = {"per_contract": 0.0, "slippage_pct_index": 0, "slippage_pct_stock": 0}
    return r


def test_bs_matches_conftest_and_parity():
    for cp in "PC":
        assert B.bs_price(100, 95, 0.2, 0.3, cp) == pytest.approx(bs(100, 95, 0.2, 0.3, cp)[0], rel=1e-9)
    c, p = B.bs_price(100, 95, 0.5, 0.25, "C", 0.04), B.bs_price(100, 95, 0.5, 0.25, "P", 0.04)
    assert c - p == pytest.approx(100 - 95 * math.exp(-0.04 * 0.5), rel=1e-9)


@pytest.mark.parametrize("cp,delta", [("P", 0.20), ("P", 0.30), ("C", 0.10), ("C", 0.30)])
def test_strike_for_delta_hits_target_with_skew(cp, delta):
    S, T, atm, slope = 400.0, 45 / 365, 0.22, 0.8
    K = B.strike_for_delta(S, T, atm, delta, cp, slope, r=0.03)
    iv = B.skew_iv(atm, S, K, slope)
    assert abs(B.bs_delta(S, K, T, iv, cp, 0.03)) == pytest.approx(delta, abs=1e-4)
    assert (K < S) if cp == "P" else (K > S)
    if cp == "P":
        assert iv > atm  # put skew


def test_fix_splits_back_adjusts():
    h = make_history(300, seed=3)
    h.iloc[200:, :4] = h.iloc[200:, :4] / 10.0   # unadjusted 10:1 split
    fixed, notes = B.fix_splits(h)
    assert len(notes) == 1 and "1/10" in notes[0]
    r = fixed["close"].iloc[200] / fixed["close"].iloc[199]
    assert 0.9 < r < 1.1
    clean, notes2 = B.fix_splits(make_history(300, seed=3))
    assert notes2 == []


def test_signal_frame_spike_matches_live_function(rules):
    h = make_history(600, seed=5, shocks={1: -0.07})
    f = B.signal_frame(h, rules)
    live = signals.spike(h["close"], rules["thresholds"]["spike_max_days"], rules["thresholds"]["spike_hv_window"])
    assert f["down"].iloc[-1] == pytest.approx(live["down"], rel=1e-9)
    assert f["up"].iloc[-1] == pytest.approx(live["up"], abs=1e-9)
    hv = signals.hv(h["close"], 20)
    assert f["hv_ref"].iloc[-1] == pytest.approx(hv.iloc[-1 - rules["thresholds"]["spike_max_days"]])
    assert f["ivr"].iloc[-1] == pytest.approx(signals.proxy_ivr(h["close"]), abs=1e-6)


def test_signal_frame_uses_vol_index(rules):
    h = make_history(600, seed=6)
    vix = pd.Series(np.linspace(15, 30, 600), index=h.index)
    f = B.signal_frame(h, rules, vix)
    assert f["iv_raw"].iloc[-1] == pytest.approx(0.30)
    assert f["iv"].iloc[-1] == pytest.approx(0.30 * rules["backtest"]["vol_index_atm_ratio"])
    assert f["ivr"].iloc[-1] == pytest.approx(100.0)
    assert bool(f["gate"].iloc[-1])


def _frame(closes, iv=0.25, ivr=80.0, down=0.0, up=0.0, regime="Mid", gate=False):
    idx = pd.bdate_range("2020-01-01", periods=len(closes))
    f = pd.DataFrame({"close": closes, "hv20": iv, "hv_ref": iv / 1.2, "iv": iv, "iv_raw": iv,
                      "ivr": ivr, "down": down, "up": up, "regime": regime, "gate": gate}, index=idx)
    return f


def _sim(rules, frame, variant=None, sym="TEST", vix=None):
    rules["universe"]["Test"] = {"cap": 100, "core": [sym], "opportunistic": []}
    rules["backtest"]["min_history_days"] = 1
    rules["backtest"]["circuit_breakers"] = {}
    v = {"name": "t", "symbols": [sym], "mode": "spike", "entry_pct": 10,
         "caps": {"total": 100, "per_name": 100, "Test": 100}, **(variant or {})}
    rates = pd.Series(0.0, index=frame.index)
    meta = {"bucket": {sym: "Test"}, "index_syms": set(), "vol_index_syms": set(),
            "first_date": {sym: frame.index[0]},
            "vix": pd.Series(vix, index=frame.index) if vix is not None else None}
    return B.Sim(v, {sym: frame}, meta, rates, rules, frame.index[0], frame.index[-1]).run()


def test_put_expires_worthless_or_closes_at_profit(rules):
    closes = np.full(80, 100.0)
    f = _frame(closes)
    f.loc[f.index[0], "down"] = 2.0          # one spike on day 0, flat afterwards
    s = _sim(rules, f)
    st = s.stats
    assert st["puts_sold"] == 1
    assert st["closed_profit"] + st["closed_21dte"] + st["expired_worthless"] == 1
    assert st["assigned"] == 0
    assert s.equity[-1] > 500000             # kept part of the premium
    assert not s.opts


def test_crash_assigns_then_calls_away_on_recovery(rules):
    closes = np.r_[np.full(5, 100.0), np.full(60, 70.0), np.full(5, 130.0), np.full(70, 160.0)]
    f = _frame(closes)
    f.loc[f.index[0], "down"] = 2.0
    f.loc[f.index[65], "up"] = 2.0            # up-spike on the recovery -> covered call, then a rally
    s = _sim(rules, f, {"calls": "spike"})
    st = s.stats
    assert st["assigned"] == 1
    assert st["calls_sold"] >= 1
    # Mid regime: the covered call strike is at least the net cost per share
    assert st["called_away"] == 1 and s.shares["TEST"] == pytest.approx(0, abs=1e-9)
    # accounting identity: final equity = cash (no positions left)
    assert s.equity[-1] == pytest.approx(s.cash, rel=1e-9)
    assert sum(s.cf.values()) == pytest.approx(s.cash - 500000, rel=1e-9)


def test_spike_needs_ivr_and_gate(rules):
    f = _frame(np.full(30, 100.0), ivr=40.0)
    f["down"] = 2.0
    assert _sim(rules, f).stats["puts_sold"] == 0
    g = _frame(np.full(30, 100.0), gate=True)
    g["down"] = 2.0
    g["iv_raw"], g["hv_ref"] = 0.20, 0.20     # IV/HV 1.0 < 1.15
    assert _sim(rules, g).stats["puts_sold"] == 0


def test_ladder_spacing_and_max_rungs(rules):
    f = _frame(np.full(30, 100.0))
    f["down"] = 2.0                           # spike every day, price flat
    s = _sim(rules, f, {"max_rungs": 3})
    opened = sorted(o.opened for o in s.opts)
    assert len(opened) <= 3
    gaps = np.diff([f.index.get_loc(d) for d in opened])
    assert all(g >= rules["backtest"]["ladder_spacing_days"] for g in gaps)


def test_always_mode_enters_on_schedule_within_cap(rules):
    f = _frame(np.full(60, 100.0), ivr=10.0)
    s = _sim(rules, f, {"mode": "always", "entry_every_days": 5, "min_ivr": 0, "entry_pct": 10,
                        "caps": {"total": 30, "per_name": 30, "Test": 30}})
    assert s.stats["puts_sold"] >= 3
    assert max(s.deployed) <= 0.30 + 1e-6
    s2 = _sim(rules, f, {"mode": "always", "min_ivr": 30})
    assert s2.stats["puts_sold"] == 0


def test_hold_and_metrics(rules):
    rules["universe"]["Test"] = {"cap": 100, "core": ["TEST"], "opportunistic": []}
    rules["backtest"]["min_history_days"] = 1
    closes = np.linspace(100, 200, 300)
    f = _frame(closes)
    rates = pd.Series(0.0, index=f.index)
    meta = {"bucket": {"TEST": "Test"}, "index_syms": set(), "vol_index_syms": set(), "first_date": {"TEST": f.index[0]}}
    res = B.run_hold({"symbols": ["TEST"], "weight": 100}, {"TEST": f}, meta, rates, rules, f.index[0], f.index[-1])
    assert res["final"] == pytest.approx(1_000_000, rel=1e-6)
    assert res["max_dd_pct"] == 0
    half = B.run_hold({"symbols": ["TEST"], "weight": 50}, {"TEST": f}, meta, rates, rules, f.index[0], f.index[-1])
    assert 500_000 * 1.4 < half["final"] < 1_000_000


def test_clean_ticks_and_last_listing():
    h = make_history(300, seed=4)
    h.iloc[150, h.columns.get_loc("close")] = 0.5          # one bad print
    clean, notes = B.clean_ticks(h)
    assert len(clean) == 299 and len(notes) == 1
    old = make_history(200, seed=1, end=pd.Timestamp("2012-03-01").date())
    new = make_history(300, seed=2, end=pd.Timestamp("2026-10-02").date())
    both, notes = B.last_listing(pd.concat([old, new]))
    assert len(both) == 300 and both.index[0] == new.index[0] and notes


def test_hold_survives_missing_bars(rules):
    rules["universe"]["Test"] = {"cap": 100, "core": ["TEST"], "opportunistic": []}
    rules["backtest"]["min_history_days"] = 1
    f = _frame(np.linspace(100, 110, 100))
    f.iloc[50, f.columns.get_loc("close")] = np.nan       # feed missing one day
    rates = pd.Series(0.0, index=f.index)
    meta = {"bucket": {"TEST": "Test"}, "index_syms": set(), "vol_index_syms": set(), "first_date": {"TEST": f.index[0]}}
    res = B.run_hold({"symbols": ["TEST"], "weight": 100}, {"TEST": f}, meta, rates, rules, f.index[0], f.index[-1])
    assert res["max_dd_pct"] > -1


def test_vix_cap_bands():
    bands = [[0, 40], [15, 55], [20, 70], [30, 80]]
    assert B.vix_cap(12.0, bands) == 40
    assert B.vix_cap(15.0, bands) == 55
    assert B.vix_cap(29.9, bands) == 70
    assert B.vix_cap(45.0, bands) == 80
    assert B.vix_cap(float("nan"), bands) is None and B.vix_cap(20.0, []) is None


def test_vix_cap_limits_deployment(rules):
    f = _frame(np.full(60, 100.0), ivr=10.0)
    rules["backtest"]["costs"]["per_contract"] = 0.0
    base = {"mode": "always", "entry_every_days": 1, "min_ivr": 0, "entry_pct": 10,
            "caps": {"total": 100, "per_name": 100, "Test": 100}}
    uncapped = _sim(rules, f, base)
    rules["deployment"] = {"vix_caps": [[0, 30], [25, 90]]}
    calm = _sim(rules, f, {**base, "vix_caps": True}, vix=12.0)
    stressed = _sim(rules, f, {**base, "vix_caps": True}, vix=35.0)
    assert max(calm.deployed) <= 0.30 + 1e-6
    assert max(stressed.deployed) > 0.6
    assert max(uncapped.deployed) > max(calm.deployed)


def test_dte_by_regime(rules):
    f = _frame(np.full(4, 100.0), regime="Low")
    f.loc[f.index[0], "down"] = 2.0
    s = _sim(rules, f, {"dte": {"Low": 30}})
    o = s.opts[0]
    assert (o.expiry - o.opened).days == 30
    assert s._dte("High", 45) == 45


def test_call_coverage_and_regimes(rules):
    closes = np.r_[np.full(5, 100.0), np.full(30, 70.0)]   # assigned ~day 32, call still open at the end
    f = _frame(closes, regime="High")                       # High: no net-cost floor on the call strike
    f.loc[f.index[0], "down"] = 2.0
    half = _sim(rules, f, {"calls": "always", "call_coverage": 50})
    calls = [o for o in half.opts if o.cp == "C"]
    assert calls and sum(o.qty for o in calls) == pytest.approx(half.shares["TEST"] * 0.5)
    none = _sim(rules, f, {"calls": "always", "call_regimes": ["Low"]})
    assert none.stats["calls_sold"] == 0


def test_roll_until_right_puts_down_and_out(rules):
    closes = np.r_[np.full(5, 100.0), np.full(80, 90.0)]       # put goes ITM and stays there
    f = _frame(closes)
    f.loc[f.index[0], "down"] = 2.0
    held = _sim(rules, f)
    assert held.stats["assigned"] == 1
    rolled = _sim(rules, f, {"roll_itm": {"puts": True, "max_rolls": 6}})
    assert rolled.stats["rolled_puts"] >= 1 and rolled.stats["assigned"] == 0
    # stop just after the roll (24 calendar days in = 17 sessions): the new put is lower and later
    just = _sim(rules, f.iloc[:19], {"roll_itm": {"puts": True, "max_rolls": 6}})
    first = _sim(rules, f.iloc[:5])
    k0 = first.opts[0].strike
    puts = [o for o in just.opts if o.cp == "P"]
    assert puts and puts[0].rolls == 1 and puts[0].strike < k0


def test_roll_calls_only_outside_top_regime(rules):
    closes = np.r_[np.full(5, 100.0), np.full(30, 70.0), np.full(5, 72.0), np.full(60, 95.0)]
    f = _frame(closes, regime="High")
    f.loc[f.index[0], "down"] = 2.0
    base = {"calls": "always"}
    rolled = _sim(rules, f, {**base, "roll_itm": {"calls": True, "call_regimes": ["Low", "Mid", "High"]}})
    kept = _sim(rules, f, {**base, "roll_itm": {"calls": True, "call_regimes": ["Low", "Mid"]}})
    assert rolled.stats["rolled_calls"] >= 1
    assert kept.stats["rolled_calls"] == 0 and kept.stats["called_away"] >= 1


def test_short_dte_entries_hold_to_expiry(rules):
    f = _frame(np.full(12, 100.0), regime="Low")
    f.loc[f.index[0], "down"] = 2.0
    s = _sim(rules, f, {"dte": {"Low": 21}})
    assert s.stats["closed_21dte"] == 0


def test_hold_weights_and_rotation(rules):
    rules["backtest"]["min_history_days"] = 1
    idx = pd.bdate_range("2020-01-01", periods=600)
    up = _frame(np.linspace(100, 200, 600)).set_axis(idx)
    flat = _frame(np.full(600, 100.0)).set_axis(idx)
    frames = {"A": up, "B": flat}
    rates = pd.Series(0.0, index=idx)
    meta = {"first_date": {"A": idx[0], "B": idx[0]}}
    mix = B.run_hold({"symbols": ["A", "B"], "weights": {"A": 75, "B": 25}}, frames, meta, rates, rules, idx[0], idx[-1])
    eq = B.run_hold({"symbols": ["A", "B"]}, frames, meta, rates, rules, idx[0], idx[-1])
    assert mix["final"] > eq["final"]
    rot = B.run_hold({"symbols": ["A", "B"], "rotate": {"lookback": 252, "top": 1, "abs": True}},
                     frames, meta, rates, rules, idx[0], idx[-1])
    assert rot["months_held_pct"]["A"] > 0 and rot["months_held_pct"]["B"] == 0


def test_hold_trend_exit_moves_to_tbills(rules):
    rules["backtest"]["min_history_days"] = 1
    idx = pd.bdate_range("2020-01-01", periods=600)
    closes = np.r_[np.linspace(100, 200, 300), np.linspace(200, 100, 300)]
    frames = {"A": _frame(closes).set_axis(idx)}
    rates = pd.Series(0.0, index=idx)
    meta = {"first_date": {"A": idx[0]}}
    hold = B.run_hold({"symbols": ["A"]}, frames, meta, rates, rules, idx[0], idx[-1])
    trend = B.run_hold({"symbols": ["A"], "trend_sma": 200}, frames, meta, rates, rules, idx[0], idx[-1])
    assert trend["max_dd_pct"] > hold["max_dd_pct"]          # exits in the fall
    assert trend["months_held_pct"]["T-bills"] > 0
