import math

import numpy as np
import pandas as pd
import pytest

from vol_wheel import signals
from conftest import make_history


def test_iv_rank_basic():
    hist = pd.Series([0.20, 0.30, 0.40])
    assert signals.iv_rank(0.30, hist) == pytest.approx(50)
    assert signals.iv_rank(0.40, hist) == pytest.approx(100)
    assert signals.iv_rank(0.20, hist) == pytest.approx(0)
    # current outside the stored range extends it
    assert signals.iv_rank(0.50, hist) == pytest.approx(100)
    assert math.isnan(signals.iv_rank(float("nan"), hist))


def test_percentile_rank():
    assert signals.percentile_rank(5, range(1, 11)) == pytest.approx(50)
    assert signals.percentile_rank(10, range(1, 11)) == pytest.approx(100)


def test_hv_matches_constant_returns():
    # alternating +/- 1% log returns -> stdev 1% -> annualized ~15.9%
    r = np.array([0.01, -0.01] * 30)
    close = pd.Series(100 * np.exp(np.cumsum(np.r_[0, r])))
    hv = signals.hv(close, 20).iloc[-1]
    assert hv == pytest.approx(0.01 * math.sqrt(252) * math.sqrt(20 / 19), rel=1e-3)


def test_down_spike_detected():
    h = make_history(n=300, vol=0.01, seed=3, shocks={1: -0.04})  # -4% today on ~1% daily vol
    s = signals.spike(h["close"], 3, 20)
    assert s["down"] >= 3
    assert s["down_k"] in (1, 2, 3)
    assert s["up"] < 1.5


def test_up_spike_multi_day():
    h = make_history(n=300, vol=0.01, seed=4, shocks={3: 0.015, 2: 0.015, 1: 0.015})
    s = signals.spike(h["close"], 3, 20)
    assert s["up"] >= 1.5
    assert s["up_k"] == 3  # the 3-day move is the most standardized


def test_spike_uses_hv_before_window():
    # Quiet history then one big day: sigma comes from the quiet part, so z is big.
    close = pd.Series([100 * (1.001 if i % 2 else 0.999) for i in range(40)] + [90.0])
    s = signals.spike(close, 1, 20)
    assert s["down"] > 10


def test_extension_and_regime():
    up = pd.Series(np.linspace(50, 150, 400))  # steady trend: ratio near its middle/top
    ext = signals.extension(up)
    assert 0 <= ext["pct"] <= 100
    crash = pd.Series(np.r_[np.linspace(100, 150, 400), np.linspace(150, 90, 40)])
    e2 = signals.extension(crash)
    assert e2["pct"] < 20
    assert signals.regime(e2["pct"]) == "Low"
    assert signals.regime(90) == "High"
    assert signals.regime(50) == "Mid"
    assert signals.regime(float("nan")) == "Mid"


def test_consolidation_requires_tight_bands_and_low_ivr():
    rng = np.random.default_rng(0)
    noisy = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 280)))
    quiet = noisy[-1] * np.exp(np.cumsum(rng.normal(0, 0.002, 30)))
    close = pd.Series(np.r_[noisy, quiet])
    c = signals.consolidation(close, ivr=10)
    assert c["on"] and c["bb_pct"] <= 25
    assert not signals.consolidation(close, ivr=40)["on"]


def test_range_position():
    h = pd.DataFrame({"high": [110] * 50, "low": [90] * 50, "close": [95] * 50})
    assert signals.range_position(h, 50) == pytest.approx(0.25)


def test_bull_gate():
    up = pd.Series(np.linspace(100, 200, 300))
    assert signals.bull_gate(True, up)["on"]
    assert not signals.bull_gate(False, up)["on"]
    down = pd.Series(np.linspace(200, 100, 300))
    assert not signals.bull_gate(True, down)["on"]


def test_proxy_ivr_high_after_vol_burst():
    rng = np.random.default_rng(1)
    calm = rng.normal(0, 0.005, 280)
    wild = rng.normal(0, 0.04, 20)
    close = pd.Series(100 * np.exp(np.cumsum(np.r_[calm, wild])))
    assert signals.proxy_ivr(close) > 90


def test_swing_points():
    s = pd.Series([5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3])
    assert signals.swing_points(s, 3, "low") == [1.0]
    assert signals.swing_points(s, 2, "high") == [5.0]
