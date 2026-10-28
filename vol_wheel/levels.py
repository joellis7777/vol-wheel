"""Level trades: short-dated options struck at technical levels (Jordan, 2026-10-28).

Puts just above a nearby swing low, as a way to buy at a level you'd place a limit order at anyway
(keep the premium if it holds; get assigned if it doesn't). Calls mirror it to trim: just below a
nearby swing high, or, in price discovery (no swing high above), well above a price stretched far
over its EMA. Single stocks only; the core ETFs are scaled through the portfolio ladder.

These are alerts to consider, not signals with a measured edge (no backtest of the level edge yet).
Config: `level_trades` in rules.yaml.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import signals
from .strikes import expected_move


def in_scope(sym: str, rules: dict) -> bool:
    lc = rules.get("level_trades") or {}
    if not lc.get("enabled"):
        return False
    scope = lc.get("symbols", "single_stocks")
    if scope == "single_stocks":
        return sym not in rules.get("earnings", {}).get("etfs", [])
    return sym in scope


def short_expiry(opts: pd.DataFrame, lo: int, hi: int) -> tuple[date | None, int | None]:
    """Shortest listed expiry with lo <= DTE <= hi."""
    if opts.empty:
        return None, None
    exp = opts.groupby("expiry")["dte"].first()
    exp = exp[(exp >= lo) & (exp <= hi)]
    if not len(exp):
        return None, None
    e = exp.idxmin()
    return e, int(exp[e])


def spans_report(report: str | None, timing: str | None, expiry: date) -> bool:
    if not report:
        return False
    d = date.fromisoformat(report)
    return d < expiry or (d == expiry and (timing or "").lower() != "amc")


def _candidates(opts: pd.DataFrame, expiry: date, side: str, lo: float, hi: float, price: float,
                cfg: dict) -> list[dict]:
    o = opts[(opts["expiry"] == expiry) & (opts["type"] == side) & (opts["strike"] >= lo) & (opts["strike"] <= hi)]
    o = o[o["strike"] < price] if side == "P" else o[o["strike"] > price]
    out = []
    for _, r in o.iterrows():
        bid, ask, mid = r["bid"], r["ask"], r["mid"]
        if not (np.isfinite(bid) and np.isfinite(ask)) or bid <= 0 or mid <= 0:
            continue
        spread = ask - bid
        if not (spread <= cfg["max_spread_pct"] / 100 * mid or spread <= cfg["max_spread_abs"] + 1e-9):
            continue
        if r["oi"] < cfg["min_open_interest"]:
            continue
        dlo, dhi = cfg.get("delta", [0, 100])
        if not dlo <= abs(r["delta"]) * 100 <= dhi:
            continue
        base = r["strike"] if side == "P" else price
        yld = mid / base * 100
        if yld < cfg["min_yield_pct"]:
            continue
        dte = max(int(r["dte"]), 1)
        out.append({"strike": float(r["strike"]), "expiry": expiry.isoformat(), "dte": dte,
                    "delta": float(r["delta"]), "bid": float(bid), "ask": float(ask), "mid": float(mid),
                    "iv": float(r["iv"]), "oi": float(r["oi"]), "spread_pct": spread / mid * 100,
                    "yield_pct": yld, "annualized": yld / 100 * 365 / dte,
                    "breakeven": float(r["strike"] - mid if side == "P" else r["strike"] + mid)})
    # Puts: highest strike first (most premium, likeliest assignment); calls: lowest first.
    out.sort(key=lambda c: -c["strike"] if side == "P" else c["strike"])
    return out[:cfg.get("top_n", 3)]


def level_trades(opts: pd.DataFrame, hist: pd.DataFrame, price: float, iv: float, cfg: dict,
                 report: str | None = None, timing: str | None = None) -> dict:
    """{expiry, dte, em_week, note, put, call}. put/call: {level, kind, dist_pct, dist_em, near, active,
    limit, candidates, ...}; call.mode is 'resistance' or 'discovery'."""
    exp, dte = short_expiry(opts, *cfg["dte"])
    out = {"expiry": exp.isoformat() if exp else None, "dte": dte, "put": None, "call": None,
           "em_week": expected_move(price, iv, cfg["em_days"]), "note": None}
    if exp is None:
        out["note"] = f"no expiry of {cfg['dte'][0]}–{cfg['dte'][1]} DTE"
        return out
    if spans_report(report, timing, exp):
        out["note"] = f"the {exp.isoformat()} expiry spans earnings {report}"
        return out
    em = out["em_week"]
    if not (np.isfinite(em) and em > 0):
        out["note"] = "no IV for the expected move"
        return out
    zone, off = cfg["zone_pct"] / 100, cfg["limit_offset_pct"] / 100
    recent = hist.iloc[-cfg["swing_lookback_days"]:]

    lows = [v for v in signals.swing_points(recent["low"], cfg["swing_order"], "low") if v < price]
    if lows:
        lv = max(lows)
        near = (price - lv) <= cfg["near_em"] * em
        cands = _candidates(opts, exp, "P", lv, lv * (1 + zone), price, cfg) if near else []
        out["put"] = {"level": lv, "kind": "swing low", "dist_pct": (price / lv - 1) * 100,
                      "dist_em": (price - lv) / em, "near": bool(near), "limit": lv * (1 + off),
                      "zone": [lv, lv * (1 + zone)], "candidates": cands, "active": bool(near and cands)}

    highs = [v for v in signals.swing_points(recent["high"], cfg["swing_order"], "high") if v > price]
    if highs:
        lv = min(highs)
        near = (lv - price) <= cfg["near_em"] * em
        cands = _candidates(opts, exp, "C", lv * (1 - zone), lv, price, cfg) if near else []
        out["call"] = {"mode": "resistance", "level": lv, "kind": "swing high", "dist_pct": (lv / price - 1) * 100,
                       "dist_em": (lv - price) / em, "near": bool(near), "limit": lv * (1 - off),
                       "zone": [lv * (1 - zone), lv], "candidates": cands, "active": bool(near and cands)}
    else:
        dc = cfg["discovery"]
        ema = float(hist["close"].ewm(span=dc["ema_days"], adjust=False).mean().iloc[-1])
        stretch = (price - ema) / em
        on = stretch >= dc["stretch_em"]
        k_min = price + dc["strike_em"] * expected_move(price, iv, dte)
        cands = _candidates(opts, exp, "C", k_min, np.inf, price, cfg) if on else []
        out["call"] = {"mode": "discovery", "level": None, "kind": "price discovery", "ema": ema,
                       "ema_days": dc["ema_days"], "stretch_em": stretch, "stretch_min": dc["stretch_em"], "near": bool(on), "strike_min": k_min,
                       "candidates": cands, "active": bool(on and cands)}
    return out
