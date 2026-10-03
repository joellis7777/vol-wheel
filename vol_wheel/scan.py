"""Daily scan: fetch data, compute signals, pick strikes, write docs/data/latest.json.

    python -m vol_wheel.scan                      # full run (appends IV history)
    python -m vol_wheel.scan --symbols SPY,NVDA --no-append --out /tmp/x.json

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

from . import data, ivhistory, signals, strikes
from .config import ROOT, load_rules, universe

log = logging.getLogger("vol_wheel")

ACTION_PRIORITY = {"SELL_PUT": 0, "SELL_CALL": 1, "LEAP_BUY": 2, "WATCH": 3, "NEUTRAL": 4,
                   "NO_SHORT": 5, "NO_DATA": 6, "ERROR": 7}
ACTION_LABEL = {
    "SELL_PUT": "SELL PUT", "SELL_CALL": "SELL COVERED CALL", "LEAP_BUY": "LEAP BUY",
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
                  gate_on: bool, role: str, rules: dict) -> dict:
    th, lp = rules["thresholds"], rules["leap"]
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
    if not np.isfinite(ivr):
        action = "NO_DATA"
        reasons.append("IV rank unavailable")
    elif ivr >= th["ivr_sell"] and down and (not up or spk["down"] >= spk["up"]):
        action = "SELL_PUT"
        reasons.append(f"IVR {ivr:.0f} ≥ {th['ivr_sell']} and down-spike {spk['down']:.1f}σ")
    elif ivr >= th["ivr_sell"] and up:
        action = "SELL_CALL"
        reasons.append(f"IVR {ivr:.0f} ≥ {th['ivr_sell']} and up-spike {spk['up']:.1f}σ — only if holding shares/LEAPs")
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
    both_sides = bool(action == "SELL_PUT" and regime == "Mid" and ivr >= th["ivr_both_sides"])
    if both_sides:
        reasons.append(f"Mid regime + IVR ≥ {th['ivr_both_sides']}: a {th['both_sides_call_delta']}Δ "
                       "covered call may sit alongside the put")
    if role == "opportunistic" and action in ("WATCH", "NEUTRAL", "NO_SHORT"):
        reasons.append("Opportunistic name: spikes only")
    return {"action": action, "label": ACTION_LABEL[action], "priority": ACTION_PRIORITY[action],
            "reasons": reasons, "both_sides": both_sides, "leap_window": leap_window,
            "leap_checks": leap_checks}


# ---------------------------------------------------------------- per ticker

def scan_ticker(t: dict, rules: dict, gate: dict, index_hists: dict, append: bool = True,
                chain: dict | None = None, hist: pd.DataFrame | None = None) -> dict:
    sym = t["symbol"]
    notes: list[str] = []
    dcfg = rules["data"]
    if chain is None:
        try:
            chain = data.fetch_chain(sym, dcfg)
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
    if append and np.isfinite(iv30):
        ivhistory.append(sym, asof, iv30, price)
    iv_hist = ivhistory.load(sym)
    if not append and np.isfinite(iv30):
        iv_hist = pd.concat([iv_hist[iv_hist.index < pd.Timestamp(asof)],
                             pd.Series([iv30], index=pd.DatetimeIndex([pd.Timestamp(asof)]))])

    idx_sym = rules.get("vol_index_proxy", {}).get(sym)
    ivr = compute_ivr(sym, iv30, iv_hist, close, rules, index_hists.get(idx_sym), idx_sym)

    th, rg, cc = rules["thresholds"], rules["regime"], rules["consolidation"]
    hv20_s = signals.hv(close, th["spike_hv_window"]).dropna()
    hv20 = float(hv20_s.iloc[-1]) if len(hv20_s) else float("nan")
    spk = signals.spike(close, th["spike_max_days"], th["spike_hv_window"])
    ext = signals.extension(close, rg["sma_window"], rg["lookback_days"], rg["min_days"])
    regime = signals.regime(ext["pct"], rg["low_below"], rg["high_above"])
    if not np.isfinite(ext["pct"]):
        notes.append("not enough history for the 200-day extension; regime defaults to Mid")
    cons = signals.consolidation(close, ivr["ivr"], cc["bb_window"], cc["bb_std"], cc["bb_lookback_days"],
                                 cc["bb_pct_max"], cc["ivr_max"])
    rpos = signals.range_position(hist, cc["range_window"])
    dec = decide_action(ivr["ivr"], spk, regime, cons["on"], rpos, gate["on"], t["role"], rules)

    spike_dir, spike_size, spike_k = None, 0.0, None
    if spk["down"] >= spk["up"] and spk["down"] > 0:
        spike_dir, spike_size, spike_k = "down", spk["down"], spk["down_k"]
    elif spk["up"] > 0:
        spike_dir, spike_size, spike_k = "up", spk["up"], spk["up_k"]

    out = {
        "symbol": sym, "bucket": t["bucket"], "role": t["role"], "asof": asof.isoformat(),
        **{k: dec[k] for k in ("action", "label", "priority", "reasons", "both_sides", "leap_window", "leap_checks")},
        "price": price, "prev_close": float(close.iloc[-2]) if len(close) > 1 else None,
        "iv30": iv30, "hv20": hv20, "iv_hv": iv30 / hv20 if np.isfinite(iv30) and hv20 > 0 else None,
        "ivr": ivr["ivr"], "ivr_source": ivr["source"], "iv_history_days": ivr["days"],
        "index_level": ivr.get("index_level"),
        "regime": regime, "extension_pct": ext["pct"], "price_to_sma200": ext["ratio"],
        "spike": {"dir": spike_dir, "size": spike_size, "k": spike_k, "down": spk["down"], "up": spk["up"],
                  "is_spike": spike_size >= th["spike_sigma"]},
        "consolidation": cons["on"], "bb_pct": cons["bb_pct"], "range_pos": rpos,
        "sma50": signals.sma(close, 50), "sma200": signals.sma(close, 200),
        "history_days": len(close), "history_source": hist_src, "notes": notes,
    }
    if out["prev_close"]:
        out["change_pct"] = (price / out["prev_close"] - 1) * 100

    if opts.empty:
        out["notes"].append("no option quotes: strikes, ladder and LEAP skipped")
        return out

    sc = rules["strikes"]
    expiry, dte, exp_note = strikes.choose_expiry(opts, sc)
    out["expiry"], out["dte"], out["expiry_note"] = (expiry.isoformat() if expiry else None), dte, exp_note
    if expiry is None:
        out["notes"].append(f"no usable expiry ({exp_note})")
    else:
        exp_opts = opts[opts["expiry"] == expiry]
        rc = sc["richness"]
        poly = strikes.skew_fit(exp_opts, price, rc.get("fit_delta_min", 5), rc.get("fit_delta_max", 60))
        ac = sc["assignment"]
        recent = hist.iloc[-ac.get("swing_lookback_days", 252):]
        anchors = [signals.sma(close, 200)] + [v for v in signals.swing_points(
            recent["low"], sc["support"].get("swing_order", 5), "low") if v < price]
        base_ctx = {"price": price, "iv30": iv30, "hv20": hv20, "hist": hist, "expiry": expiry, "dte": dte,
                    "poly": poly, "anchors": anchors}
        put_lv = strikes.levels(hist, opts, price, "P", sc)
        call_lv = strikes.levels(hist, opts, price, "C", sc)
        out["supports"] = _levels_out(put_lv)
        out["resistances"] = _levels_out(call_lv)
        out["puts"] = strikes.select_strikes(opts, "P", sc["put_delta"][regime], {**base_ctx, "levels": put_lv}, sc)
        out["calls"] = strikes.select_strikes(opts, "C", sc["call_delta"][regime], {**base_ctx, "levels": call_lv}, sc)
        if dec["both_sides"]:
            out["pair_call"] = strikes.select_strikes(opts, "C", th["both_sides_call_delta"],
                                                      {**base_ctx, "levels": call_lv}, sc, top_n=1)
        em_iv = iv30
        if sym in rules.get("weekend_gap_names", []) and np.isfinite(hv20):
            em_iv = np.nanmax([iv30, hv20])
        out["em45"] = strikes.expected_move(price, em_iv, rules["sizing"]["ladder_dte"])
        if out["puts"]["candidates"]:
            put_strikes = opts[(opts["type"] == "P") & (opts["expiry"] == expiry)]["strike"].tolist()
            out["ladder"] = strikes.ladder(out["puts"]["candidates"][0]["strike"], price, em_iv, put_strikes,
                                           sc, rules["sizing"]["ladder_rungs"], rules["sizing"]["ladder_dte"])
        if sym in rules.get("momentum_names", []):
            out["notes"].append(f"Momentum name: cover at most {rules['momentum_max_call_coverage']}% with calls")
    out["leap"] = strikes.leap_candidate(opts, price, rules["leap"])
    return out


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


def run(rules: dict, symbols: list[str] | None = None, append: bool = True) -> dict:
    started = datetime.now(timezone.utc)
    notes: list[str] = []
    uni = universe(rules)
    if symbols:
        uni = [t for t in uni if t["symbol"] in symbols]

    # Bull gate needs SPY history even if SPY is filtered out.
    spy_close = None
    try:
        spy_hist, _, _ = data.fetch_history("SPY", rules["data"])
        try:
            spy_chain = data.fetch_chain("SPY", rules["data"])
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
            r = scan_ticker(t, rules, gate, index_hists, append=append)
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
    errs = [r["symbol"] for r in results if r["action"] == "ERROR"]
    if errs:
        notes.append(f"Failed: {', '.join(errs)}")
    for r in results:
        for nn in r.get("notes", []):
            if any(w in nn for w in ("unavailable", "failed", "short", "missing")):
                notes.append(f"{r['symbol']}: {nn}")
    notes.append("Quotes are CBOE delayed (~15 min) end-of-day snapshots")

    buckets = [{"name": b, "cap": s["cap"], "core": s.get("core") or [], "opportunistic": s.get("opportunistic") or []}
               for b, s in rules["universe"].items()]
    return clean({
        "generated_at": started.isoformat(timespec="seconds"),
        "scan_date": max((r.get("asof") or "" for r in results), default=date.today().isoformat()),
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
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rules = load_rules(a.rules)
    syms = [s.strip().upper() for s in a.symbols.split(",")] if a.symbols else None
    result = run(rules, syms, append=not a.no_append)
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
    # Fail the job only if nothing at all came back.
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
