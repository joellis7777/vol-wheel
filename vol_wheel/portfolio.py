"""Portfolio layer for the dashboard and alerts (docs/STRATEGY.md): the core pyramid, the stock-picks
watchlist and the bitcoin readiness warning. Signals only: nothing here knows what Jordan holds.

Core cycle (`portfolio.core`): each name's sleeve = budget_pct x weight of the account. Its invested
target = interpolation of `alloc` [[drawdown % from the all-time high, % of the sleeve]] at today's
drawdown, capped by `alloc_gain` [[gain % from the 3-year low, max %]] as a bull run matures (scale out
into strength; Jordan 2026-10-11). Steps are the alloc points past the first; the step index (how many step levels the drawdown has
reached) is what alerts compare: deeper = ADD, shallower = TRIM. There is no trend exit (Jordan,
2026-10-11); each name's trend state is shown for information. `history_symbol` measures the drawdown on
a longer history (IBIT launched 2024; BTC-USD stands in) and converts step prices back to the ETF.

Picks (`picks.watchlist`, `picks.rules`): entry needs a full trend state (above a rising 200-day) and a
relative-strength score (average of the 6- and 12-month return ratio vs `rs_benchmark`) in the top
`rs_top_frac` of the watchlist. A pick in the "out" state, or more than `trailing_stop_pct` below its
1-year high, shows EXIT IF HELD (the stop is measured from the 1-year high because positions aren't known).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .backtest import trend_states

log = logging.getLogger(__name__)
TD = 252


def alloc_target(dd_pct: float, alloc: list) -> float:
    """% of the sleeve invested at a drawdown of dd_pct (positive %), linear between alloc points."""
    pts = sorted(alloc)
    return float(np.interp(dd_pct, [p[0] for p in pts], [p[1] for p in pts]))


def step_index(dd_pct: float, alloc: list) -> int:
    """How many step levels (alloc points past the first) the drawdown has reached."""
    return sum(1 for lvl, _ in sorted(alloc)[1:] if dd_pct >= lvl)


def core_row(sym: str, cfg: dict, budget_pct: float, hist: pd.DataFrame, ref: pd.DataFrame | None = None) -> dict:
    """One core sleeve. `hist` = the ETF's daily bars; `ref` = the longer history used for the drawdown."""
    close = hist["close"].dropna()
    rclose = (ref if ref is not None else hist)["close"].dropna()
    price, rprice = float(close.iloc[-1]), float(rclose.iloc[-1])
    high = float(rclose.max())
    high_date = rclose.idxmax()
    dd = max(0.0, (1 - rprice / high) * 100)
    alloc = cfg["alloc"]
    target = alloc_target(dd, alloc)
    sleeve = budget_pct * cfg["weight"] / 100
    steps = sorted(alloc)[1:]
    idx = step_index(dd, alloc)
    conv = price / rprice                     # ETF price per unit of the reference
    nxt = None
    if idx < len(steps):
        lvl, tgt = steps[idx]
        nxt = {"dd_pct": lvl, "target_pct": tgt, "price": round(high * (1 - lvl / 100) * conv, 2)}
    prev = None
    if idx > 0:                               # recovering above the last step reached lowers the target
        lvl = steps[idx - 1][0]
        prev = {"dd_pct": lvl, "target_pct": sorted(alloc)[idx - 1][1],
                "price": round(high * (1 - lvl / 100) * conv, 2)}
    # scale-out cap as the bull matures: gain from the lowest close of the last gain_lookback_days
    gain, cap, gstep, gnext = None, None, 0, None
    if cfg.get("alloc_gain"):
        lb = int(cfg.get("gain_lookback_days", 756))
        low = float(rclose.iloc[-lb:].min())
        gain = (rprice / low - 1) * 100
        ga = sorted(cfg["alloc_gain"])
        cap = alloc_target(gain, ga)
        gstep = sum(1 for lvl, _ in ga[1:] if gain >= lvl)
        if gstep < len(ga) - 1:
            lvl, c2 = ga[gstep + 1]
            gnext = {"gain_pct": lvl, "cap_pct": c2, "price": round(low * (1 + lvl / 100) * conv, 2)}
        target = min(target, cap)
    st = trend_states(close).iloc[-1] if len(close) >= 220 else np.nan
    return {
        "symbol": sym, "weight": cfg["weight"], "price": round(price, 2),
        "ref_symbol": cfg.get("history_symbol") or sym, "high": round(high * conv, 2),
        "high_date": str(pd.Timestamp(high_date).date()), "dd_pct": round(dd, 1),
        "target_pct": round(target, 1), "base_pct": sorted(alloc)[0][1],
        "pyramid_pct": round(alloc_target(dd, alloc), 1),
        "sleeve_pct": round(sleeve, 2), "account_pct": round(sleeve * min(target, cap if cap is not None else 999) / 100, 2),
        "step": idx, "steps": len(steps), "next": nxt, "trim_above": prev,
        "trend_state": None if not np.isfinite(st) else float(st),
        "gain_pct": None if gain is None else round(gain, 1), "scale_cap_pct": None if cap is None else round(cap, 1),
        "gain_step": gstep, "next_trim": gnext,
        "full_at_dd": steps[-1][0] if steps else 0,
        "asof": str(close.index[-1].date()),
    }


def rs_score(close: pd.Series, bench: pd.Series, months: list[int]) -> float:
    """Average over `months` of (name return / benchmark return) - 1."""
    b = bench.reindex(close.index).ffill()
    vals = []
    for m in months:
        n = int(round(m * 21))
        if len(close) > n and np.isfinite(b.iloc[-1 - n]):
            vals.append((close.iloc[-1] / close.iloc[-1 - n]) / (b.iloc[-1] / b.iloc[-1 - n]) - 1)
    return float(np.mean(vals)) if vals else float("nan")


def pick_rows(watch: list, hists: dict, bench: pd.Series, prules: dict) -> list[dict]:
    rows = []
    for w in watch:
        sym = w["symbol"]
        h = hists.get(sym)
        base = {k: w.get(k) for k in ("symbol", "theme", "source", "thesis", "added")}
        if h is None or len(h["close"].dropna()) < 260:
            rows.append({**base, "status": "NO_DATA"})
            continue
        c = h["close"].dropna()
        st = float(trend_states(c).iloc[-1])
        hi1 = float(c.iloc[-TD:].max())
        rows.append({**base, "price": round(float(c.iloc[-1]), 2), "trend_state": st,
                     "rs": rs_score(c, bench, prules.get("rs_months", [6, 12])),
                     "dd_1y_pct": round((1 - float(c.iloc[-1]) / hi1) * 100, 1),
                     "stop_price": round(hi1 * (1 - prules.get("trailing_stop_pct", 28) / 100), 2),
                     "sma200": round(float(c.rolling(200).mean().iloc[-1]), 2), "asof": str(c.index[-1].date())})
    scored = sorted([r for r in rows if np.isfinite(r.get("rs", np.nan))], key=lambda r: -r["rs"])
    top_n = max(1, int(np.ceil(len(scored) * prules.get("rs_top_frac", 1 / 3))))
    for i, r in enumerate(scored):
        r["rs_rank"] = i + 1
        r["rs_top"] = i < top_n
        stop_hit = r["price"] <= r["stop_price"]
        if r["trend_state"] == 0 or stop_hit:
            r["status"] = "EXIT_IF_HELD"
            r["why"] = "below a falling 200-day" if r["trend_state"] == 0 else f"{r['dd_1y_pct']:.0f}% below its 1-year high"
        elif r["trend_state"] == 1 and r["rs_top"]:
            r["status"] = "ENTRY_OK"
            r["why"] = f"rising 200-day, strength rank {i + 1}/{len(scored)}"
        else:
            r["status"] = "WAIT"
            r["why"] = ("trend not confirmed" if r["trend_state"] < 1 else
                        f"strength rank {i + 1}/{len(scored)} (top {top_n} enter)")
        r["rs"] = round(r["rs"] * 100, 1)
    order = {"ENTRY_OK": 0, "WAIT": 1, "EXIT_IF_HELD": 2, "NO_DATA": 3}
    return sorted(rows, key=lambda r: (order.get(r["status"], 9), r.get("rs_rank", 99)))


def btc_warning(hist: pd.DataFrame) -> dict:
    c = hist["close"].dropna()
    st = trend_states(c)
    cur = float(st.iloc[-1])
    changed = st.ne(st.shift()).to_numpy().nonzero()[0]
    since = str(c.index[changed[-1]].date()) if len(changed) else None
    label = {1.0: "trend intact", 0.5: "trend weakening", 0.0: "trend broken"}.get(cur, "n/a")
    return {"symbol": "BTC-USD", "state": cur, "label": label, "since": since, "price": round(float(c.iloc[-1]), 2),
            "sma200": round(float(c.rolling(200).mean().iloc[-1]), 2), "asof": str(c.index[-1].date()),
            "note": "Readiness only: the core keeps holding; no exit is triggered."}


def build(rules: dict, fetch) -> dict:
    """fetch(sym) -> daily bars DataFrame with a 'close' column (raises on failure)."""
    pc = rules.get("portfolio") or {}
    out: dict = {"trend_exit": bool(pc.get("trend_exit", False)), "budget_pct": pc.get("budget_pct"),
                 "core": [], "picks": [], "notes": []}
    cache: dict = {}

    def get(sym):
        if sym not in cache:
            try:
                cache[sym] = fetch(sym)
            except Exception as e:  # noqa: BLE001 - one name failing never fails the scan
                cache[sym] = None
                out["notes"].append(f"portfolio: {sym} history unavailable ({str(e)[:80]})")
        return cache[sym]

    for sym, cfg in (pc.get("core") or {}).items():
        h = get(sym)
        ref = get(cfg["history_symbol"]) if cfg.get("history_symbol") else None
        if h is None or (cfg.get("history_symbol") and ref is None):
            out["core"].append({"symbol": sym, "weight": cfg["weight"], "error": "no data"})
            continue
        try:
            out["core"].append(core_row(sym, cfg, pc.get("budget_pct", 85), h, ref))
        except Exception as e:  # noqa: BLE001
            out["core"].append({"symbol": sym, "weight": cfg["weight"], "error": str(e)[:120]})
    out["reserve_pct"] = round(pc.get("budget_pct", 85) - sum(r.get("account_pct", 0) for r in out["core"]), 2)
    if pc.get("profiles"):          # per-account-size weights; the dashboard re-weights rows by the selected size
        out["profiles"] = {str(k): v for k, v in pc["profiles"].items()}
    bw = (pc.get("btc_warning") or {}).get("symbol")
    if bw and get(bw) is not None:
        out["btc_warning"] = btc_warning(get(bw))
    picks = rules.get("picks") or {}
    bench_h = get(pc.get("rs_benchmark", "QQQ"))
    if picks.get("watchlist") and bench_h is not None:
        hists = {w["symbol"]: get(w["symbol"]) for w in picks["watchlist"]}
        out["picks"] = pick_rows(picks["watchlist"], hists, bench_h["close"], picks.get("rules") or {})
        out["picks_rules"] = picks.get("rules")
    return out
