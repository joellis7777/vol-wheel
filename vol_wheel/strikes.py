"""Strike selection: value inside a delta band.

For each side: choose the ~45 DTE monthly, keep strikes within target delta +/- band, apply
hard filters (spread, open interest, minimum credit), score five factors 0..1 and return the
top N with a one-line reason. Also: LEAP candidate and ladder rungs.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import signals

LEVEL_LABELS = {
    "sma50": "50-day avg", "sma100": "100-day avg", "sma200": "200-day avg",
    "swing": "swing low", "swing_high": "swing high", "round": "round number",
    "oi_wall": "put-OI wall", "oi_wall_call": "call-OI wall",
}


def _clip01(x: float) -> float:
    if not np.isfinite(x):
        return 0.0
    return float(min(1.0, max(0.0, x)))


# ---------------------------------------------------------------- expiry

def is_monthly(d: date, expiries: set[date] | None = None) -> bool:
    """Third-Friday monthly (or the Thursday before when that Friday is a holiday)."""
    if d.weekday() == 4 and 15 <= d.day <= 21:
        return True
    if d.weekday() == 3 and 14 <= d.day <= 20:
        return expiries is None or (d + timedelta(days=1)) not in expiries
    return False


def choose_expiry(opts: pd.DataFrame, cfg: dict) -> tuple[date | None, int | None, str]:
    """Monthly closest to target inside [dte_min, dte_max]; else any expiry in the window;
    else the expiry closest to target overall."""
    if opts.empty:
        return None, None, "empty chain"
    exp = opts.groupby("expiry")["dte"].first()
    exp_set = set(exp.index)
    lo, hi, tgt = cfg["dte_min"], cfg["dte_max"], cfg["dte_target"]
    inwin = exp[(exp >= lo) & (exp <= hi)]
    if cfg.get("prefer_monthly", True):
        monthly = inwin[[is_monthly(e, exp_set) for e in inwin.index]]
        if len(monthly):
            e = (monthly - tgt).abs().idxmin()
            return e, int(exp[e]), "monthly"
    if len(inwin):
        e = (inwin - tgt).abs().idxmin()
        return e, int(exp[e]), "weekly (no monthly in window)"
    pos = exp[exp > 0]
    if len(pos):
        e = (pos - tgt).abs().idxmin()
        return e, int(exp[e]), f"outside {lo}-{hi} DTE window"
    return None, None, "no future expiries"


# ---------------------------------------------------------------- skew

def skew_fit(exp_opts: pd.DataFrame, price: float):
    """Quadratic fit of IV vs log-moneyness on OTM quotes of one expiry. Returns poly or None."""
    o = exp_opts[(exp_opts["iv"] > 0) & (exp_opts["bid"] > 0)]
    otm = o[((o["type"] == "P") & (o["strike"] <= price)) | ((o["type"] == "C") & (o["strike"] >= price))]
    if len(otm) < 5:
        return None
    x = np.log(otm["strike"].values / price)
    try:
        coef = np.polyfit(x, otm["iv"].values, 2)
    except (np.linalg.LinAlgError, ValueError):
        return None
    return np.poly1d(coef)


def skew_residual(poly, strike: float, iv: float, price: float) -> float:
    if poly is None or not np.isfinite(iv):
        return float("nan")
    return float(iv - poly(math.log(strike / price)))


# ---------------------------------------------------------------- levels

def nice_step(price: float, frac: float = 0.05) -> float:
    """Round-number step near frac*price, snapped to 1/2/2.5/5 x 10^n."""
    raw = max(price * frac, 1e-6)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw * 0.999:
            return m * mag
    return 10 * mag


def levels(hist: pd.DataFrame, opts: pd.DataFrame, price: float, side: str, cfg: dict) -> list[dict]:
    """Support levels below price (side='P') or resistance above price (side='C')."""
    sc = cfg["support"]
    strength = sc.get("strength", {})
    rng = sc.get("level_range_pct", 25) / 100.0
    below = side == "P"

    def ok(v: float) -> bool:
        if not np.isfinite(v):
            return False
        return (price * (1 - rng) <= v < price) if below else (price < v <= price * (1 + rng))

    out: list[dict] = []
    close = hist["close"]
    for w in (50, 100, 200):
        v = signals.sma(close, w)
        if ok(v):
            out.append({"value": v, "kind": f"sma{w}", "strength": strength.get(f"sma{w}", 1.0)})
    recent = hist.iloc[-sc.get("swing_lookback_days", 120):]
    order = sc.get("swing_order", 5)
    swings = signals.swing_points(recent["low"] if below else recent["high"], order, "low" if below else "high")
    for v in sorted(set(round(x, 2) for x in swings)):
        if ok(v):
            out.append({"value": v, "kind": "swing" if below else "swing_high", "strength": strength.get("swing", 1.0)})
    step = nice_step(price, sc.get("round_step_frac", 0.05))
    k0 = math.floor(price / step) if below else math.ceil(price / step)
    for i in range(0, 12):
        v = (k0 - i) * step if below else (k0 + i) * step
        if abs(v - price) < 1e-9:
            continue
        if ok(v):
            out.append({"value": float(v), "kind": "round", "strength": strength.get("round", 0.7)})
    if not opts.empty:
        near = opts[(opts["type"] == side) & (opts["dte"] > 0) & (opts["dte"] <= sc.get("oi_wall_max_dte", 60))]
        if len(near):
            oi = near.groupby("strike")["oi"].sum()
            oi = oi[[ok(k) for k in oi.index]]
            if len(oi) and oi.max() > 0:
                out.append({"value": float(oi.idxmax()), "kind": "oi_wall" if below else "oi_wall_call",
                            "strength": strength.get("oi_wall", 0.9), "oi": float(oi.max())})
    return out


def sr_score(strike: float, lv: list[dict], side: str, cfg: dict) -> tuple[float, dict | None, float]:
    """Score a strike against support (puts) / resistance (calls).

    d = % the strike sits beyond the level (below support for puts, above resistance for calls).
    0.5-3% beyond scores 1 (times level strength), fading to 0 at 8%; 0..0.5% ramps 0.5->1.
    A strike within 2% on the wrong side of a level loses `penalty` (times strength).
    Returns (score, best level, d of best level).
    """
    sc = cfg["support"]
    lo, hi, fade = sc["ideal_min_pct"], sc["ideal_max_pct"], sc["fade_to_pct"]
    pz, pen = sc["penalty_zone_pct"], sc["penalty"]
    best, best_lv, best_d = 0.0, None, float("nan")
    penalty = 0.0
    for L in lv:
        v = L["value"]
        d = (v - strike) / v * 100 if side == "P" else (strike - v) / v * 100
        if d < 0:
            if -d <= pz:
                penalty = max(penalty, pen * L["strength"])
            continue
        if d < lo:
            base = 0.5 + 0.5 * d / lo
        elif d <= hi:
            base = 1.0
        elif d < fade:
            base = (fade - d) / (fade - hi)
        else:
            base = 0.0
        base *= L["strength"]
        if base > best:
            best, best_lv, best_d = base, L, d
    return _clip01(best - penalty), best_lv, best_d


# ---------------------------------------------------------------- factor helpers

def richness_score(resid: float, iv: float, hv20: float, cfg: dict) -> float:
    rc = cfg["richness"]
    s_hv = _clip01((iv / hv20 - rc["iv_hv_floor"]) / (rc["iv_hv_cap"] - rc["iv_hv_floor"])) \
        if np.isfinite(hv20) and hv20 > 0 and np.isfinite(iv) else float("nan")
    s_res = _clip01((resid * 100 - rc["resid_floor_pts"]) / (rc["resid_cap_pts"] - rc["resid_floor_pts"])) \
        if np.isfinite(resid) else float("nan")
    w = rc.get("resid_weight", 0.5)
    if np.isfinite(s_res) and np.isfinite(s_hv):
        return w * s_res + (1 - w) * s_hv
    if np.isfinite(s_res):
        return s_res
    if np.isfinite(s_hv):
        return s_hv
    return 0.5


def rank_scores(values: list[float]) -> list[float]:
    """Rank within the band: best = 1, worst = 0, single = 1."""
    v = pd.Series(values, dtype=float)
    if len(v) <= 1:
        return [1.0] * len(v)
    r = v.rank(method="average")
    return list(((r - 1) / (len(v) - 1)).fillna(0).values)


def expected_move(price: float, iv: float, dte: float) -> float:
    if not (np.isfinite(price) and np.isfinite(iv) and dte > 0):
        return float("nan")
    return price * iv * math.sqrt(dte / 365.0)


def assignment_score(be: float, anchors: list[float], cfg: dict) -> float:
    ac = cfg["assignment"]
    best = 0.0
    for a in anchors:
        if not np.isfinite(a) or a <= 0:
            continue
        d = (be - a) / a * 100
        if d <= ac["near_pct"]:
            s = 1.0
        elif d >= ac["fade_to_pct"]:
            s = 0.0
        else:
            s = (ac["fade_to_pct"] - d) / (ac["fade_to_pct"] - ac["near_pct"])
        best = max(best, s)
    return best


# ---------------------------------------------------------------- filters

def passes_filters(row, side: str, cfg: dict) -> tuple[bool, str]:
    bid, ask, mid = row["bid"], row["ask"], row["mid"]
    if not (np.isfinite(bid) and np.isfinite(ask)) or bid <= 0 or ask <= 0 or mid <= 0:
        return False, "no bid"
    spread = ask - bid
    if not (spread <= cfg["max_spread_pct"] / 100.0 * mid or spread <= cfg["max_spread_abs"] + 1e-9):
        return False, "spread"
    if row["oi"] < cfg["min_open_interest"]:
        return False, "open interest"
    if side == "P":
        dabs = abs(row["delta"]) * 100
        need = cfg["put_min_credit_pct_high_delta"] if dabs >= cfg["put_high_delta_cutoff"] \
            else cfg["put_min_credit_pct_low_delta"]
        if mid < need / 100.0 * row["strike"]:
            return False, "credit"
    return True, ""


# ---------------------------------------------------------------- main selection

def select_strikes(opts: pd.DataFrame, side: str, target_delta: float, ctx: dict, cfg: dict,
                   top_n: int | None = None) -> dict:
    """Return {'target', 'band', 'in_band', 'passed', 'rejected': {...}, 'candidates': [...]}.

    ctx: price, iv30 (decimal), hv20 (decimal), hist (DataFrame), expiry, dte, poly (skew fit),
         levels (list for this side), anchors (assignment anchors for puts).
    """
    top_n = top_n or cfg.get("top_n", 3)
    band = cfg["delta_band"]
    price, dte = ctx["price"], ctx["dte"]
    o = opts[(opts["expiry"] == ctx["expiry"]) & (opts["type"] == side)].copy()
    o["dabs"] = o["delta"].abs() * 100
    o = o[(o["dabs"] >= target_delta - band) & (o["dabs"] <= target_delta + band)]
    # Short premium only: OTM strikes.
    o = o[o["strike"] < price] if side == "P" else o[o["strike"] > price]
    res = {"side": side, "target": target_delta, "band": [max(target_delta - band, 0), target_delta + band],
           "in_band": int(len(o)), "passed": 0, "rejected": {}, "candidates": []}
    keep = []
    for _, r in o.iterrows():
        ok, why = passes_filters(r, side, cfg)
        if ok:
            keep.append(r)
        else:
            res["rejected"][why] = res["rejected"].get(why, 0) + 1
    res["passed"] = len(keep)
    if not keep:
        return res

    w = cfg["weights"]
    iv_for_move = ctx["iv30"] if np.isfinite(ctx.get("iv30", np.nan)) else None
    move = None
    rows = []
    for r in keep:
        K, mid, iv = float(r["strike"]), float(r["mid"]), float(r["iv"])
        move = expected_move(price, iv_for_move if iv_for_move else iv, dte)
        if side == "P":
            ann = mid / K * 365.0 / dte
            be = K - mid
            cushion = (price - be) / move if move and move > 0 else float("nan")
            fit = assignment_score(be, ctx.get("anchors", []), cfg)
        else:
            ann = mid / price * 365.0 / dte
            be = K + mid
            cushion = (K - price) / move if move and move > 0 else float("nan")
            fit = 1.0 if K > price else 0.0
        sr, lv, d = sr_score(K, ctx["levels"], side, cfg)
        resid = skew_residual(ctx.get("poly"), K, iv, price)
        rows.append({
            "strike": K, "expiry": ctx["expiry"].isoformat(), "dte": int(dte),
            "delta": round(float(r["delta"]), 3), "bid": float(r["bid"]), "ask": float(r["ask"]),
            "mid": round(mid, 3), "iv": round(iv, 4), "oi": int(r["oi"]),
            "annualized": ann, "breakeven": round(be, 2), "cushion_moves": cushion,
            "iv_resid_pts": resid * 100 if np.isfinite(resid) else None,
            "level": lv, "level_dist_pct": d,
            "f_support": sr, "f_richness": richness_score(resid, iv, ctx.get("hv20", np.nan), cfg),
            "f_cushion": _clip01(cushion / cfg["cushion"]["full_score_moves"]) if np.isfinite(cushion) else 0.0,
            "f_assignment": fit,
            "collateral": K * 100,
        })
    for row, rk in zip(rows, rank_scores([x["annualized"] for x in rows])):
        row["f_roc"] = rk
    for row in rows:
        row["score"] = (w["support"] * row["f_support"] + w["richness"] * row["f_richness"]
                        + w["roc"] * row["f_roc"] + w["cushion"] * row["f_cushion"]
                        + w["assignment"] * row["f_assignment"])
        row["reason"] = reason(row, side)
    rows.sort(key=lambda x: (-x["score"], -x["annualized"]))
    res["candidates"] = [_clean(x) for x in rows[:top_n]]
    return res


def reason(row: dict, side: str) -> str:
    parts = []
    lv, d = row.get("level"), row.get("level_dist_pct")
    if lv and np.isfinite(d):
        label = LEVEL_LABELS.get(lv["kind"], lv["kind"])
        if lv["kind"] == "round":
            label = f"round {lv['value']:g}"
        parts.append(f"{d:.1f}% {'under' if side == 'P' else 'over'} {label}")
    else:
        parts.append("no nearby " + ("support" if side == "P" else "resistance"))
    rp = row.get("iv_resid_pts")
    if rp is not None and np.isfinite(rp):
        parts.append("IV on the skew curve" if abs(rp) < 0.05 else f"IV {abs(rp):.1f} pts {'rich' if rp > 0 else 'cheap'}")
    parts.append(f"{row['annualized'] * 100:.0f}% annualized")
    c = row.get("cushion_moves")
    if c is not None and np.isfinite(c):
        parts.append(f"BE {c:.1f} moves away" if side == "P" else f"{c:.1f} moves OTM")
    return " · ".join(parts)


def _clean(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k == "level":
            out["level"] = None if v is None else {"value": round(v["value"], 2), "kind": v["kind"],
                                                   "label": LEVEL_LABELS.get(v["kind"], v["kind"])}
        elif isinstance(v, float):
            out[k] = round(v, 4) if np.isfinite(v) else None
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------- LEAP

def leap_candidate(opts: pd.DataFrame, price: float, cfg: dict) -> dict | None:
    """12-18 month 70-80 delta call with the lowest extrinsic value as % of price."""
    o = opts[(opts["type"] == "C") & (opts["dte"] >= cfg["min_dte"]) & (opts["dte"] <= cfg["max_dte"])].copy()
    if o.empty:
        return {"found": False, "note": f"no expiries {cfg['min_dte']}-{cfg['max_dte']} DTE"}
    o = o[(o["delta"] * 100 >= cfg["delta_min"]) & (o["delta"] * 100 <= cfg["delta_max"])]
    o = o[(o["bid"] > 0) & (o["ask"] > 0)]
    if o.empty:
        return {"found": False, "note": f"no {cfg['delta_min']}-{cfg['delta_max']} delta calls with a bid"}
    spread = o["ask"] - o["bid"]
    liquid = o[((spread <= cfg["max_spread_pct"] / 100.0 * o["mid"]) | (spread <= cfg["max_spread_abs"]))
               & (o["oi"] >= cfg["min_open_interest"])]
    note = ""
    if liquid.empty:
        liquid, note = o, "wide spreads / thin OI"
    liquid = liquid.assign(intrinsic=np.maximum(price - liquid["strike"], 0.0))
    liquid = liquid.assign(extrinsic=liquid["mid"] - liquid["intrinsic"])
    liquid = liquid.assign(ext_pct=liquid["extrinsic"] / price * 100)
    r = liquid.sort_values(["ext_pct", "dte"]).iloc[0]
    return {
        "found": True, "note": note, "strike": float(r["strike"]), "expiry": r["expiry"].isoformat(),
        "dte": int(r["dte"]), "delta": round(float(r["delta"]), 3), "bid": float(r["bid"]),
        "ask": float(r["ask"]), "mid": round(float(r["mid"]), 2), "iv": round(float(r["iv"]), 4),
        "oi": int(r["oi"]), "extrinsic": round(float(r["extrinsic"]), 2),
        "extrinsic_pct": round(float(r["ext_pct"]), 2), "cost": round(float(r["mid"]) * 100, 0),
        "exposure": round(float(r["delta"]) * price * 100, 0),
        "breakeven": round(float(r["strike"] + r["mid"]), 2),
    }


# ---------------------------------------------------------------- ladder

def ladder(first_strike: float, price: float, iv: float, strikes: list[float], cfg: dict,
           rungs: int = 3, dte: int = 45) -> list[dict]:
    """Rung 1 = the chosen put strike; rungs 2..n = 1..n-1 forty-five-day expected moves below,
    snapped down to a listed strike."""
    em = expected_move(price, iv, dte)
    if not np.isfinite(first_strike):
        return []
    out = [{"rung": 1, "strike": first_strike, "target": first_strike, "collateral": first_strike * 100,
            "moves_below": 0, "listed": True}]
    if not np.isfinite(em):
        return out
    listed = sorted(set(float(s) for s in strikes))
    for i in range(1, rungs):
        tgt = first_strike - i * em
        if tgt <= 0:
            break
        below = [s for s in listed if s <= tgt + 1e-9]
        k = below[-1] if below else round(tgt, 2)
        out.append({"rung": i + 1, "strike": k, "target": round(tgt, 2), "collateral": k * 100, "moves_below": i,
                    "listed": bool(below)})
    for r in out:
        r["em45"] = round(em, 2)
    return out
