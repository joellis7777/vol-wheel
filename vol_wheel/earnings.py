"""Earnings mode: next earnings dates, implied earnings move, ex-earnings IV, earnings plays and
post-earnings gaps.

Dates come from Nasdaq's analyst earnings-date endpoint (yfinance as fallback) and are cached in
data/earnings.json so a failed fetch falls back to yesterday's answer. ETFs have no earnings.

Implied move (term structure): with E1 the first expiry after the earnings reaction and E2 a later
one, ATM IVs s1, s2 and year fractions T1 < T2, assume a constant base vol plus one earnings jump:
    s1^2 T1 = b^2 T1 + e^2,   s2^2 T2 = b^2 T2 + e^2
    b^2 = (s2^2 T2 - s1^2 T1) / (T2 - T1),   e^2 = (s1^2 - b^2) T1
e is the one-day 1-sigma earnings move (fraction of price). Ex-earnings iv30 removes that variance
from the 30-day window: sqrt(iv30^2 - e^2 / (30/365)). If any step is non-positive the estimate is
not feasible and IV rank is flagged "earnings-inflated".
"""
from __future__ import annotations

import json
import logging
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import data
from .config import ROOT

log = logging.getLogger("vol_wheel.earnings")

MONTH_DATE = re.compile(r"([A-Z][a-z]{2})[a-z]*\.? (\d{1,2}), (\d{4})")
SLASH_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


# ---------------------------------------------------------------- dates

def next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def reaction_date(edate: date, timing: str | None) -> date:
    """First session whose prices include the report: same day if before the open, else the next
    weekday (after the close or unknown timing)."""
    return edate if timing == "bmo" else next_weekday(edate)


def parse_nasdaq(payload: dict) -> dict | None:
    """{"data": {"announcement": "Earnings announcement* for NVDA: Nov 19, 2026",
                 "reportText": "... is estimated to report earnings on 11/19/2026 after market close ..."}}"""
    d = (payload or {}).get("data") or {}
    text = " ".join(str(d.get(k) or "") for k in ("announcement", "reportText"))
    edate = None
    m = MONTH_DATE.search(text)
    if m:
        try:
            edate = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").date()
        except ValueError:
            edate = None
    if edate is None:
        m = SLASH_DATE.search(text)
        if m:
            try:
                edate = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                edate = None
    if edate is None:
        return None
    low = text.lower()
    timing = "amc" if "after market close" in low or "after-hours" in low else \
        "bmo" if "before market open" in low or "pre-market" in low else None
    return {"date": edate.isoformat(), "timing": timing, "estimated": "estimat" in low or "*" in text}


def fetch_nasdaq(sym: str, url_tmpl: str) -> dict | None:
    headers = {"Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
    r = data.session().get(url_tmpl.format(sym=sym.lower()), headers=headers, timeout=20)
    r.raise_for_status()
    return parse_nasdaq(r.json())


def fetch_yf(sym: str, today: date) -> dict | None:
    import yfinance as yf  # optional dependency

    cal = yf.Ticker(sym).calendar
    dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
    for d in dates or []:
        d = d.date() if isinstance(d, datetime) else d
        if isinstance(d, date) and d >= today:
            return {"date": d.isoformat(), "timing": None, "estimated": True}
    return None


def is_past(info: dict | None, today: date) -> bool:
    if not info or not info.get("date"):
        return False
    return reaction_date(date.fromisoformat(info["date"]), info.get("timing")) <= today and \
        date.fromisoformat(info["date"]) <= today


def load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def cache_path(cfg: dict) -> Path:
    return ROOT / cfg.get("cache_path", "data/earnings.json")


def save_cache(cache: dict, cfg: dict, path: Path | None = None) -> None:
    p = path or cache_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")


def refresh(symbols: list[str], today: date, cfg: dict, fetch=None, cache: dict | None = None) -> tuple[dict, list[str]]:
    """Update the earnings cache for single stocks (call save_cache after the scan); returns
    (cache, notes).

    A report that has happened moves from `next` to `last`, carrying the implied move recorded on
    the last scan before it (used for the post-earnings gap). Fetch failures keep the cached date.
    """
    cache = load_cache(cache_path(cfg)) if cache is None else cache
    notes: list[str] = []
    fetch = fetch or (lambda s: _fetch_any(s, today, cfg))
    for sym in symbols:
        e = cache.setdefault(sym, {})
        nxt = e.get("next")
        if nxt and is_past(nxt, today):
            e["last"] = {**nxt, "implied_move": e.get("implied_move")}
            e["next"] = None
            e.pop("implied_move", None)
        if e.get("fetched") == today.isoformat() and e.get("next"):
            continue
        try:
            got = fetch(sym)
        except Exception as ex:  # noqa: BLE001 - any source failure falls back to the cache
            got = None
            notes.append(f"{sym}: earnings date fetch failed ({type(ex).__name__}); using cache")
        if got and date.fromisoformat(got["date"]) >= today and not is_past(got, today):
            e["next"] = {k: got[k] for k in ("date", "timing", "estimated", "source") if k in got}
            e["fetched"] = today.isoformat()
        elif got is None and not e.get("next") and not any(n.startswith(f"{sym}:") for n in notes):
            notes.append(f"{sym}: no upcoming earnings date found")
    return cache, notes


def _fetch_any(sym: str, today: date, cfg: dict) -> dict | None:
    err = None
    try:
        got = fetch_nasdaq(sym, cfg["nasdaq_url"])
        if got:
            return {**got, "source": "nasdaq"}
    except Exception as ex:  # noqa: BLE001
        err = ex
        log.warning("nasdaq earnings %s failed: %s", sym, ex)
    try:
        got = fetch_yf(sym, today)
        if got:
            return {**got, "source": "yfinance"}
    except Exception as ex:  # noqa: BLE001
        log.warning("yfinance earnings %s failed: %s", sym, ex)
        err = err or ex
    if err:
        raise err
    return None


# ---------------------------------------------------------------- implied move

def atm_iv(opts: pd.DataFrame, expiry: date, price: float) -> tuple[float, float]:
    """(mean IV, straddle mid) at the strike nearest the money for one expiry."""
    o = opts[(opts["expiry"] == expiry) & (opts["iv"] > 0) & (opts["bid"] > 0)]
    if o.empty:
        return float("nan"), float("nan")
    k = o.iloc[(o["strike"] - price).abs().argsort()]["strike"].iloc[0]
    atm = o[o["strike"] == k]
    straddle = atm.groupby("type")["mid"].first().sum() if set(atm["type"]) == {"C", "P"} else float("nan")
    return float(atm["iv"].mean()), float(straddle)


def implied_move(opts: pd.DataFrame, price: float, edate: date, timing: str | None, today: date,
                 iv30: float, cfg: dict) -> dict:
    """Term-structure earnings move, straddle move and ex-earnings iv30. Pure."""
    out = {"feasible": False, "move": None, "straddle_move": None, "iv30_ex": None, "base_iv": None,
           "e1": None, "e2": None}
    react = reaction_date(edate, timing)
    exps = sorted(e for e in opts["expiry"].unique() if e >= react)
    if not exps:
        return {**out, "why": "no expiry after earnings"}
    e1 = exps[0]
    later = [e for e in exps[1:] if (e - e1).days >= cfg.get("min_term_gap_days", 5)]
    s1, straddle = atm_iv(opts, e1, price)
    out["e1"] = e1.isoformat()
    # The straddle only approximates the earnings move when E1 expires right after the report and
    # soon (otherwise it is mostly base vol).
    if (np.isfinite(straddle) and price > 0 and (e1 - react).days <= cfg.get("straddle_max_days_after", 7)
            and (e1 - today).days <= cfg.get("straddle_max_dte", 14)):
        out["straddle_move"] = straddle / price
    if not later or not np.isfinite(s1):
        return {**out, "why": "no second expiry for the term structure"}
    e2 = later[0]
    s2, _ = atm_iv(opts, e2, price)
    out["e2"] = e2.isoformat()
    t1, t2 = max((e1 - today).days, 1) / 365.0, max((e2 - today).days, 1) / 365.0
    if not np.isfinite(s2) or t2 <= t1:
        return {**out, "why": "bad term structure"}
    b2 = (s2 * s2 * t2 - s1 * s1 * t1) / (t2 - t1)
    e2var = (s1 * s1 - b2) * t1
    days_to = (edate - today).days
    in_iv = np.isfinite(iv30) and 0 <= days_to <= cfg.get("iv_window_days", 30)
    if b2 <= 0:
        return {**out, "why": "front IV too high for a base-vol fit"}
    min_move = cfg.get("min_move", 0.005)
    if e2var <= min_move * min_move:
        # No earnings premium visible in the term structure: iv30 isn't inflated, nothing to strip.
        out.update(feasible=True, move=None, base_iv=math.sqrt(b2), why="no earnings bump in the term structure")
        if in_iv:
            out["iv30_ex"] = iv30
        return out
    out.update(feasible=True, move=math.sqrt(e2var), base_iv=math.sqrt(b2))
    if in_iv:
        w = cfg.get("iv_window_days", 30) / 365.0
        rest = iv30 * iv30 - e2var / w
        if rest > 0:
            # If iv30 holds less of the jump than the term structure implies, the subtraction
            # overshoots; never go below the fitted base vol (capped at iv30).
            out["iv30_ex"] = max(math.sqrt(rest), min(math.sqrt(b2), iv30))
        else:
            out.update(feasible=False, why="earnings variance exceeds the 30-day IV")
    return out


def move_for_strikes(im: dict) -> float | None:
    """Earnings move used for strike distance: the term-structure move; the straddle only when the
    term structure couldn't be read at all (never when it read and found no bump)."""
    if im.get("feasible"):
        return im.get("move")
    return im.get("straddle_move")


def pre_earnings_expiry(opts: pd.DataFrame, edate: date, timing: str | None, today: date,
                        cfg: dict) -> tuple[date, int] | None:
    """Latest expiry inside [min_dte, max_dte] that settles before the report: on or before the
    report day for after-close reports, strictly before it otherwise (before-open or unknown)."""
    pc = cfg.get("pre_earnings_expiry") or {}
    if not pc.get("enabled") or opts is None or opts.empty:
        return None
    exps = opts.groupby("expiry")["dte"].first()
    ok = [(e, int(d)) for e, d in exps.items()
          if pc.get("min_dte", 21) <= d <= pc.get("max_dte", 34)
          and (e <= edate if timing == "amc" else e < edate)]
    if not ok:
        return None
    if pc.get("prefer_monthly"):
        from .strikes import is_monthly
        monthly = [x for x in ok if is_monthly(x[0], set(exps.index))]
        ok = monthly or ok
    return max(ok, key=lambda x: x[1])


# ---------------------------------------------------------------- signals

def trend(close: pd.Series, days: int = 5, hv20: float = float("nan")) -> dict:
    """5-day return and its size in HV20 units."""
    c = pd.Series(close, dtype=float).dropna()
    if len(c) <= days:
        return {"ret": None, "z": None}
    r = float(c.iloc[-1] / c.iloc[-1 - days] - 1)
    z = r / (hv20 * math.sqrt(days / 252.0)) if np.isfinite(hv20) and hv20 > 0 else None
    return {"ret": r, "z": z}


def post_gap(close: pd.Series, last: dict | None, today: date, cfg: dict, max_days: int = 3) -> dict | None:
    """Post-earnings move since the pre-report close, if the reaction was within the last
    `max_days` sessions and it's >= gap_mult x the implied move recorded before the report."""
    if not last or not last.get("date") or not last.get("implied_move"):
        return None
    edate = pd.Timestamp(last["date"])
    c = pd.Series(close, dtype=float).dropna()
    # Pre-report close: the report day's close for after-close reports, otherwise the close before
    # the report day (covers before-open reports and unknown timing, which Nasdaq often omits).
    before = c[c.index <= edate] if last.get("timing") == "amc" else c[c.index < edate]
    if before.empty:
        return None
    after = c[c.index > before.index[-1]]
    if after.empty or len(after) > max_days or pd.Timestamp(today) < after.index[0]:
        return None
    move = float(c.iloc[-1] / before.iloc[-1] - 1)
    ratio = abs(move) / last["implied_move"]
    if ratio < cfg.get("gap_mult", 1.5):
        return None
    return {"dir": "down" if move < 0 else "up", "move": move, "implied_move": last["implied_move"],
            "ratio": ratio, "date": last["date"]}


def earnings_context(sym: str, cache: dict, opts: pd.DataFrame, price: float, iv30: float, today: date,
                     expiry: date | None, cfg: dict) -> dict:
    """Everything the scanner needs about earnings for one ticker."""
    if sym in cfg.get("etfs", []):
        return {"applies": False}
    e = cache.get(sym) or {}
    nxt = e.get("next")
    out = {"applies": True, "next": nxt, "last": e.get("last"), "days_to": None, "in_window": False,
           "in_iv_window": False, "implied": None}
    if not nxt:
        return out
    edate = date.fromisoformat(nxt["date"])
    out["days_to"] = (edate - today).days
    react = reaction_date(edate, nxt.get("timing"))
    out["in_window"] = bool(expiry and react <= expiry)
    out["in_iv_window"] = 0 <= out["days_to"] <= cfg.get("iv_window_days", 30)
    if (out["in_window"] or out["in_iv_window"]) and opts is not None and not opts.empty:
        out["implied"] = implied_move(opts, price, edate, nxt.get("timing"), today, iv30, cfg)
    return out
