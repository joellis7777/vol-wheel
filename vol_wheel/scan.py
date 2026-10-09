"""Daily scan: fetch data, compute signals, pick strikes, write docs/data/latest.json.

    python -m vol_wheel.scan                      # mode from the ET clock (post-close appends IV history)
    python -m vol_wheel.scan --mode intraday      # update latest.json + alerts only
    python -m vol_wheel.scan --mode auto --schedule "30 14 * * 1-5"   # what the workflow runs
    python -m vol_wheel.scan --symbols SPY,NVDA --no-append --no-alerts --out /tmp/x.json

One ticker failing never fails the run; it shows up as an ERROR card with a note.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import alerts, data, earnings, ivhistory, schedule, signals, strikes
from .config import ROOT, load_rules, universe

log = logging.getLogger("vol_wheel")

ACTION_PRIORITY = {"SELL_PUT": 0, "SELL_CALL": 1, "EARNINGS_PLAY": 2, "LEAP_BUY": 3, "WATCH": 4,
                   "NEUTRAL": 5, "NO_SHORT": 6, "NO_DATA": 7, "ERROR": 8}
ACTION_LABEL = {
    "SELL_PUT": "SELL PUT", "SELL_CALL": "SELL COVERED CALL", "EARNINGS_PLAY": "EARNINGS PLAY",
    "LEAP_BUY": "LEAP BUY",
    "WATCH": "WATCH", "NEUTRAL": "WAIT", "NO_SHORT": "NO NEW SHORTS", "NO_DATA": "NO DATA",
    "ERROR": "ERROR",
}


# ---------------------------------------------------------------- IV rank

def compute_ivr(sym: str, iv30: float, iv_hist: pd.Series, close: pd.Series, rules: dict,
                index_hist: pd.Series | None = None, index_sym: str | None = None) -> dict:
    """True IVR from our own iv30 history once long enough; else VIX/VXN for index ETFs;
    else the realized-vol percentile proxy."""
    c = rules["iv_rank"]
    h = iv_hist.dropna().iloc[-c["lookback_days"]:]
    n = len(h)
    if n >= c["min_history_days"] and np.isfinite(iv30):
        label = "true" if n >= c["full_history_days"] else "partial"
        return {"ivr": signals.iv_rank(iv30, h), "source": label, "days": n}
    if index_hist is not None and len(index_hist) >= 60:
        ih = index_hist.dropna().iloc[-c["lookback_days"]:]
        return {"ivr": signals.iv_rank(float(ih.iloc[-1]), ih), "source": index_sym.lstrip("_"),
                "days": n, "index_level": float(ih.iloc[-1])}
    return {"ivr": signals.proxy_ivr(close, c["proxy_hv_window"], c["lookback_days"]), "source": "proxy",
            "days": n}


def atm_iv(opts: pd.DataFrame, price: float) -> float:
    """Fallback iv30: mean IV of the two strikes nearest the money at the expiry nearest 30 DTE."""
    o = opts[(opts["iv"] > 0) & (opts["dte"] >= 7)]
    if o.empty:
        return float("nan")
    e = (o.groupby("expiry")["dte"].first() - 30).abs().idxmin()
    x = o[o["expiry"] == e].assign(dist=lambda d: (d["strike"] - price).abs()).nsmallest(4, "dist")
    return float(x["iv"].mean())


# ---------------------------------------------------------------- action

def decide_action(ivr: float, spk: dict, regime: str, cons_on: bool, range_pos: float,
                  gate_on: bool, role: str, rules: dict, iv_hv: float | None = None,
                  earn: dict | None = None) -> dict:
    """earn: {"in_window": earnings before the chosen expiry, "inflated": IVR can't be stripped of
    the earnings bump, "date", "days_to", "play": {"side", "ret", "z"} | None}."""
    th, lp = rules["thresholds"], rules["leap"]
    earn = earn or {}
    sig = th["spike_sigma"]
    down, up = spk.get("down", 0.0) >= sig, spk.get("up", 0.0) >= sig
    leap_checks = {
        "bull_gate": bool(gate_on),
        "regime": regime in lp["regimes"],
        "consolidation": bool(cons_on),
        "bottom_third": bool(np.isfinite(range_pos) and range_pos <= lp["range_pos_max"]),
        "ivr_low": bool(np.isfinite(ivr) and ivr < lp["ivr_max"]),
        "core_name": role == "core" or not lp.get("core_only", True),
    }
    leap_window = all(leap_checks.values())
    reasons: list[str] = []
    min_ratio = th.get("min_iv_hv_ratio", 0)
    ratio_ok = iv_hv is None or not np.isfinite(iv_hv) or iv_hv >= min_ratio
    gap = spk.get("earnings_gap")
    if gap:
        reasons.append(f"Post-earnings gap {gap['move'] * 100:+.1f}% = {gap['ratio']:.1f}× the implied "
                       f"{gap['implied_move'] * 100:.1f}% move (counts as a spike)")
    play = earn.get("play")
    if not np.isfinite(ivr):
        action = "NO_DATA"
        reasons.append("IV rank unavailable")
    elif play:
        action = "EARNINGS_PLAY"
        side = "call after a run-up" if play["side"] == "C" else "put after a sell-off"
        ec = rules["earnings"]
        reasons.append(f"Earnings {earn.get('date')} in {earn.get('days_to')}d · 5-day {play['ret'] * 100:+.1f}% "
                       f"({play['z']:+.1f}σ): sell a {side} at {ec['play_delta_min']}–{ec['play_delta_max']}Δ, "
                       f"outside {ec['play_move_mult']}× the implied move, half size")
    elif ivr >= th["ivr_sell"] and (down or up):
        is_put = down and (not up or spk["down"] >= spk["up"])
        what = f"{'down' if is_put else 'up'}-spike {spk['down' if is_put else 'up']:.1f}σ"
        if earn.get("in_window") or earn.get("inflated"):
            action = "WATCH"
            reasons.append(f"IVR {ivr:.0f} and {what}, but earnings {earn.get('date')} fall before expiry: "
                           "normal entries paused (earnings mode)")
        elif not ratio_ok:
            action = "WATCH"
            reasons.append(f"IVR {ivr:.0f} and {what}, but IV/HV {iv_hv:.2f} < {min_ratio}: "
                           "premium not rich versus realized moves")
        else:
            action = "SELL_PUT" if is_put else "SELL_CALL"
            ratio_txt = f", IV/HV {iv_hv:.2f}" if iv_hv is not None and np.isfinite(iv_hv) else ""
            reasons.append(f"IVR {ivr:.0f} ≥ {th['ivr_sell']}, {what}{ratio_txt}"
                           + ("" if is_put else " — only if holding shares/LEAPs"))
    elif ivr >= th["ivr_sell"]:
        action = "WATCH"
        reasons.append(f"IVR {ivr:.0f} ≥ {th['ivr_sell']}, no {sig}σ spike yet")
    elif leap_window:
        action = "LEAP_BUY"
        reasons.append("Bull gate on, quiet consolidation at the bottom of the range, IVR "
                       f"{ivr:.0f} < {lp['ivr_max']}")
    elif ivr < th["ivr_no_short"]:
        action = "NO_SHORT"
        reasons.append(f"IVR {ivr:.0f} < {th['ivr_no_short']}: no new short premium")
    else:
        action = "NEUTRAL"
        reasons.append(f"IVR {ivr:.0f} between {th['ivr_no_short']} and {th['ivr_sell']}: wait")
    if earn.get("inflated"):
        reasons.append("IVR earnings-inflated (ex-earnings IV not estimable): normal signals off")
    both_sides = bool(action == "SELL_PUT" and regime == "Mid" and ivr >= th["ivr_both_sides"])
    if both_sides:
        reasons.append(f"Mid regime + IVR ≥ {th['ivr_both_sides']}: a {th['both_sides_call_delta']}Δ "
                       "covered call may sit alongside the put")
    if role == "opportunistic" and action in ("WATCH", "NEUTRAL", "NO_SHORT"):
        reasons.append("Opportunistic name: spikes only")
    return {"action": action, "label": ACTION_LABEL[action], "priority": ACTION_PRIORITY[action],
            "reasons": reasons, "both_sides": both_sides, "leap_window": leap_window,
            "leap_checks": leap_checks}


def earnings_play_setup(ectx: dict, close: pd.Series, iv30: float, hv20: float, rules: dict) -> dict | None:
    """Directional pre-earnings sale: earnings 1-21 days out and before expiry, an implied move to
    stay outside of, raw IV rich versus realized, and a 5-day run-up (call) or sell-off (put)."""
    ec, th = rules["earnings"], rules["thresholds"]
    if not ectx.get("in_window") or ectx.get("days_to") is None:
        return None
    if not (ec["play_min_days"] <= ectx["days_to"] <= ec["play_max_days"]):
        return None
    move = earnings.move_for_strikes(ectx.get("implied") or {})
    if not move:
        return None
    if not (np.isfinite(iv30) and np.isfinite(hv20) and hv20 > 0 and iv30 / hv20 >= th.get("min_iv_hv_ratio", 0)):
        return None
    tr = earnings.trend(close, ec.get("trend_days", 5), hv20)
    if tr["z"] is None or abs(tr["z"]) < ec.get("trend_sigma", 1.0):
        return None
    return {"side": "C" if tr["z"] > 0 else "P", "ret": tr["ret"], "z": tr["z"], "move": move}


# ---------------------------------------------------------------- per ticker

def scan_ticker(t: dict, rules: dict, gate: dict, index_hists: dict, append: bool = True,
                chain: dict | None = None, hist: pd.DataFrame | None = None,
                earn_cache: dict | None = None, today: date | None = None) -> dict:
    sym = t["symbol"]
    notes: list[str] = []
    dcfg = rules["data"]
    if chain is None:
        try:
            chain = data.fetch_chain(sym, dcfg, asof=today)
        except Exception as e:  # noqa: BLE001
            notes.append(f"option chain unavailable: {e}")
            chain = None
    hist_src = "fixture"
    if hist is None:
        hist, hist_src, hn = data.fetch_history(sym, dcfg)
        notes += hn
    hist = data.with_today(hist, chain)
    close = hist["close"]
    opts = chain["options"] if chain else pd.DataFrame()
    price = chain["price"] if chain and np.isfinite(chain["price"]) else float(close.iloc[-1])
    asof = data.market_date(chain["asof"]) if chain else hist.index[-1].date()

    iv30 = chain["iv30"] if chain else float("nan")
    if chain and not np.isfinite(iv30) and not opts.empty:
        iv30 = atm_iv(opts, price)
        if np.isfinite(iv30):
            notes.append("iv30 missing; using ATM IV of the ~30 DTE expiry")

    th, rg, cc, sc = rules["thresholds"], rules["regime"], rules["consolidation"], rules["strikes"]
    hv20_s = signals.hv(close, th["spike_hv_window"]).dropna()
    hv20 = float(hv20_s.iloc[-1]) if len(hv20_s) else float("nan")

    expiry, dte, exp_note = (strikes.choose_expiry(opts, sc) if not opts.empty else (None, None, "no chain"))

    # Earnings mode: strip the earnings bump from iv30 when the report is inside the IV window.
    ec = rules.get("earnings", {})
    ectx = earnings.earnings_context(sym, earn_cache or {}, opts, price, iv30, asof, expiry, ec)
    iv_eff, iv30_ex, inflated = iv30, None, False
    im = ectx.get("implied") or {}
    if ectx.get("in_iv_window"):
        if im.get("feasible") and im.get("iv30_ex"):
            iv30_ex = im["iv30_ex"]
            iv_eff = iv30_ex
        else:
            inflated = True
    if earn_cache is not None and ectx.get("next") and earnings.move_for_strikes(im):
        earn_cache.setdefault(sym, {})["implied_move"] = earnings.move_for_strikes(im)

    # Earnings before the usual expiry: trade the latest expiry that ends before the report when
    # one exists (normal signals); otherwise the trade would span earnings and normal entries pause.
    trade_exp, trade_dte, trade_note, pre = expiry, dte, exp_note, None
    nxt = ectx.get("next") or {}
    if ectx.get("in_window") and expiry is not None:
        pre = earnings.pre_earnings_expiry(opts, date.fromisoformat(nxt["date"]), nxt.get("timing"), asof, ec)
        if pre:
            trade_exp, trade_dte = pre
            trade_note = f"ends before earnings {nxt['date']}; the usual {expiry.isoformat()} expiry spans them"
    spans = bool(ectx.get("in_window")) and pre is None

    if append and np.isfinite(iv30):
        ivhistory.append(sym, asof, iv30, price, iv30_ex=iv30_ex)
    iv_hist = ivhistory.load(sym)
    if not append and np.isfinite(iv_eff):
        iv_hist = pd.concat([iv_hist[iv_hist.index < pd.Timestamp(asof)],
                             pd.Series([iv_eff], index=pd.DatetimeIndex([pd.Timestamp(asof)]))])

    idx_sym = rules.get("vol_index_proxy", {}).get(sym)
    ivr = compute_ivr(sym, iv_eff, iv_hist, close, rules, index_hists.get(idx_sym), idx_sym)

    spk = signals.spike(close, th["spike_max_days"], th["spike_hv_window"])
    gap = earnings.post_gap(close, ectx.get("last"), asof, ec, th["spike_max_days"]) if ectx.get("applies") else None
    if gap:
        spk[gap["dir"]] = max(spk[gap["dir"]], th["spike_sigma"])
        spk[f"{gap['dir']}_k"] = spk.get(f"{gap['dir']}_k") or 1
        spk["earnings_gap"] = gap
    ext = signals.extension(close, rg["sma_window"], rg["lookback_days"], rg["min_days"])
    regime = signals.regime(ext["pct"], rg["low_below"], rg["high_above"])
    if not np.isfinite(ext["pct"]):
        notes.append("not enough history for the 200-day extension; regime defaults to Mid")
    cons = signals.consolidation(close, ivr["ivr"], cc["bb_window"], cc["bb_std"], cc["bb_lookback_days"],
                                 cc["bb_pct_max"], cc["ivr_max"])
    rpos = signals.range_position(hist, cc["range_window"])
    iv_hv = iv_eff / hv20 if np.isfinite(iv_eff) and hv20 > 0 else None
    play = earnings_play_setup(ectx, close, iv30, hv20, rules) if ectx.get("applies") else None
    earn_flags = {"in_window": spans, "inflated": inflated, "date": nxt.get("date"),
                  "days_to": ectx.get("days_to"), "play": play}
    dec = decide_action(ivr["ivr"], spk, regime, cons["on"], rpos, gate["on"], t["role"], rules, iv_hv, earn_flags)
    if pre and dec["action"] in ("SELL_PUT", "SELL_CALL"):
        dec["reasons"].append(f"Using the {trade_exp.isoformat()} expiry ({trade_dte} DTE), which ends before "
                              f"earnings {nxt['date']}")
    elif spans and dec["action"] == "WATCH" and any("earnings mode" in r for r in dec["reasons"]):
        dec["reasons"].append(f"No expiry of {ec.get('pre_earnings_expiry', {}).get('min_dte', 21)}+ DTE ends "
                              "before the report")

    spike_dir, spike_size, spike_k = None, 0.0, None
    if spk["down"] >= spk["up"] and spk["down"] > 0:
        spike_dir, spike_size, spike_k = "down", spk["down"], spk["down_k"]
    elif spk["up"] > 0:
        spike_dir, spike_size, spike_k = "up", spk["up"], spk["up_k"]

    stripped = iv30_ex is not None and np.isfinite(iv30) and iv30_ex < iv30 - 0.0005
    ivr_flag = "earnings-inflated" if inflated else ("ex-earnings" if stripped else None)
    out = {
        "symbol": sym, "bucket": t["bucket"], "role": t["role"], "asof": asof.isoformat(),
        **{k: dec[k] for k in ("action", "label", "priority", "reasons", "both_sides", "leap_window", "leap_checks")},
        "price": price, "prev_close": float(close.iloc[-2]) if len(close) > 1 else None,
        "iv30": iv30, "iv30_ex": iv30_ex, "hv20": hv20, "iv_hv": iv_hv,
        "iv_hv_min": th.get("min_iv_hv_ratio"), "iv_hv_ok": iv_hv is None or iv_hv >= th.get("min_iv_hv_ratio", 0),
        "ivr": ivr["ivr"], "ivr_source": ivr["source"], "ivr_flag": ivr_flag, "iv_history_days": ivr["days"],
        "index_level": ivr.get("index_level"),
        "regime": regime, "extension_pct": ext["pct"], "price_to_sma200": ext["ratio"],
        "spike": {"dir": spike_dir, "size": spike_size, "k": spike_k, "down": spk["down"], "up": spk["up"],
                  "is_spike": spike_size >= th["spike_sigma"], "earnings_gap": gap},
        "consolidation": cons["on"], "bb_pct": cons["bb_pct"], "range_pos": rpos,
        "sma50": signals.sma(close, 50), "sma200": signals.sma(close, 200),
        "earnings": _earnings_out(ectx, play, pre, spans),
        "history_days": len(close), "history_source": hist_src, "notes": notes,
    }
    if out["prev_close"]:
        out["change_pct"] = (price / out["prev_close"] - 1) * 100
    if pre and out["earnings"] and out["earnings"].get("pre_expiry"):
        out["earnings"]["pre_expiry"]["take_profit_pct"] = ec.get("pre_earnings_expiry", {}).get("take_profit_pct", 50)

    if opts.empty:
        out["notes"].append("no option quotes: strikes, ladder and LEAP skipped")
        return out

    out["expiry"], out["dte"], out["expiry_note"] = (trade_exp.isoformat() if trade_exp else None), trade_dte, trade_note
    if trade_exp is None:
        out["notes"].append(f"no usable expiry ({exp_note})")
    else:
        rc = sc["richness"]

        def fit(e):
            return strikes.skew_fit(opts[opts["expiry"] == e], price, rc.get("fit_delta_min", 5), rc.get("fit_delta_max", 60))
        poly = fit(trade_exp)
        ac = sc["assignment"]
        recent = hist.iloc[-ac.get("swing_lookback_days", 252):]
        anchors = [signals.sma(close, 200)] + [v for v in signals.swing_points(
            recent["low"], sc["support"].get("swing_order", 5), "low") if v < price]
        base_ctx = {"price": price, "iv30": iv_eff, "hv20": hv20, "hist": hist, "expiry": trade_exp,
                    "dte": trade_dte, "poly": poly, "anchors": anchors}
        # Earnings plays sell through the report, so they always use the usual (spanning) expiry.
        play_ctx = base_ctx if trade_exp == expiry else {**base_ctx, "expiry": expiry, "dte": dte, "poly": fit(expiry)}
        put_lv = strikes.levels(hist, opts, price, "P", sc)
        call_lv = strikes.levels(hist, opts, price, "C", sc)
        out["supports"] = _levels_out(put_lv)
        out["resistances"] = _levels_out(call_lv)
        out["puts"] = strikes.select_strikes(opts, "P", sc["put_delta"][regime], {**base_ctx, "levels": put_lv}, sc)
        out["calls"] = strikes.select_strikes(opts, "C", sc["call_delta"][regime], {**base_ctx, "levels": call_lv}, sc)
        if dec["both_sides"]:
            out["pair_call"] = strikes.select_strikes(opts, "C", th["both_sides_call_delta"],
                                                      {**base_ctx, "levels": call_lv}, sc, top_n=1)
        move = earnings.move_for_strikes(im) if ectx.get("in_window") else None
        if move:
            lo, hi, mult = ec["play_delta_min"], ec["play_delta_max"], ec["play_move_mult"]
            ep = {"move": move, "move_usd": move * price, "mult": mult, "band": [lo, hi],
                  "size_frac": ec.get("play_size_frac", 0.5), "side": play["side"] if play else None}
            for side, key, lv in (("P", "puts", put_lv), ("C", "calls", call_lv)):
                lim = price * (1 - mult * move) if side == "P" else price * (1 + mult * move)
                ep[key] = strikes.select_strikes(opts, side, (lo + hi) / 2,
                                                 {**play_ctx, "levels": lv, "band": (lo, hi), "strike_limit": lim}, sc)
            out["earnings_play"] = ep
        em_iv = iv_eff
        if sym in rules.get("weekend_gap_names", []) and np.isfinite(hv20):
            em_iv = np.nanmax([iv_eff, hv20])
        out["em45"] = strikes.expected_move(price, em_iv, rules["sizing"]["ladder_dte"])
        if out["puts"]["candidates"]:
            put_strikes = opts[(opts["type"] == "P") & (opts["expiry"] == trade_exp)]["strike"].tolist()
            out["ladder"] = strikes.ladder(out["puts"]["candidates"][0]["strike"], price, em_iv, put_strikes,
                                           sc, rules["sizing"]["ladder_rungs"], rules["sizing"]["ladder_dte"])
        if sym in rules.get("momentum_names", []):
            out["notes"].append(f"Momentum name: cover at most {rules['momentum_max_call_coverage']}% with calls")
    lp = rules["leap"]
    variants = lp.get("variants") or {"ira": {"min_dte": lp["min_dte"], "max_dte": lp["max_dte"], "label": "LEAP"}}
    out["leaps"] = {}
    for name, v in variants.items():
        cand = strikes.leap_candidate(opts, price, {**lp, "min_dte": v["min_dte"], "max_dte": v["max_dte"]})
        if not cand.get("found") and v.get("fallback_max_dte"):
            # LEAP expiries are sparse (Jan, plus a few Mar/Jun/Dec); take the nearest one past the
            # window rather than nothing, and say so.
            alt = strikes.leap_candidate(opts, price, {**lp, "min_dte": v["min_dte"], "max_dte": v["fallback_max_dte"]})
            if alt.get("found"):
                months = alt["dte"] / 30.44
                alt["note"] = (f"no listed expiry {v['min_dte'] / 30.44:.0f}–{v['max_dte'] / 30.44:.0f} months out; "
                               f"nearest is {months:.0f} months" + (f" · {alt['note']}" if alt.get("note") else ""))
                alt["outside_window"] = True
                cand = alt
        out["leaps"][name] = {**cand, "label": v.get("label", name), "variant_note": v.get("note", "")}
    out["leap"] = out["leaps"].get("ira") or next(iter(out["leaps"].values()))
    if rules.get("hedge_alerts") and sym in rules.get("hedge", {}).get("symbols", []):
        out["hedge_puts"] = strikes.hedge_puts(opts, price, rules["hedge"])
    return out


def _earnings_out(ectx: dict, play: dict | None, pre: tuple | None = None, spans: bool = False) -> dict | None:
    if not ectx.get("applies"):
        return None
    im = ectx.get("implied") or {}
    nxt = ectx.get("next") or {}
    return {"date": nxt.get("date"), "timing": nxt.get("timing"), "estimated": nxt.get("estimated"),
            "pre_expiry": {"expiry": pre[0].isoformat(), "dte": pre[1]} if pre else None, "spans_trade": spans,
            "source": nxt.get("source"), "days_to": ectx.get("days_to"), "in_window": ectx.get("in_window"),
            "in_iv_window": ectx.get("in_iv_window"), "implied_move": earnings.move_for_strikes(im),
            "implied_feasible": im.get("feasible"), "implied_why": im.get("why"), "iv30_ex": im.get("iv30_ex"),
            "last": ectx.get("last"), "play": play}


def _levels_out(lv: list[dict]) -> list[dict]:
    return [{"value": round(x["value"], 2), "kind": x["kind"],
             "label": strikes.LEVEL_LABELS.get(x["kind"], x["kind"])} for x in sorted(lv, key=lambda x: x["value"])]


# ---------------------------------------------------------------- run

def clean(o):
    """Make JSON-safe: NaN/inf -> None, numpy -> python, round floats."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return round(f, 4) if math.isfinite(f) else None
    if isinstance(o, (date, pd.Timestamp)):
        return o.isoformat()
    return o


def load_index_hists(rules: dict) -> tuple[dict, list[str]]:
    out, notes = {}, []
    for idx in sorted(set(rules.get("vol_index_proxy", {}).values())):
        try:
            h, src, n = data.fetch_history(idx, {**rules["data"], "history_min_days": 200})
            out[idx] = h["close"]
            notes += [f"{idx}: {x}" for x in n]
        except Exception as e:  # noqa: BLE001
            notes.append(f"{idx} history unavailable ({e}); index ETFs use the HV proxy")
    return out, notes


def coverage(rules: dict, results: list[dict], symbols: list[str] | None = None) -> dict:
    """Check that every universe ticker made it into the output, and why any failed."""
    expected = [t["symbol"] for t in universe(rules) if not symbols or t["symbol"] in symbols]
    present = {r["symbol"] for r in results}
    failed = {r["symbol"]: (r.get("reasons") or ["unknown"])[0] for r in results
              if r["action"] in ("ERROR", "NO_DATA")}
    no_chain = sorted(r["symbol"] for r in results
                      if any("option chain unavailable" in n or "no option quotes" in n for n in r.get("notes", [])))
    return {"expected": len(expected), "present": len(present & set(expected)),
            "missing": [s for s in expected if s not in present], "failed": failed, "no_chain": no_chain}


def hedge_card(rules: dict, results: list[dict], index_hists: dict, spy_regime: dict | None) -> dict | None:
    """Optional far-OTM SPY/QQQ put suggestion when VIX is low and SPY is extended."""
    if not rules.get("hedge_alerts"):
        return None
    hc = rules["hedge"]
    vix_s = index_hists.get("_VIX")
    vix = float(vix_s.iloc[-1]) if vix_s is not None and len(vix_s) else None
    reg = (spy_regime or {}).get("regime")
    conds = {"vix_low": vix is not None and vix < hc["vix_max"], "spy_regime": reg == hc["spy_regime"]}
    cands = {r["symbol"]: r["hedge_puts"] for r in results if r.get("hedge_puts")}
    return {"enabled": True, "active": all(conds.values()), "vix": vix, "vix_max": hc["vix_max"],
            "spy_regime": reg, "conditions": conds, "candidates": cands,
            "dte": [hc["min_dte"], hc["max_dte"]], "otm_pcts": hc["otm_pcts"]}


def run(rules: dict, symbols: list[str] | None = None, append: bool = True, mode: str = "close",
        slot: str | None = None, today: date | None = None, persist: bool = True) -> dict:
    started = datetime.now(timezone.utc)
    today = today or data.session_date(None, rules.get("schedule", {}).get("timezone", "America/New_York"),
                                       rules.get("schedule", {}).get("market_open", "09:30"))
    notes: list[str] = []
    uni = universe(rules)
    if symbols:
        uni = [t for t in uni if t["symbol"] in symbols]
    ec = rules.get("earnings", {})
    stocks = [t["symbol"] for t in uni if t["symbol"] not in ec.get("etfs", [])]
    try:
        earn_cache, en = earnings.refresh(stocks, today, ec)
        notes += en
    except Exception as e:  # noqa: BLE001 - earnings are optional context
        earn_cache = {}
        notes.append(f"earnings dates unavailable ({e})")

    # Bull gate needs SPY history even if SPY is filtered out.
    spy_close = None
    try:
        spy_hist, _, _ = data.fetch_history("SPY", rules["data"])
        try:
            spy_chain = data.fetch_chain("SPY", rules["data"], asof=today)
            spy_hist = data.with_today(spy_hist, spy_chain)
        except Exception:  # noqa: BLE001
            pass
        spy_close = spy_hist["close"]
    except Exception as e:  # noqa: BLE001
        notes.append(f"SPY history unavailable ({e}); bull gate off")
    gate = signals.bull_gate(rules.get("bull_mode", False), spy_close if spy_close is not None else pd.Series(dtype=float))
    spy_regime = None
    if spy_close is not None:
        ext = signals.extension(spy_close, rules["regime"]["sma_window"], rules["regime"]["lookback_days"])
        spy_regime = {"regime": signals.regime(ext["pct"], rules["regime"]["low_below"], rules["regime"]["high_above"]),
                      "extension_pct": ext["pct"]}

    index_hists, n = load_index_hists(rules)
    notes += n

    results = []
    for t in uni:
        log.info("scanning %s", t["symbol"])
        try:
            r = scan_ticker(t, rules, gate, index_hists, append=append, earn_cache=earn_cache, today=today)
        except Exception as e:  # noqa: BLE001
            log.error("%s failed: %s\n%s", t["symbol"], e, traceback.format_exc())
            r = {"symbol": t["symbol"], "bucket": t["bucket"], "role": t["role"], "action": "ERROR",
                 "label": "ERROR", "priority": ACTION_PRIORITY["ERROR"], "reasons": [str(e)[:200]],
                 "notes": [f"scan failed: {str(e)[:200]}"]}
        results.append(r)

    results.sort(key=lambda r: (r["priority"], -(r.get("spike") or {}).get("size", 0) or 0,
                                -(r.get("ivr") if r.get("ivr") is not None and np.isfinite(r.get("ivr")) else -1)))

    srcs = [r.get("ivr_source") for r in results]
    proxies = [r["symbol"] for r in results if r.get("ivr_source") == "proxy"]
    if proxies:
        notes.append(f"IVR is a realized-vol proxy for {len(proxies)} names until "
                     f"{rules['iv_rank']['min_history_days']} days of IV history are stored")
    partial = [r["symbol"] for r in results if r.get("ivr_source") == "partial"]
    if partial:
        notes.append(f"IVR uses partial (<{rules['iv_rank']['full_history_days']}d) IV history for {', '.join(partial)}")
    cov = coverage(rules, results, symbols)
    if cov["missing"]:
        notes.append(f"Missing from output: {', '.join(cov['missing'])}")
    for sym, why in cov["failed"].items():
        notes.append(f"Failed: {sym} ({why})")
    for r in results:
        if r["action"] == "ERROR":
            continue  # already reported as "Failed: SYM (reason)"
        for nn in r.get("notes", []):
            if any(w in nn for w in ("unavailable", "failed", "short", "missing")):
                notes.append(f"{r['symbol']}: {nn}")
    notes.append("Quotes are CBOE delayed (~15 min) " + ("intraday snapshots; IV history is only "
                 "appended after the close" if mode == "intraday" else "end-of-day snapshots"))

    if persist:
        try:
            earnings.save_cache(earn_cache, ec)
        except OSError as e:
            notes.append(f"earnings cache not written: {e}")
    hedge = hedge_card(rules, results, index_hists, spy_regime)
    for r in results:
        r.pop("hedge_puts", None)
    buckets = [{"name": b, "cap": s["cap"], "core": s.get("core") or [], "opportunistic": s.get("opportunistic") or []}
               for b, s in rules["universe"].items()]
    return clean({
        "generated_at": started.isoformat(timespec="seconds"),
        "scan_mode": mode, "scan_slot": slot, "coverage": cov, "session_date": today.isoformat(),
        "hedge": hedge, "earnings_cfg": {k: ec.get(k) for k in ("play_delta_min", "play_delta_max", "play_move_mult",
                                                                  "play_size_frac")},
        "scan_date": today.isoformat(),
        "bull_gate": gate, "spy_regime": spy_regime, "notes": notes,
        "ivr_sources": {s: srcs.count(s) for s in set(srcs) if s},
        "sizing": rules["sizing"], "buckets": buckets, "total_deployed_cap": rules["total_deployed_cap"],
        "per_name_cap": rules.get("per_name_cap"), "per_name_cap_index": rules.get("per_name_cap_index"),
        "momentum_names": rules.get("momentum_names", []),
        "thresholds": rules["thresholds"],
        "tickers": results,
    })


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rules", default=None)
    ap.add_argument("--out", default=str(ROOT / "docs" / "data" / "latest.json"))
    ap.add_argument("--symbols", default=None, help="comma-separated subset")
    ap.add_argument("--no-append", action="store_true", help="don't write IV history")
    ap.add_argument("--mode", default="auto", choices=["auto", "close", "intraday"],
                    help="close appends IV history; intraday only updates latest.json and alerts")
    ap.add_argument("--schedule", default="", help="cron string of the scheduled run (github.event.schedule)")
    ap.add_argument("--no-alerts", action="store_true", help="don't send ntfy alerts")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rules = load_rules(a.rules)
    syms = [s.strip().upper() for s in a.symbols.split(",")] if a.symbols else None
    m = schedule.resolve_mode(a.mode, a.schedule or None, None, rules.get("schedule", {}))
    log.info("mode %s (%s, %s ET)", m["mode"], m["reason"], m["et"])
    if m["mode"] == "skip":
        return 0
    result = run(rules, syms, append=(m["mode"] == "close" and not a.no_append), mode=m["mode"], slot=m["slot"])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(result, f, indent=1, allow_nan=False)
    ok = sum(1 for r in result["tickers"] if r["action"] not in ("ERROR",))
    log.info("wrote %s: %d/%d tickers ok", a.out, ok, len(result["tickers"]))
    for r in result["tickers"]:
        log.info("  %-5s %-18s IVR %s (%s) regime %s", r["symbol"], r["label"],
                 r.get("ivr"), r.get("ivr_source"), r.get("regime"))
    for nn in result["notes"]:
        log.info("note: %s", nn)
    cov = result["coverage"]
    log.info("coverage: %d/%d universe tickers present; missing %s; failed %s; no chain %s",
             cov["present"], cov["expected"], cov["missing"] or "none", cov["failed"] or "none",
             cov["no_chain"] or "none")
    if not a.no_alerts:
        try:
            summary = alerts.process(result, m["mode"], rules)
            log.info("alerts: %s", summary)
        except Exception as e:  # noqa: BLE001 - alerting must never fail the scan
            log.error("alerts failed: %s\n%s", e, traceback.format_exc())
    # Fail the job only if nothing at all came back.
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
