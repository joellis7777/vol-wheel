"""Portfolio layer: core pyramid targets and steps, picks ranking, bitcoin warning."""
import numpy as np
import pandas as pd
import pytest

from vol_wheel import portfolio as P

ALLOC = [[0, 80], [20, 85], [40, 90], [60, 95], [80, 100]]


def _hist(closes, start="2020-01-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"close": np.asarray(closes, dtype=float)}, index=idx)


def test_alloc_target_and_steps():
    assert P.alloc_target(0, ALLOC) == 80 and P.alloc_target(30, ALLOC) == pytest.approx(87.5)
    assert P.alloc_target(95, ALLOC) == 100
    assert [P.step_index(d, ALLOC) for d in (0, 19.9, 20, 45, 80)] == [0, 0, 1, 2, 4]


def test_core_row_next_step_and_trim_level():
    h = _hist(np.r_[np.linspace(50, 100, 300), np.linspace(100, 75, 60)])     # 25% off the high
    r = P.core_row("QQQ", {"weight": 35, "alloc": ALLOC}, 85, h)
    assert r["dd_pct"] == pytest.approx(25, abs=0.1) and r["step"] == 1
    assert r["next"] == {"dd_pct": 40, "target_pct": 90, "price": 60.0}
    assert r["trim_above"]["price"] == 80.0 and r["trim_above"]["target_pct"] == 80
    assert r["account_pct"] == pytest.approx(85 * 0.35 * r["target_pct"] / 100, abs=0.05)


def test_core_row_uses_reference_history_for_drawdown():
    btc = _hist(np.r_[np.linspace(20_000, 100_000, 400), np.linspace(100_000, 50_000, 100)])
    ibit = _hist(np.linspace(30, 40, 300) * 0 + 30.0, start="2021-07-01")       # short ETF history
    r = P.core_row("IBIT", {"weight": 20, "alloc": [[0, 70], [25, 78], [50, 86], [80, 100]],
                            "history_symbol": "BTC-USD"}, 85, ibit, btc)
    assert r["dd_pct"] == pytest.approx(50, abs=0.1) and r["step"] == 2
    # next step (−80%) priced on the ETF: 30 x (1 − 0.8) / (1 − 0.5)
    assert r["next"]["price"] == pytest.approx(12.0, abs=0.01)


def test_picks_rank_and_status():
    n = 400
    bench = _hist(np.linspace(100, 120, n))["close"]
    strong = _hist(np.linspace(100, 250, n))
    mid = _hist(np.linspace(100, 140, n))
    weak = _hist(np.r_[np.linspace(100, 160, 250), np.linspace(160, 90, n - 250)])
    watch = [{"symbol": "S"}, {"symbol": "M"}, {"symbol": "W"}]
    rows = P.pick_rows(watch, {"S": strong, "M": mid, "W": weak}, bench,
                       {"rs_months": [6, 12], "rs_top_frac": 1 / 3, "trailing_stop_pct": 28})
    by = {r["symbol"]: r for r in rows}
    assert by["S"]["status"] == "ENTRY_OK" and by["S"]["rs_rank"] == 1
    assert by["M"]["status"] == "WAIT"
    assert by["W"]["status"] == "EXIT_IF_HELD"
    assert rows[0]["symbol"] == "S"


def test_btc_warning_and_build_survives_failures():
    h = _hist(np.r_[np.linspace(100, 200, 300), np.linspace(200, 120, 80)])
    w = P.btc_warning(h)
    assert w["state"] in (0.0, 0.5) and w["since"]
    rules = {"portfolio": {"budget_pct": 85, "core": {"QQQ": {"weight": 35, "alloc": ALLOC},
                                                      "GLD": {"weight": 35, "alloc": ALLOC}},
                           "btc_warning": {"symbol": "BTC-USD"}},
             "picks": {"watchlist": [{"symbol": "S"}], "rules": {}}}

    def fetch(sym):
        if sym == "GLD":
            raise RuntimeError("boom")
        return h
    out = P.build(rules, fetch)
    assert out["core"][0]["symbol"] == "QQQ" and "error" in out["core"][1]
    assert any("GLD" in n for n in out["notes"]) and out["btc_warning"]["label"]
    assert out["picks"][0]["symbol"] == "S"


def test_core_row_scale_out_cap_by_gain_from_low():
    h = _hist(np.r_[np.linspace(100, 50, 200), np.linspace(50, 175, 500)])      # +250% off the 3-year low, at a high
    cfg = {"weight": 35, "alloc": ALLOC, "alloc_gain": [[0, 100], [50, 90], [100, 70], [150, 50], [200, 40]]}
    r = P.core_row("QQQ", cfg, 85, h)
    assert r["dd_pct"] == 0 and r["pyramid_pct"] == 80
    assert r["gain_pct"] == pytest.approx(250, abs=1) and r["scale_cap_pct"] == 40 and r["target_pct"] == 40
    assert r["gain_step"] == 4 and r["next_trim"] is None
