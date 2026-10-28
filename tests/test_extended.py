from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from vol_wheel import alerts, data, extended, schedule

# 2026-10-28 is a Wednesday; 20:40 UTC = 16:40 EDT, 12:00 UTC = 08:00 EDT, 17:00 UTC = 13:00 EDT.
POST, PRE, OPEN = (datetime(2026, 10, 28, h, m, tzinfo=timezone.utc) for h, m in ((20, 40), (12, 0), (17, 0)))
PAYLOAD = {"data": {"current_price": 296.0, "close": 321.89, "prev_day_close": 316.83, "iv30": 38.7, "options": []}}


def test_chain_price_is_the_regular_close_outside_hours():
    c = data.parse_chain(PAYLOAD, asof=date(2026, 10, 28), now=POST)
    assert c["price"] == 321.89 and c["ext_price"] == 296.0
    c = data.parse_chain(PAYLOAD, asof=date(2026, 10, 28), now=OPEN)
    assert c["price"] == 296.0 and np.isnan(c["ext_price"])
    assert data.parse_chain(PAYLOAD, asof=date(2026, 10, 28))["price"] == 296.0   # no clock: unchanged


def test_windows(rules):
    cfg = rules["extended_hours"]
    at = lambda h, m: datetime(2026, 10, 28, h, m, tzinfo=timezone.utc)   # EDT = UTC-4
    assert [extended.in_window(at(h, m), cfg) for h, m in ((12, 29), (12, 30), (13, 15), (13, 30))] == \
        [False, True, True, False]                                         # 08:29 / 08:30 / 09:15 / 09:30 ET
    assert [extended.in_window(at(h, m), cfg) for h, m in ((20, 0), (20, 45), (21, 0))] == [True, True, False]


def test_phase():
    assert [extended.phase(t) for t in (PRE, OPEN, POST)] == ["pre", "regular", "post"]
    assert extended.phase(datetime(2026, 10, 31, 15, tzinfo=timezone.utc)) == "closed"


def _hist(n=130, last=321.89, day="2026-10-28"):
    idx = pd.bdate_range(end=pd.Timestamp(day), periods=n)
    rng = np.random.default_rng(0)
    c = np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    c = c / c[-1] * last                                     # ~24% HV20, ending at the regular close
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6},
                        index=pd.DatetimeIndex(idx, name="date"))


def _run(rules, quotes, earn, now=POST):
    return extended.run(rules, now=now, symbols=list(quotes), quote_fn=lambda s: quotes[s],
                        hist_fn=lambda s: _hist(last=quotes[s]["close"]), earn_cache=earn)


def _q(last, close):
    return {"last": last, "close": close, "prev_close": close, "bid": np.nan, "ask": np.nan}


def test_earnings_gap_alerts_with_context(rules):
    quotes = {"SPY": _q(771.5, 772.3), "GOOG": _q(296.0, 321.89), "NVDA": _q(180.5, 180.0)}
    earn = {"GOOG": {"implied_move": 0.065, "next": {"date": "2026-10-28", "timing": None}}}
    res = _run(rules, quotes, earn)
    g = next(r for r in res["rows"] if r["symbol"] == "GOOG")
    assert res["phase"] == "post" and res["session_date"] == "2026-10-28"
    assert g["kind"] == "earnings" and g["alert"] and abs(g["move_pct"] + 8.04) < 0.01
    assert abs(g["move_vs_implied"] - 8.04 / 6.5) < 0.01
    assert not next(r for r in res["rows"] if r["symbol"] == "NVDA")["alert"]
    msgs = alerts.evaluate_extended(res, {}, rules)
    assert [m["symbol"] for m in msgs] == ["GOOG"]
    assert msgs[0]["title"] == "AFTER HOURS -8.0% · GOOG" and "implied ±6.5%" in msgs[0]["body"]
    assert "drift tends to continue" in msgs[0]["body"]


def test_market_wide_and_dedup(rules):
    quotes = {"SPY": _q(757.0, 772.3), "NVDA": _q(172.0, 180.0)}
    res = _run(rules, quotes, {}, now=PRE)
    n = next(r for r in res["rows"] if r["symbol"] == "NVDA")
    assert res["phase"] == "pre" and res["session_date"] == "2026-10-27" and n["kind"] == "market"
    st = {}
    m = alerts.evaluate_extended(res, st, rules)
    assert len(m) == 1 and m[0]["title"].startswith("PRE-MARKET")
    st["extended"] = {"NVDA": m[0]["xapply"][1]}
    assert alerts.evaluate_extended(res, st, rules) == []                 # same session, same move: quiet
    deeper = _run(rules, {"SPY": _q(757.0, 772.3), "NVDA": _q(164.0, 180.0)}, {}, now=PRE)
    assert len(alerts.evaluate_extended(deeper, st, rules)) == 1          # 3+ points deeper: again


def test_report_context_timing():
    e = {"next": {"date": "2026-10-29", "timing": "BMO"}, "implied_move": 0.05}
    assert extended.report_context(e, date(2026, 10, 28), "pre")["date"] == "2026-10-29"
    assert extended.report_context({"next": {"date": "2026-10-29", "timing": "AMC"}}, date(2026, 10, 28), "post") is None
    assert extended.report_context({"next": {"date": "2026-10-28", "timing": "BMO"}}, date(2026, 10, 28), "post") is None


def test_resolve_mode_extended(rules):
    m = schedule.resolve_mode("extended", None, POST, rules["schedule"])
    assert m["mode"] == "extended"
