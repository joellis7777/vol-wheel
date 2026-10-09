from vol_wheel import scan
from test_alerts import ticker


def test_no_suggestion_for_quiet_actions(rules):
    for a in ("WATCH", "NEUTRAL", "NO_SHORT", "NO_DATA", "ERROR"):
        assert scan.build_suggestion(ticker(action=a), rules) is None


def test_sell_put_suggestion(rules):
    s = scan.build_suggestion(ticker(), rules)
    assert s["text"] == "Sell NVDA Nov 20 $215 put @ ~$4.45"
    assert s["requires"] is None and s["collateral"] == 21500 and s["entry_frac"] == 1.0
    assert "IV/HV ≥ 1.15" in s["valid_while"]


def test_pre_earnings_expiry_changes_management(rules):
    t = ticker()
    t["earnings"] = {"date": "2026-11-04", "pre_expiry": {"expiry": "2026-11-20", "dte": 48, "take_profit_pct": 50}}
    s = scan.build_suggestion(t, rules)
    assert s["manage"] == "Take 50% of the credit or hold to expiry; never roll past earnings 2026-11-04"


def test_covered_call_requires_shares_and_pair_call(rules):
    s = scan.build_suggestion(ticker(action="SELL_CALL"), rules)
    assert s["kind"] == "call" and "100 NVDA shares (or a LEAP on NVDA)" in s["requires"]
    p = scan.build_suggestion(ticker(both=True), rules)
    assert p["also"].startswith("Optional: also sell Nov 20 $280 call")


def test_earnings_play_call_suggestion(rules):
    t = ticker(action="EARNINGS_PLAY")
    t["earnings"] = {"date": "2026-10-21"}
    t["earnings_play"] = {"side": "C", "mult": 1.5, "size_frac": 0.5, "calls": {"candidates": [
        {"strike": 445.0, "expiry": "2026-11-20", "dte": 43, "delta": 0.145, "mid": 3.8, "annualized": 0.086}]}}
    s = scan.build_suggestion(t, rules)
    assert s["text"] == "Sell NVDA Nov 20 $445 call @ ~$3.80 · half size"
    assert "1 contract or skip" in s["requires"] and s["entry_frac"] == 0.5


def test_leap_suggestion_lists_variants(rules):
    t = ticker(action="LEAP_BUY")
    t["leaps"] = {"ira": {**t["leap"], "label": "IRA · 12–18 months"},
                  "taxable": {**t["leap"], "expiry": "2028-06-16", "label": "Taxable · 16–18 months"}}
    s = scan.build_suggestion(t, rules)
    assert s["text"] == "IRA · 12–18 months: buy NVDA Dec 17 2027 $190 call @ ~$55.20"
    assert len(s["variants"]) == 2


def test_no_candidate_is_not_tradeable(rules):
    t = ticker()
    t["puts"] = {"candidates": []}
    assert scan.build_suggestion(t, rules)["tradeable"] is False


def test_wide_market_noted_in_suggestion(rules):
    t = ticker()
    t["puts"]["candidates"][0]["wide_spread"] = True
    assert scan.build_suggestion(t, rules)["text"] == "Sell NVDA Nov 20 $215 put @ ~$4.45 · wide market: limit order near the mid"
