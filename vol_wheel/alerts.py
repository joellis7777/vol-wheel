"""Phone alerts via ntfy.

After each scan, new triggers (SELL_PUT, SELL_CALL, LEAP_BUY, PAIR_CALL) are pushed to
https://ntfy.sh/$NTFY_TOPIC. The topic comes only from the NTFY_TOPIC environment variable (a repo
secret); without it, alerting is skipped and nothing is recorded, so triggers still alert once the
secret is added.

Dedup state lives in data/alert_state.json:

    {"tickers": {"NVDA": {"action": "SELL_PUT", "seen": "2026-10-02",
                          "alerts": {"SELL_PUT": {"date": "2026-10-02", "strike": 215.0, "price": 234.2,
                                                  "em": 21.3, "rung": 1, "active": true}}}},
     "digest_date": "2026-10-02"}

Rules (evaluate()):
- A trigger alerts when it has no record, or its record is inactive and from an earlier day.
- While a trigger stays active it re-alerts only when price reaches the next ladder rung: one
  expected move past the last alerted strike (puts: below, calls: above, LEAPs: below the last
  alerted price), up to alerts.max_rungs.
- A trigger that lapses is marked inactive; if it returns the same day it is reactivated silently
  (one alert per ticker + action per day).
- ERROR / NO_DATA cards leave state untouched, so a bad fetch doesn't reset an episode.

    python -m vol_wheel.alerts --test     # send a test notification
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

import requests

from .config import ROOT, load_rules

log = logging.getLogger("vol_wheel.alerts")

STATE_PATH = ROOT / "data" / "alert_state.json"
TITLES = {"SELL_PUT": "SELL PUT", "SELL_CALL": "SELL COVERED CALL", "LEAP_BUY": "LEAP BUY",
          "PAIR_CALL": "ADD 10Δ CALL", "EARNINGS_PLAY": "EARNINGS PLAY", "HEDGE": "HEDGE"}
# Direction a rung moves: puts and LEAP adds step down, calls step up; the add-on call, earnings
# plays (one per report) and the hedge don't ladder.
RUNG_DIR = {"SELL_PUT": -1, "SELL_CALL": 1, "LEAP_BUY": -1, "PAIR_CALL": 0, "EARNINGS_PLAY": 0, "HEDGE": 0}
HEDGE_KEY = "_HEDGE"


# ---------------------------------------------------------------- state

def load_state(path: Path | None = None) -> dict:
    p = Path(path or STATE_PATH)
    if not p.exists():
        return {"tickers": {}}
    try:
        s = json.loads(p.read_text())
        s.setdefault("tickers", {})
        return s
    except (json.JSONDecodeError, OSError) as e:
        log.warning("alert state unreadable (%s); starting fresh", e)
        return {"tickers": {}}


def save_state(state: dict, path: Path | None = None) -> None:
    p = Path(path or STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")


# ---------------------------------------------------------------- formatting

def _money(x, d=2) -> str:
    if x is None:
        return "–"
    return f"${x:,.{d}f}"


def _strike(x) -> str:
    return _money(x, 0 if float(x).is_integer() else 2)


def _expiry(s: str | None, dte) -> str:
    if not s:
        return ""
    try:
        d = date.fromisoformat(s)
        return f"{d.strftime('%b')} {d.day} {d.year} ({dte} DTE)"
    except ValueError:
        return f"{s} ({dte} DTE)"


def entry_size(rules: dict) -> float:
    return rules["alerts"]["sizing_tier"] * rules["sizing"]["entry_pct"] / 100.0


def tier_label(rules: dict) -> str:
    t = rules["alerts"]["sizing_tier"]
    return f"${t / 1e6:g}M" if t >= 1e6 else f"${t / 1e3:g}k"


def header_line(t: dict) -> str:
    ch = t.get("change_pct")
    chs = f" ({ch:+.1f}%)" if ch is not None else ""
    ivr = t.get("ivr")
    src = t.get("ivr_source")
    ivr_s = f"IVR {ivr:.0f}" if ivr is not None else "IVR –"
    if src and src != "true":
        ivr_s += f" ({src})"
    return f"{_money(t.get('price'))}{chs} · {t.get('regime', '–')} regime · {ivr_s}"


def option_line(c: dict, kind: str) -> list[str]:
    return [
        f"{kind} {_strike(c['strike'])} · {_expiry(c.get('expiry'), c.get('dte'))} · "
        f"{abs(c['delta']) * 100:.0f}Δ · mid {_money(c['mid'])} · {c['annualized'] * 100:.0f}% ann",
        c.get("reason", ""),
    ]


def top_candidate(t: dict, trigger: str) -> dict | None:
    if trigger == "EARNINGS_PLAY":
        ep = t.get("earnings_play") or {}
        c = (ep.get("calls" if ep.get("side") == "C" else "puts") or {}).get("candidates") or []
        return c[0] if c else None
    key = {"SELL_PUT": "puts", "SELL_CALL": "calls", "PAIR_CALL": "pair_call"}.get(trigger)
    if not key:
        return None
    c = (t.get(key) or {}).get("candidates") or []
    return c[0] if c else None


def leap_line(lp: dict) -> str:
    return (f"{_strike(lp['strike'])} call · {_expiry(lp.get('expiry'), lp.get('dte'))} · "
            f"{lp['delta'] * 100:.0f}Δ · mid {_money(lp['mid'])} · extrinsic {lp['extrinsic_pct']:.1f}%")


def build_message(t: dict, trigger: str, rules: dict, rung: int = 1, upgrade: bool = False,
                  rec: dict | None = None) -> dict:
    ac = rules["alerts"]
    sym = t["symbol"]
    title = f"{TITLES[trigger]} · {sym}" + (f" · rung {rung}" if rung > 1 else "")
    lines = []
    es, tier = entry_size(rules), tier_label(rules)
    sg = t.get("suggestion") or {}
    if trigger == "PAIR_CALL" and sg.get("also"):
        lines.append("→ " + sg["also"])
    elif sg.get("action") == trigger and sg.get("text"):
        lines.append("→ " + sg["text"])
        if sg.get("requires"):
            lines.append("⚠ " + sg["requires"])
        if sg.get("manage"):
            lines.append("Manage: " + sg["manage"])
    lines.append(header_line(t))
    c = top_candidate(t, trigger)
    if trigger == "SELL_PUT":
        if c:
            lines += option_line(c, "Put")
            need = c["strike"] * 100
            lines.append(f"CSP ok at {tier}: {_money(need, 0)} of the {_money(es, 0)} entry" if need <= es else
                         f"Too big for a CSP at {tier} ({_money(need, 0)} > {_money(es, 0)} entry): "
                         "use a spread / PMCC")
        else:
            lines.append("No put passes the filters today; see the dashboard")
    elif trigger in ("SELL_CALL", "PAIR_CALL"):
        if trigger == "PAIR_CALL":
            lines.append("Mid regime + IVR ≥ 70: a 10Δ covered call may sit alongside the put")
        if c:
            lines += option_line(c, "Call")
        else:
            lines.append("No call passes the filters today; see the dashboard")
        cover = "Covered only: against 100 shares or a LEAP"
        if sym in rules.get("momentum_names", []):
            cover += f" (cover ≤ {rules.get('momentum_max_call_coverage', 50)}%)"
        lines.append(cover)
    elif trigger == "LEAP_BUY":
        leaps = t.get("leaps") or {"ira": t.get("leap") or {}}
        for name, lp in leaps.items():
            label = lp.get("label") or name
            if lp.get("found"):
                lines.append(f"{label}: {leap_line(lp)}")
                cost = lp["cost"]
                lines.append(f"  cost {_money(cost, 0)} {'fits' if cost <= es else 'exceeds'} the {_money(es, 0)} "
                             f"entry at {tier}" + (f" · {lp['variant_note']}" if lp.get("variant_note") else ""))
            else:
                lines.append(f"{label}: no candidate ({lp.get('note', 'none')})")
        lines.append("Bull gate on · quiet consolidation at the bottom of the range")
    elif trigger == "EARNINGS_PLAY":
        e = t.get("earnings") or {}
        ep = t.get("earnings_play") or {}
        play = e.get("play") or {}
        when = f" ({e['timing'].upper()})" if e.get("timing") else ""
        lines.append(f"Earnings {e.get('date')}{when} in {e.get('days_to')}d · implied move "
                     f"±{(ep.get('move') or 0) * 100:.1f}% ({_money(ep.get('move_usd'))})")
        side_word = "call after a run-up" if ep.get("side") == "C" else "put after a sell-off"
        if play.get("ret") is not None:
            lines.append(f"5-day {play['ret'] * 100:+.1f}% ({play['z']:+.1f}σ) → sell a {side_word}")
        if c:
            lines += option_line(c, "Call" if ep.get("side") == "C" else "Put")
            lines.append(f"Outside {ep.get('mult', 1.5)}× the implied move · "
                         f"{ep.get('band', [10, 15])[0]}–{ep.get('band', [10, 15])[1]}Δ")
            half = es * ep.get("size_frac", 0.5)
            if ep.get("side") == "P":
                need = c["strike"] * 100
                lines.append(f"Half size: CSP ok at {tier} ({_money(need, 0)} of the {_money(half, 0)} half entry)"
                             if need <= half else
                             f"Half size: too big for a CSP at {tier} ({_money(need, 0)} > {_money(half, 0)}): "
                             "use a spread")
            else:
                lines.append("Half size · covered only: against shares or a LEAP")
        else:
            lines.append("No strike passes the filters outside the implied move; see the dashboard")
    pre = (t.get("earnings") or {}).get("pre_expiry")
    if pre and trigger in ("SELL_PUT", "SELL_CALL", "PAIR_CALL"):
        tp = pre.get("take_profit_pct", 50)
        lines.append(f"Expiry ends before earnings {(t.get('earnings') or {}).get('date')} · "
                     f"take {tp}% or hold to expiry; don't roll past the report")
    if rung > 1 and rec:
        ref = rec.get("strike") if trigger != "LEAP_BUY" else rec.get("price")
        side = "below" if RUNG_DIR[trigger] < 0 else "above"
        lines.append(f"Rung {rung}: price is ≥ 1 expected move ({_money(rec.get('em'))}) {side} "
                     f"the last alert at {_money(ref)}")
    if upgrade:
        lines.append("Upgraded from WATCH")
    pr = ac["priority"]
    tags = [ac["tags"].get(trigger, "bell")]
    if trigger == "EARNINGS_PLAY":
        ep = t.get("earnings_play") or {}
        tags.append(ac["tags"]["SELL_CALL" if ep.get("side") == "C" else "SELL_PUT"])
    return {
        "title": title, "body": "\n".join(x for x in lines if x),
        "priority": pr["upgrade_from_watch"] if upgrade else pr["trigger"],
        "tags": tags, "click": ac["dashboard_url"],
    }


def hedge_message(h: dict, rules: dict) -> dict:
    ac = rules["alerts"]
    lines = [f"VIX {h.get('vix') or 0:.1f} < {h.get('vix_max')} and SPY in the {h.get('spy_regime')} regime",
             f"Optional far-OTM puts, {h['dte'][0]}–{h['dte'][1]} DTE:"]
    for sym, hp in (h.get("candidates") or {}).items():
        for p in (hp or {}).get("puts", []):
            lines.append(f"{sym} {_strike(p['strike'])} put · {_expiry(p['expiry'], p['dte'])} · "
                         f"{p['otm_pct']:.0f}% OTM · mid {_money(p['mid'])} ({_money(p['cost'], 0)})")
    lines.append("Not a standing hedge: protection is the cash reserve, caps and circuit breakers")
    return {"title": "HEDGE · SPY/QQQ puts", "body": "\n".join(lines), "priority": ac["priority"].get("hedge", "default"),
            "tags": [ac["tags"].get("HEDGE", "shield")], "click": ac["dashboard_url"]}


# ---------------------------------------------------------------- dedup logic

def triggers_for(t: dict, rules: dict) -> list[str]:
    """Ticker-level triggers (the hedge is result-level; see evaluate())."""
    allowed = rules["alerts"].get("triggers", list(TITLES))
    out = []
    if t.get("action") in allowed and t.get("action") in TITLES:
        out.append(t["action"])
    if t.get("both_sides") and "PAIR_CALL" in allowed:
        out.append("PAIR_CALL")
    return out


def trigger_record(t: dict, trigger: str, today: str, rung: int) -> dict:
    c = top_candidate(t, trigger)
    strike = c["strike"] if c else t.get("price")
    return {"date": today, "strike": strike, "price": t.get("price"), "em": t.get("em45"),
            "rung": rung, "active": True}


def rung_reached(rec: dict, price: float | None, trigger: str) -> bool:
    d = RUNG_DIR.get(trigger, 0)
    em = rec.get("em")
    if d == 0 or not em or price is None:
        return False
    ref = rec.get("price") if trigger == "LEAP_BUY" else rec.get("strike")
    if ref is None:
        return False
    return price <= ref - em if d < 0 else price >= ref + em


def evaluate(result: dict, state: dict, today: str, rules: dict) -> tuple[list[dict], dict]:
    """Pure: returns (alerts to send, state with silent changes applied).

    Each alert carries `apply` = (symbol, trigger, record); the caller writes it into state only
    after the notification is sent.
    """
    state = copy.deepcopy(state)
    tickers = state.setdefault("tickers", {})
    max_rungs = rules["alerts"].get("max_rungs", 3)
    out: list[dict] = []
    for t in result.get("tickers", []):
        if t.get("action") in ("ERROR", "NO_DATA"):
            continue
        sym = t["symbol"]
        st = tickers.setdefault(sym, {"alerts": {}})
        recs = st.setdefault("alerts", {})
        prev_action = st.get("action")
        current = triggers_for(t, rules)
        for trig in current:
            rec = recs.get(trig)
            if rec is None or (not rec.get("active") and rec.get("date") != today):
                upgrade = prev_action == "WATCH" and trig != "PAIR_CALL"
                msg = build_message(t, trig, rules, 1, upgrade)
                out.append({**msg, "symbol": sym, "trigger": trig,
                            "apply": (sym, trig, trigger_record(t, trig, today, 1))})
            elif not rec.get("active"):
                rec["active"] = True  # came back the same day: already alerted today
            elif rec.get("rung", 1) < max_rungs and rung_reached(rec, t.get("price"), trig):
                rung = rec.get("rung", 1) + 1
                msg = build_message(t, trig, rules, rung, False, rec)
                out.append({**msg, "symbol": sym, "trigger": trig,
                            "apply": (sym, trig, trigger_record(t, trig, today, rung))})
        for trig, rec in recs.items():
            if trig not in current:
                rec["active"] = False
        st["action"] = t.get("action")
        st["seen"] = today
    # Hedge: one alert per episode (conditions newly met), same inactive/same-day rules.
    h = result.get("hedge") or {}
    if "HEDGE" in rules["alerts"].get("triggers", []) and h.get("enabled"):
        st = tickers.setdefault(HEDGE_KEY, {"alerts": {}})
        recs = st.setdefault("alerts", {})
        rec = recs.get("HEDGE")
        if h.get("active"):
            if rec is None or (not rec.get("active") and rec.get("date") != today):
                out.append({**hedge_message(h, rules), "symbol": HEDGE_KEY, "trigger": "HEDGE",
                            "apply": (HEDGE_KEY, "HEDGE", {"date": today, "rung": 1, "active": True})})
            elif not rec.get("active"):
                rec["active"] = True
        elif rec:
            rec["active"] = False
    return out, state


def digest(result: dict, state: dict, today: str, rules: dict) -> dict | None:
    """Low-priority post-close list of WATCH names (IVR ≥ 50, no spike), once per day."""
    if not rules["alerts"].get("daily_digest") or state.get("digest_date") == today:
        return None
    watch = [t for t in result.get("tickers", []) if t.get("action") == "WATCH"]
    if not watch:
        return None
    lines = []
    for t in watch:
        sp = t.get("spike") or {}
        src = t.get("ivr_source")
        lines.append(f"{t['symbol']} {_money(t.get('price'))} · IVR {t.get('ivr') or 0:.0f}"
                     f"{f' ({src})' if src and src != 'true' else ''} · {t.get('regime')}"
                     + (f" · {'▼' if sp.get('dir') == 'down' else '▲'} {sp.get('size', 0):.1f}σ" if sp.get("dir") else ""))
    ac = rules["alerts"]
    return {"title": f"WATCH · {len(watch)} name{'s' if len(watch) > 1 else ''}",
            "body": "IVR ≥ 50, waiting for a spike:\n" + "\n".join(lines),
            "priority": ac["priority"]["digest"], "tags": [ac["tags"].get("DIGEST", "eyes")],
            "click": ac["dashboard_url"], "symbol": None, "trigger": "DIGEST"}


# ---------------------------------------------------------------- sending

def send(msg: dict, topic: str, server: str = "https://ntfy.sh", timeout: float = 15) -> bool:
    """POST to {server}/{topic}. Title/priority/tags/click go as query params, which ntfy reads
    the same as headers and which carry UTF-8 (·, Δ) safely. Never logs the topic."""
    params = {"title": msg["title"], "priority": msg.get("priority", "default"),
              "tags": ",".join(msg.get("tags") or []), "click": msg.get("click", "")}
    try:
        r = requests.post(f"{server.rstrip('/')}/{topic}", data=msg["body"].encode("utf-8"),
                          params={k: v for k, v in params.items() if v}, timeout=timeout)
        if r.status_code >= 400:
            log.warning("ntfy rejected %r: HTTP %s", msg["title"], r.status_code)
            return False
        return True
    except requests.RequestException as e:
        log.warning("ntfy send failed for %r: %s", msg["title"], type(e).__name__)
        return False


def process(result: dict, mode: str, rules: dict, state_path: Path | None = None,
            topic: str | None = None, sender=send) -> dict:
    """Evaluate, send and persist. Returns a summary for the log."""
    ac = rules.get("alerts") or {}
    if not ac.get("enabled", True):
        return {"status": "disabled"}
    topic = topic if topic is not None else os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return {"status": "skipped (NTFY_TOPIC not set)"}
    today = result.get("scan_date") or date.today().isoformat()
    state = load_state(state_path)
    msgs, state = evaluate(result, state, today, rules)
    if mode == "close":
        dg = digest(result, state, today, rules)
        if dg:
            msgs.append(dg)
    sent, failed = [], []
    for m in msgs:
        if sender(m, topic, ac.get("ntfy_server", "https://ntfy.sh")):
            sent.append(m["title"])
            if m.get("apply"):
                sym, trig, rec = m["apply"]
                state["tickers"][sym]["alerts"][trig] = rec
            if m["trigger"] == "DIGEST":
                state["digest_date"] = today
        else:
            failed.append(m["title"])
    save_state(state, state_path)
    return {"status": "ok", "sent": sent, "failed": failed}


def send_test(rules: dict, topic: str | None = None, sender=send) -> bool:
    ac = rules["alerts"]
    topic = topic if topic is not None else os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        raise SystemExit("NTFY_TOPIC is not set: add it under Settings → Secrets and variables → Actions")
    msg = {"title": "vol-wheel test alert",
           "body": "If you can read this, phone alerts work. Tap to open the dashboard.",
           "priority": "default", "tags": ["white_check_mark"], "click": ac["dashboard_url"]}
    return sender(msg, topic, ac.get("ntfy_server", "https://ntfy.sh"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="vol-wheel ntfy alerts")
    ap.add_argument("--test", action="store_true", help="send a test notification")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if a.test:
        ok = send_test(load_rules())
        log.info("test alert %s", "sent" if ok else "FAILED")
        return 0 if ok else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
