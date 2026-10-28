"""Extended-hours watch (Jordan, 2026-10-28): price-only scans before the open and after the close.

Options don't trade outside 09:30–16:00 ET, but shares do (limit orders). This checks each universe
name's latest extended-hours trade against its regular-session close and alerts on a big move, with
the context that decides whether it's worth acting on: an earnings report, the market moving with it,
a swing level crossed, the implied move. The guidance lines come from the 2026-10-28 gap study
(50 names, 2010→): earnings gap-downs bought at the open lagged the stock's own drift by ~1.5% over 20
days; market-wide gap-downs gained ~3.5%; stock-specific ones showed no edge.

Writes docs/data/extended.json (the dashboard's "After hours" / "Pre-market" panel); never touches
latest.json or the IV history. Config: `extended_hours` in rules.yaml.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import data, earnings, signals
from .config import universe

log = logging.getLogger(__name__)

GUIDE = {
    ("down", "earnings"): "Earnings gap-downs bought at the open lagged by ~1.5% over the next 20 days (2010–26 study): "
                          "no rush; the drift tends to continue.",
    ("down", "market"): "Market-wide gap-downs bounced (~+3.5% over 20 days in the study): the kind of dip the core buys.",
    ("down", "stock"): "Stock-specific gap-downs without earnings showed no edge either way.",
    ("up", "earnings"): "Earnings gap-up: calls only if holding shares; consider trimming into strength.",
    ("up", "market"): "Market-wide gap-up.",
    ("up", "stock"): "Stock-specific gap-up.",
}


def phase(now: datetime, tz: str = "America/New_York") -> str:
    """'pre' (before 09:30 ET on a weekday), 'regular', 'post' (after 16:00) or 'closed' (weekend)."""
    et = now.astimezone(ZoneInfo(tz))
    if et.weekday() >= 5:
        return "closed"
    hm = (et.hour, et.minute)
    return "pre" if hm < (9, 30) else "regular" if hm < (16, 0) else "post"


def in_window(now: datetime, cfg: dict, tz: str = "America/New_York") -> bool:
    """True inside the configured pre-market or after-hours window (`extended_hours.windows`)."""
    ph = phase(now, tz)
    win = (cfg.get("windows") or {}).get(ph)
    if not win:
        return False
    et = now.astimezone(ZoneInfo(tz))
    hm = et.strftime("%H:%M")
    return win[0] <= hm < win[1]


def parse_quote(payload: dict) -> dict:
    d = payload.get("data", payload) if isinstance(payload, dict) else {}
    num = data._num
    return {"last": num(d.get("current_price")), "close": num(d.get("close")),
            "prev_close": num(d.get("prev_day_close")), "bid": num(d.get("bid")), "ask": num(d.get("ask")),
            "last_trade_time": d.get("last_trade_time")}


def fetch_quote(sym: str, cfg: dict) -> dict:
    url = cfg["cboe_quote_url"].format(sym=sym)
    return parse_quote(data.get_json(url, cfg.get("timeout_s", 30), cfg.get("retries", 3)))


def reference_close(q: dict, hist: pd.DataFrame | None, ref_day: date) -> float:
    """The regular-session close the extended move is measured from: history's bar for ref_day when it
    has one (pre-market), else CBOE's `close` (post-market, before the daily bar is published)."""
    if hist is not None and len(hist) and hist.index[-1].date() == ref_day:
        return float(hist["close"].iloc[-1])
    c = q.get("close", float("nan"))
    if np.isfinite(c) and c > 0:
        return float(c)
    return float(hist["close"].iloc[-1]) if hist is not None and len(hist) else float("nan")


def report_context(e: dict | None, ref_day: date, ph: str) -> dict | None:
    """The earnings report this extended session belongs to: after the close of ref_day, or before the
    next open. Unknown timing counts for both."""
    if not e:
        return None
    nxt_day = ref_day + timedelta(days=1)
    while nxt_day.weekday() >= 5:
        nxt_day += timedelta(days=1)
    for key in ("next", "last"):
        info = e.get(key) or {}
        if not info.get("date"):
            continue
        d, timing = date.fromisoformat(info["date"]), (info.get("timing") or "").lower()
        if (d == ref_day and timing != "bmo") or (d == nxt_day and timing != "amc"):
            im = e.get("implied_move") if key == "next" else (info.get("implied_move") or e.get("implied_move"))
            return {"date": info["date"], "timing": info.get("timing"), "implied_move": im}
    return None


def nearest_levels(hist: pd.DataFrame | None, ref: float, cfg: dict) -> tuple[float | None, float | None]:
    if hist is None or len(hist) < 2 * cfg["swing_order"] + 1:
        return None, None
    recent = hist.iloc[-cfg["swing_lookback_days"]:]
    lows = [v for v in signals.swing_points(recent["low"], cfg["swing_order"], "low") if v < ref]
    highs = [v for v in signals.swing_points(recent["high"], cfg["swing_order"], "high") if v > ref]
    return (max(lows) if lows else None), (min(highs) if highs else None)


def assess(sym: str, q: dict, hist: pd.DataFrame | None, ec: dict | None, ref_day: date, ph: str,
           market_move: float | None, rules: dict) -> dict | None:
    xc, lc = rules["extended_hours"], rules["level_trades"]
    last, ref = q.get("last", float("nan")), reference_close(q, hist, ref_day)
    if not (np.isfinite(last) and np.isfinite(ref) and last > 0 and ref > 0):
        return None
    move = (last / ref - 1) * 100
    hv20 = float("nan")
    if hist is not None and len(hist) > 21:
        s = signals.hv(hist["close"], 20).dropna()
        hv20 = float(s.iloc[-1]) if len(s) else float("nan")
    z = math.log(last / ref) / (hv20 / math.sqrt(252)) if np.isfinite(hv20) and hv20 > 0 else float("nan")
    dirn = "down" if move < 0 else "up"
    rep = report_context(ec, ref_day, ph)
    mkt = (market_move is not None and sym != xc.get("market_symbol", "SPY")
           and abs(market_move) >= xc["market_move_pct"] and (market_move < 0) == (move < 0))
    kind = "earnings" if rep else "market" if mkt else "stock"
    low, high = nearest_levels(hist, ref, lc)
    crossed = None
    if dirn == "down" and low is not None and last < low:
        crossed = {"kind": "swing low", "level": low}
    elif dirn == "up" and high is not None and last > high:
        crossed = {"kind": "swing high", "level": high}
    im = (rep or {}).get("implied_move")
    hit = abs(move) >= xc["min_move_pct"] and (not np.isfinite(z) or abs(z) >= xc["min_z"])
    return {"symbol": sym, "ref_close": ref, "last": last, "bid": q.get("bid"), "ask": q.get("ask"),
            "move_pct": move, "z": z, "dir": dirn, "kind": kind, "earnings": rep,
            "implied_move_pct": im * 100 if im else None,
            "move_vs_implied": abs(move) / (im * 100) if im else None,
            "swing_low": low, "swing_high": high, "crossed": crossed, "alert": bool(hit),
            "guide": GUIDE[(dirn, kind)]}


def run(rules: dict, now: datetime | None = None, symbols: list[str] | None = None,
        quote_fn=None, hist_fn=None, earn_cache: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    sc, dc = rules.get("schedule", {}), rules["data"]
    tz = sc.get("timezone", "America/New_York")
    ph = phase(now, tz)
    ref_day = data.session_date(now, tz, sc.get("market_open", "09:30"))
    quote_fn = quote_fn or (lambda s: fetch_quote(s, dc))
    hist_fn = hist_fn or (lambda s: data.fetch_history(s, dc)[0])
    earn_cache = earn_cache if earn_cache is not None else earnings.load_cache(earnings.cache_path(rules.get("earnings", {})))
    uni = [t for t in universe(rules) if not symbols or t["symbol"] in symbols]
    mkt_sym = rules["extended_hours"].get("market_symbol", "SPY")
    notes, quotes = [], {}
    for s in dict.fromkeys([mkt_sym] + [t["symbol"] for t in uni]):
        try:
            quotes[s] = quote_fn(s)
        except Exception as e:  # noqa: BLE001
            notes.append(f"{s}: quote unavailable ({str(e)[:80]})")
    market_move = None
    mq = quotes.get(mkt_sym)
    if mq and np.isfinite(mq["last"]) and np.isfinite(mq["close"]) and mq["close"] > 0:
        market_move = (mq["last"] / mq["close"] - 1) * 100
    rows = []
    for t in uni:
        s = t["symbol"]
        if s not in quotes:
            continue
        try:
            hist = hist_fn(s)
        except Exception as e:  # noqa: BLE001
            hist = None
            notes.append(f"{s}: history unavailable ({str(e)[:80]})")
        r = assess(s, quotes[s], hist, earn_cache.get(s), ref_day, ph, market_move, rules)
        if r:
            r.update(bucket=t["bucket"], role=t["role"])
            rows.append(r)
    rows.sort(key=lambda r: -abs(r["move_pct"]))
    et = now.astimezone(ZoneInfo(tz))
    return {"generated_at": now.isoformat(timespec="seconds"), "et": et.strftime("%H:%M"), "phase": ph,
            "session_date": ref_day.isoformat(), "market_symbol": mkt_sym, "market_move_pct": market_move,
            "show_min_pct": rules["extended_hours"].get("show_min_pct", 1.5), "rows": rows, "notes": notes}
