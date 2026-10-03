from datetime import date

import numpy as np
import pandas as pd
import pytest

from vol_wheel import data, strikes
from conftest import ASOF, make_chain_payload, make_history, third_friday


@pytest.fixture
def chain():
    return data.parse_chain(make_chain_payload(price=100.0, atm_iv=0.30))


def test_is_monthly():
    assert strikes.is_monthly(date(2026, 11, 20))       # third Friday
    assert not strikes.is_monthly(date(2026, 11, 13))
    # Good Friday style: Thursday monthly when the Friday isn't listed
    assert strikes.is_monthly(date(2025, 4, 17), {date(2025, 4, 17)})
    assert not strikes.is_monthly(date(2025, 4, 17), {date(2025, 4, 17), date(2025, 4, 18)})


def test_choose_expiry_prefers_monthly_near_45(rules, chain):
    e, dte, note = strikes.choose_expiry(chain["options"], rules["strikes"])
    assert e == third_friday(2026, 11)  # 49 DTE from 2026-10-02
    assert 35 <= dte <= 50 and note == "monthly"


def test_choose_expiry_falls_back_to_weekly(rules):
    exps = [ASOF + pd.Timedelta(days=d).to_pytimedelta() for d in (10, 44, 80)]
    ch = data.parse_chain(make_chain_payload(expiries=exps))
    e, dte, note = strikes.choose_expiry(ch["options"], rules["strikes"])
    assert dte == 44 and note.startswith("weekly")


def test_filters(rules):
    sc = rules["strikes"]
    base = {"bid": 1.00, "ask": 1.05, "mid": 1.025, "oi": 500, "delta": -0.25, "strike": 100.0}
    assert strikes.passes_filters(base, "P", sc)[0]
    assert strikes.passes_filters({**base, "oi": 50}, "P", sc) == (False, "open interest")
    wide = {**base, "bid": 1.0, "ask": 1.5, "mid": 1.25}
    assert strikes.passes_filters(wide, "P", sc) == (False, "spread")
    # spread above 10% of mid but within $0.10 passes
    cheap = {**base, "bid": 0.30, "ask": 0.38, "mid": 0.34, "delta": -0.12}
    assert strikes.passes_filters(cheap, "P", sc)[0]
    # 25-delta put needs >= 1% of strike
    assert strikes.passes_filters({**base, "bid": 0.80, "ask": 0.84, "mid": 0.82}, "P", sc) == (False, "credit")
    # below 20 delta only 0.3%
    assert strikes.passes_filters({**base, "bid": 0.80, "ask": 0.84, "mid": 0.82, "delta": -0.15}, "P", sc)[0]


def test_sr_score_put_sweet_spot_and_penalty(rules):
    sc = rules["strikes"]
    lv = [{"value": 100.0, "kind": "sma50", "strength": 1.0}]
    assert strikes.sr_score(98.0, lv, "P", sc)[0] == pytest.approx(1.0)    # 2% under support
    assert strikes.sr_score(94.5, lv, "P", sc)[0] == pytest.approx(0.5)    # 5.5% -> halfway faded
    assert strikes.sr_score(91.0, lv, "P", sc)[0] == pytest.approx(0.0)    # beyond 8%
    assert strikes.sr_score(101.0, lv, "P", sc)[0] == pytest.approx(0.0)   # just above support: penalty
    # penalty from one level offsets credit from another
    lv2 = lv + [{"value": 97.0, "kind": "round", "strength": 1.0}]
    s, best, d = strikes.sr_score(98.0, lv2, "P", sc)
    assert s == pytest.approx(0.5) and best["kind"] == "sma50"


def test_sr_score_call_mirrored(rules):
    sc = rules["strikes"]
    lv = [{"value": 100.0, "kind": "swing_high", "strength": 1.0}]
    assert strikes.sr_score(102.0, lv, "C", sc)[0] == pytest.approx(1.0)
    assert strikes.sr_score(99.0, lv, "C", sc)[0] == pytest.approx(0.0)


def test_skew_fit_and_residual(chain):
    o = chain["options"]
    e = third_friday(2026, 11)
    poly = strikes.skew_fit(o[o["expiry"] == e], 100.0)
    assert poly is not None
    # the synthetic smile is exactly quadratic in log-moneyness -> tiny residuals
    assert abs(strikes.skew_residual(poly, 90.0, 0.30 - 0.15 * np.log(0.9) + 0.4 * np.log(0.9) ** 2, 100.0)) < 0.002


def test_richness_rewards_bumped_strike(rules):
    # Bump IV on the 90 strike by 3 vol points: it should score richer than neighbours.
    ch = data.parse_chain(make_chain_payload(price=100.0, iv_bumps={90.0: 0.03}))
    o = ch["options"]
    e = third_friday(2026, 11)
    poly = strikes.skew_fit(o[o["expiry"] == e], 100.0)
    rows = o[(o["expiry"] == e) & (o["type"] == "P") & (o["strike"].isin([89.0, 90.0, 91.0]))]
    sc = {r.strike: strikes.richness_score(strikes.skew_residual(poly, r.strike, r.iv, 100.0), r.iv, 0.25,
                                           rules["strikes"]) for r in rows.itertuples()}
    assert sc[90.0] > sc[89.0] and sc[90.0] > sc[91.0]


def test_rank_scores():
    assert strikes.rank_scores([0.1, 0.3, 0.2]) == pytest.approx([0, 1, 0.5])
    assert strikes.rank_scores([0.4]) == [1.0]


def test_assignment_score(rules):
    sc = rules["strikes"]
    assert strikes.assignment_score(95, [96], sc) == 1.0
    assert strikes.assignment_score(105.5, [100], sc) == pytest.approx(0.5)
    assert strikes.assignment_score(120, [100], sc) == 0.0


def test_select_strikes_band_and_top3(rules, chain):
    sc = rules["strikes"]
    hist = make_history(n=400, start=80, drift=0.0006, vol=0.012, seed=7)
    hist["close"] = hist["close"] * 100.0 / hist["close"].iloc[-1]
    hist["low"], hist["high"] = hist["close"] * 0.99, hist["close"] * 1.01
    o = chain["options"]
    e, dte, _ = strikes.choose_expiry(o, sc)
    lv = strikes.levels(hist, o, 100.0, "P", sc)
    ctx = {"price": 100.0, "iv30": 0.30, "hv20": 0.20, "hist": hist, "expiry": e, "dte": dte,
           "poly": strikes.skew_fit(o[o["expiry"] == e], 100.0), "levels": lv, "anchors": [90.0]}
    res = strikes.select_strikes(o, "P", 20, ctx, sc)
    assert res["in_band"] > 3 and res["passed"] >= 3
    cands = res["candidates"]
    assert len(cands) == 3
    assert all(13 <= abs(c["delta"]) * 100 <= 27 for c in cands)
    assert cands[0]["score"] >= cands[1]["score"] >= cands[2]["score"]
    assert "annualized" in cands[0]["reason"] and "moves away" in cands[0]["reason"]
    for c in cands:
        assert c["collateral"] == c["strike"] * 100
        assert 0 <= c["f_support"] <= 1 and 0 <= c["f_roc"] <= 1

    calls = strikes.select_strikes(o, "C", 20, {**ctx, "levels": strikes.levels(hist, o, 100.0, "C", sc)}, sc)
    assert calls["candidates"] and all(c["strike"] > 100 for c in calls["candidates"])
    assert "moves OTM" in calls["candidates"][0]["reason"]


def test_support_wins_over_exact_delta(rules, chain):
    """A strike just under strong support beats the exact-target strike sitting just above it."""
    sc = rules["strikes"]
    o = chain["options"]
    e, dte, _ = strikes.choose_expiry(o, sc)
    ps = o[(o["expiry"] == e) & (o["type"] == "P")]
    exact = ps.iloc[(ps["delta"].abs() - 0.20).abs().argmin()]
    support = float(exact["strike"]) - 1.5  # exact strike sits 1.5 above support -> penalty
    ctx = {"price": 100.0, "iv30": 0.30, "hv20": 0.25, "hist": None, "expiry": e, "dte": dte,
           "poly": strikes.skew_fit(o[o["expiry"] == e], 100.0),
           "levels": [{"value": support, "kind": "sma200", "strength": 1.0}], "anchors": []}
    res = strikes.select_strikes(o, "P", 20, ctx, sc)
    top = res["candidates"][0]
    assert top["strike"] < support
    assert top["level"]["kind"] == "sma200"


def test_leap_candidate(rules, chain):
    lc = strikes.leap_candidate(chain["options"], 100.0, rules["leap"])
    assert lc["found"]
    assert 365 <= lc["dte"] <= 548
    assert 0.70 <= lc["delta"] <= 0.80
    assert lc["extrinsic_pct"] >= 0


def test_ladder():
    rungs = strikes.ladder(95.0, 100.0, 0.30, list(np.arange(50, 151, 1.0)), {}, 3, 45)
    em = 100 * 0.30 * np.sqrt(45 / 365)
    assert [r["rung"] for r in rungs] == [1, 2, 3]
    assert rungs[1]["strike"] <= 95 - em < rungs[1]["strike"] + 1
    assert rungs[2]["strike"] <= 95 - 2 * em < rungs[2]["strike"] + 1


def test_nice_step():
    assert strikes.nice_step(600) == 50
    assert strikes.nice_step(180) == 10
    assert strikes.nice_step(25) == 2
