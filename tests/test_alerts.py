import json

import pytest

from vol_wheel import alerts


def ticker(sym="NVDA", action="SELL_PUT", price=234.22, strike=215.0, both=False, em=20.0, ivr=72.0, src="proxy"):
    put = {"strike": strike, "expiry": "2026-11-20", "dte": 48, "delta": -0.232, "mid": 4.45,
           "annualized": 0.16, "reason": "1.5% under 50-day avg · IV 0.3 pts rich · 16% annualized · BE 1.0 moves away"}
    call = {"strike": 265.0, "expiry": "2026-11-20", "dte": 48, "delta": 0.18, "mid": 2.56,
            "annualized": 0.08, "reason": "1.9% over round 260 · 1.3 moves OTM"}
    return {"symbol": sym, "action": action, "price": price, "change_pct": -4.0, "regime": "Mid",
            "ivr": ivr, "ivr_source": src, "both_sides": both, "em45": em,
            "puts": {"candidates": [put]}, "calls": {"candidates": [call]},
            "pair_call": {"candidates": [{**call, "strike": 280.0, "delta": 0.1}]} if both else None,
            "leap": {"found": True, "strike": 190.0, "expiry": "2027-12-17", "dte": 440, "delta": 0.79,
                     "mid": 55.2, "extrinsic": 10.9, "extrinsic_pct": 4.7, "breakeven": 245.2, "cost": 5520.0},
            "spike": {"dir": "down", "size": 2.1}}


def result(*tickers, day="2026-10-05"):
    return {"scan_date": day, "tickers": list(tickers)}


class Recorder:
    def __init__(self, ok=True):
        self.sent, self.ok = [], ok

    def __call__(self, msg, topic, server):
        self.sent.append((msg, topic, server))
        return self.ok


def test_message_format(rules):
    m = alerts.build_message(ticker(), "SELL_PUT", rules)
    assert m["title"] == "SELL PUT · NVDA"
    assert m["priority"] == "high" and m["tags"] == ["chart_with_downwards_trend"]
    assert m["click"] == "https://joellis7777.github.io/vol-wheel/"
    body = m["body"]
    assert "$234.22 (-4.0%) · Mid regime · IVR 72 (proxy)" in body
    assert "Put $215 · Nov 20 2026 (48 DTE) · 23Δ · mid $4.45 · 16% ann" in body
    assert "1.5% under 50-day avg" in body
    assert "CSP ok at $500k: $21,500 of the $25,000 entry" in body


def test_csp_too_big_and_call_and_leap_titles(rules):
    m = alerts.build_message(ticker(strike=740.0), "SELL_PUT", rules)
    assert "Too big for a CSP at $500k ($74,000 > $25,000 entry): use a spread / PMCC" in m["body"]
    c = alerts.build_message(ticker(action="SELL_CALL"), "SELL_CALL", rules)
    assert c["title"] == "SELL COVERED CALL · NVDA" and c["tags"] == ["chart_with_upwards_trend"]
    assert "cover ≤ 50%" in c["body"]
    l = alerts.build_message(ticker(action="LEAP_BUY"), "LEAP_BUY", rules)
    assert l["title"] == "LEAP BUY · NVDA" and l["tags"] == ["seedling"]
    assert "cost $5,520 fits the $25,000 entry at $500k" in l["body"]
    p = alerts.build_message(ticker(both=True), "PAIR_CALL", rules)
    assert p["title"] == "ADD 10Δ CALL · NVDA" and "$280" in p["body"]


def test_new_trigger_alerts_once_per_day(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    r = result(ticker())
    assert alerts.process(r, "intraday", rules, path, "topic", rec)["sent"] == ["SELL PUT · NVDA"]
    assert alerts.process(r, "intraday", rules, path, "topic", rec)["sent"] == []
    # still a SELL_PUT the next day: no repeat
    assert alerts.process(result(ticker(), day="2026-10-06"), "intraday", rules, path, "topic", rec)["sent"] == []
    st = json.loads(path.read_text())
    assert st["tickers"]["NVDA"]["alerts"]["SELL_PUT"]["strike"] == 215.0


def test_flap_same_day_is_silent_next_day_alerts(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    alerts.process(result(ticker()), "intraday", rules, path, "t", rec)
    alerts.process(result(ticker(action="WATCH")), "intraday", rules, path, "t", rec)
    assert alerts.process(result(ticker()), "close", rules, path, "t", rec)["sent"] == []
    alerts.process(result(ticker(action="WATCH"), day="2026-10-06"), "close", rules, path, "t", rec)
    out = alerts.process(result(ticker(), day="2026-10-07"), "intraday", rules, path, "t", rec)
    assert out["sent"] == ["SELL PUT · NVDA"]
    # previous scan saw WATCH -> upgrade gets default priority
    assert rec.sent[-1][0]["priority"] == "default" and "Upgraded from WATCH" in rec.sent[-1][0]["body"]


def test_action_change_alerts(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    alerts.process(result(ticker()), "intraday", rules, path, "t", rec)
    out = alerts.process(result(ticker(action="SELL_CALL")), "intraday", rules, path, "t", rec)
    assert out["sent"] == ["SELL COVERED CALL · NVDA"]


def test_rung_realerts(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    alerts.process(result(ticker(price=234.0, strike=215.0, em=20.0)), "intraday", rules, path, "t", rec)
    # 196 > 215 - 20: not yet at rung 2
    assert alerts.process(result(ticker(price=196.0, strike=180.0)), "intraday", rules, path, "t", rec)["sent"] == []
    out = alerts.process(result(ticker(price=194.0, strike=180.0)), "intraday", rules, path, "t", rec)
    assert out["sent"] == ["SELL PUT · NVDA · rung 2"]
    assert "Rung 2" in rec.sent[-1][0]["body"] and rec.sent[-1][0]["priority"] == "high"
    out = alerts.process(result(ticker(price=159.0, strike=150.0)), "intraday", rules, path, "t", rec)
    assert out["sent"] == ["SELL PUT · NVDA · rung 3"]
    # max_rungs = 3
    assert alerts.process(result(ticker(price=100.0, strike=90.0)), "intraday", rules, path, "t", rec)["sent"] == []


def test_pair_call_add_on(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    out = alerts.process(result(ticker(both=True)), "intraday", rules, path, "t", rec)
    assert out["sent"] == ["SELL PUT · NVDA", "ADD 10Δ CALL · NVDA"]


def test_no_topic_skips_and_records_nothing(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    assert alerts.process(result(ticker()), "intraday", rules, path, "", rec)["status"].startswith("skipped")
    assert rec.sent == [] and not path.exists()


def test_failed_send_retries_next_run(rules, tmp_path):
    path = tmp_path / "s.json"
    assert alerts.process(result(ticker()), "intraday", rules, path, "t", Recorder(ok=False))["failed"]
    assert alerts.process(result(ticker()), "intraday", rules, path, "t", Recorder())["sent"] == ["SELL PUT · NVDA"]


def test_error_cards_leave_state_alone(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    alerts.process(result(ticker()), "intraday", rules, path, "t", rec)
    alerts.process(result({"symbol": "NVDA", "action": "ERROR"}), "intraday", rules, path, "t", rec)
    assert alerts.process(result(ticker()), "intraday", rules, path, "t", rec)["sent"] == []


def test_digest_close_only_once(rules, tmp_path):
    path, rec = tmp_path / "s.json", Recorder()
    r = result(ticker(sym="MSTR", action="WATCH"), ticker(sym="SPY", action="NO_SHORT"))
    assert alerts.process(r, "intraday", rules, path, "t", rec)["sent"] == []
    out = alerts.process(r, "close", rules, path, "t", rec)
    assert out["sent"] == ["WATCH · 1 name"]
    m = rec.sent[-1][0]
    assert m["priority"] == "low" and "MSTR" in m["body"] and "SPY" not in m["body"]
    assert alerts.process(r, "close", rules, path, "t", rec)["sent"] == []
    off = {**rules, "alerts": {**rules["alerts"], "daily_digest": False}}
    assert alerts.process(r, "close", off, tmp_path / "x.json", "t", rec)["sent"] == []


def test_send_uses_topic_url_and_query_params(monkeypatch):
    calls = {}

    class Resp:
        status_code = 200

    def fake_post(url, data=None, params=None, timeout=None):
        calls.update(url=url, data=data, params=params)
        return Resp()

    monkeypatch.setattr(alerts.requests, "post", fake_post)
    msg = {"title": "SELL PUT · NVDA", "body": "x · y", "priority": "high",
           "tags": ["chart_with_downwards_trend"], "click": "https://example.com/"}
    assert alerts.send(msg, "my-topic")
    assert calls["url"] == "https://ntfy.sh/my-topic"
    assert calls["params"]["title"] == "SELL PUT · NVDA" and calls["params"]["priority"] == "high"
    assert calls["data"] == "x · y".encode("utf-8")


def test_send_test_requires_topic(rules):
    with pytest.raises(SystemExit):
        alerts.send_test(rules, topic="")
    rec = Recorder()
    assert alerts.send_test(rules, topic="t", sender=rec)
    assert rec.sent[0][0]["title"] == "vol-wheel test alert"


def test_earnings_play_message(rules):
    t = ticker(action="EARNINGS_PLAY")
    t["earnings"] = {"date": "2026-10-14", "timing": "amc", "days_to": 8,
                     "play": {"side": "P", "ret": -0.07, "z": -1.6}}
    t["earnings_play"] = {"side": "P", "move": 0.06, "move_usd": 14.05, "mult": 1.5, "band": [10, 15],
                          "size_frac": 0.5, "puts": {"candidates": [{"strike": 205.0, "expiry": "2026-11-20", "dte": 45,
                          "delta": -0.12, "mid": 2.1, "annualized": 0.08, "reason": "1.0% under swing low"}]}}
    m = alerts.build_message(t, "EARNINGS_PLAY", rules)
    assert m["title"] == "EARNINGS PLAY · NVDA"
    assert m["tags"] == ["date", "chart_with_downwards_trend"] and m["priority"] == "high"
    assert "Earnings 2026-10-14 (AMC) in 8d · implied move ±6.0% ($14.05)" in m["body"]
    assert "5-day -7.0% (-1.6σ) → sell a put after a sell-off" in m["body"]
    assert "Half size: too big for a CSP at $500k ($20,500 > $12,500)" in m["body"]
    assert alerts.triggers_for(t, rules) == ["EARNINGS_PLAY"]


def test_pre_earnings_expiry_noted_in_alert(rules):
    t = ticker()
    t["earnings"] = {"date": "2026-11-04", "pre_expiry": {"expiry": "2026-10-30", "dte": 28}}
    body = alerts.build_message(t, "SELL_PUT", rules)["body"]
    assert "Expiry ends before earnings 2026-11-04 · take 50% or hold to expiry; don't roll past the report" in body
    t["earnings"]["pre_expiry"] = None
    assert "ends before earnings" not in alerts.build_message(t, "SELL_PUT", rules)["body"]


def test_alert_leads_with_suggested_trade(rules):
    from vol_wheel import scan
    t = ticker()
    t["suggestion"] = scan.build_suggestion(t, rules)
    body = alerts.build_message(t, "SELL_PUT", rules)["body"].splitlines()
    assert body[0] == "→ Sell NVDA Nov 20 $215 put @ ~$4.45"
    assert body[1].startswith("Manage: Close at 50% of the credit; decide by 21 DTE")
    c = ticker(action="SELL_CALL")
    c["suggestion"] = scan.build_suggestion(c, rules)
    lines = alerts.build_message(c, "SELL_CALL", rules)["body"].splitlines()
    assert lines[0] == "→ Sell NVDA Nov 20 $265 call @ ~$2.56"
    assert lines[1] == "⚠ Only if you hold 100 NVDA shares (or a LEAP on NVDA) per contract; cover at most 50% of them"
