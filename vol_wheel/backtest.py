"""Backtest: QQQ core vs the basket, spikes-only vs always-on, vs buy-and-hold.

Daily simulation of the rulebook's short-put wheel on free price history (CBOE, Yahoo fallback).
Options are priced with Black-Scholes:
- names with a CBOE volatility index (QQQ -> VXN, SPY -> VIX, GLD -> GVZ) use it as 30-day IV
  (scaled by `vol_index_atm_ratio`, since VIX-style indexes sit above ATM IV), and get true IV rank
  and the IV/HV >= 1.15 gate exactly as the live scanner does;
- other names have no IV history, so IV = `stock_iv_mult` x max(HV20, HV60) and IV rank is the
  realized-vol percentile proxy the live scanner uses today. The multiplier is assumed, so it runs
  at several values (`stock_iv_mults`) and the results should be read as a sensitivity, not a fact.
Skew: iv(K) = atm - slope * ln(K/S) (puts richer, calls cheaper), floored at half the ATM IV.

Rules taken from config (the same knobs the scanner uses): IVR >= 50, spike >= 1.5 sigma within
1..3 days, IV/HV >= 1.15 on pre-move HV (vol-index names), regime deltas, 45 DTE, close at 50%,
21-DTE decision (OTM -> close, ITM -> hold to expiry and take assignment, or roll), covered calls
on assigned shares (momentum names at most 50%, strike >= net cost in Low/Mid), ladder of up to 3
rungs spaced by one 45-day expected move or 5 trading days, 5% entries, bucket / name / 80% caps,
circuit breakers at 25% and 40% drawdown. Cash (including put collateral) earns the 13-week T-bill
yield. Fractional contracts. Dividends, earnings IV and early assignment are ignored.

    python -m vol_wheel.backtest                 # fetch data, run every variant, write docs/backtest
    python -m vol_wheel.backtest --cache DIR      # reuse downloaded histories (CSV) between runs
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import data, signals
from .config import ROOT, load_rules, universe

log = logging.getLogger("vol_wheel.backtest")
N = NormalDist()
TD = signals.TRADING_DAYS


# ---------------------------------------------------------------- pricing

def bs_price(S: float, K: float, T: float, iv: float, cp: str, r: float = 0.0) -> float:
    """Black-Scholes price (no dividends). T in years."""
    if T <= 0 or iv <= 0:
        return max(S - K, 0.0) if cp == "C" else max(K - S, 0.0)
    sq = iv * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * iv * iv) * T) / sq
    d2 = d1 - sq
    disc = math.exp(-r * T)
    if cp == "C":
        return S * N.cdf(d1) - K * disc * N.cdf(d2)
    return K * disc * N.cdf(-d2) - S * N.cdf(-d1)


def bs_delta(S: float, K: float, T: float, iv: float, cp: str, r: float = 0.0) -> float:
    if T <= 0 or iv <= 0:
        return (1.0 if S > K else 0.0) if cp == "C" else (-1.0 if S < K else 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * iv * iv) * T) / (iv * math.sqrt(T))
    return N.cdf(d1) if cp == "C" else N.cdf(d1) - 1.0


def skew_iv(atm: float, S: float, K: float, slope: float, floor_frac: float = 0.5) -> float:
    return max(atm - slope * math.log(K / S), floor_frac * atm)


def strike_for_delta(S: float, T: float, atm: float, delta: float, cp: str, slope: float,
                     r: float = 0.0, iters: int = 25) -> float:
    """Strike whose (skewed-IV) Black-Scholes delta is `delta` (absolute, 0..1)."""
    delta = min(max(delta, 1e-4), 1 - 1e-4)
    d1 = N.inv_cdf(delta) if cp == "C" else -N.inv_cdf(delta)
    K = S
    for _ in range(iters):
        iv = skew_iv(atm, S, K, slope)
        K_new = S * math.exp(-d1 * iv * math.sqrt(T) + (r + 0.5 * iv * iv) * T)
        if abs(K_new - K) < 1e-8 * S:
            K = K_new
            break
        K = K_new
    return K


# ---------------------------------------------------------------- data

SPLIT_RATIOS = (2, 3, 4, 5, 8, 10, 15, 20, 25, 30)


def fix_splits(df: pd.DataFrame, tol: float = 0.03) -> tuple[pd.DataFrame, list[str]]:
    """Back-adjust unadjusted splits: a one-day close ratio within 3% of 1/n (or n) for a common n."""
    df = df.copy()
    notes = []
    c = df["close"].to_numpy(dtype=float, copy=True)
    for i in range(1, len(c)):
        r = c[i] / c[i - 1]
        if not np.isfinite(r) or 0.55 < r < 1.8:
            continue
        for n in SPLIT_RATIOS:
            for factor, kind in ((1.0 / n, f"1/{n} drop (split)"), (float(n), f"x{n} jump")):
                if abs(r - factor) / factor < tol:
                    cols = [col for col in ("open", "high", "low", "close") if col in df]
                    df.iloc[:i, [df.columns.get_loc(col) for col in cols]] *= factor
                    c[:i] *= factor
                    notes.append(f"{df.index[i].date()} {kind} adjusted")
                    break
            else:
                continue
            break
    return df, notes


def clean_ticks(df: pd.DataFrame, jump: float = 1.8) -> tuple[pd.DataFrame, list[str]]:
    """Drop one-day bad prints: a close that jumps by `jump`x (or 1/jump) and reverts the next day."""
    c = df["close"]
    r_prev, r_next = c / c.shift(1), c / c.shift(-1)
    bad = ((r_prev > jump) & (r_next > jump)) | ((r_prev < 1 / jump) & (r_next < 1 / jump))
    notes = [f"{d.date()} bad print dropped ({c[d]:g})" for d in c.index[bad]]
    return df[~bad], notes


def last_listing(df: pd.DataFrame, max_gap_days: int = 30) -> tuple[pd.DataFrame, list[str]]:
    """Keep the bars after the last gap longer than `max_gap_days`: a reused ticker (CEG was
    Constellation Energy until 2012, then the 2022 Exelon spin-off) is a different company."""
    gaps = df.index.to_series().diff().dt.days
    big = gaps[gaps > max_gap_days]
    if big.empty:
        return df, []
    cut = big.index[-1]
    return df.loc[cut:], [f"history before {cut.date()} dropped ({int(big.iloc[-1])}-day gap: earlier listing)"]


def load_history(sym: str, cfg: dict, cache: Path | None = None) -> tuple[pd.DataFrame, str]:
    """Longest daily history available: CBOE, else Yahoo (max period). Cached as CSV if asked."""
    if cache:
        f = cache / f"{sym}.csv"
        if f.exists():
            df = pd.read_csv(f, index_col=0, parse_dates=True)
            return df, "cache"
    df, src = None, ""
    try:
        df = data.parse_history(data.get_json(cfg["cboe_history_url"].format(sym=sym),
                                              cfg.get("timeout_s", 30), cfg.get("retries", 3)))
        src = "cboe"
    except Exception as e:  # noqa: BLE001
        log.warning("%s CBOE history failed: %s", sym, e)
    if df is None or len(df) < cfg.get("history_min_days", 220):
        try:
            y = data.fetch_history_yf(sym, period="max")
            if df is None or len(y) > len(df):
                df, src = y, "yahoo"
        except Exception as e:  # noqa: BLE001
            log.warning("%s Yahoo history failed: %s", sym, e)
    elif sym.startswith("_"):
        # CBOE's VXN/GVZ series start in 2009; Yahoo's go further back. Prepend the older part.
        try:
            y = data.fetch_history_yf(sym, period="max")
            older = y[y.index < df.index[0]]
            if len(older):
                df = pd.concat([older[df.columns.intersection(older.columns)], df]).sort_index()
                src = "yahoo+cboe"
        except Exception as e:  # noqa: BLE001
            log.warning("%s Yahoo backfill failed: %s", sym, e)
    if df is None or df.empty:
        raise RuntimeError(f"no history for {sym}")
    df = df[["open", "high", "low", "close"]].astype(float)
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache / f"{sym}.csv")
    return df, src


def cash_rate_series(cal: pd.DatetimeIndex, bt: dict, cfg: dict, cache: Path | None) -> tuple[pd.Series, str]:
    """Annual T-bill yield (decimal) per day; constant fallback."""
    fallback = bt.get("cash_yield_fallback_pct", 2.0) / 100
    sym = bt.get("cash_yield_symbol")
    if sym:
        try:
            if cache and (cache / f"{sym}.csv").exists():
                h = pd.read_csv(cache / f"{sym}.csv", index_col=0, parse_dates=True)
            else:
                h = data.fetch_history_yf(sym, period="max")[["close"]]
                if cache:
                    cache.mkdir(parents=True, exist_ok=True)
                    h.to_csv(cache / f"{sym}.csv")
            s = h["close"].astype(float)
            s = s.where((s >= 0) & (s < 30))
            if s.dropna().median() > 20:  # some feeds quote the rate x10
                s = s / 10
            out = (s / 100).reindex(cal.union(s.index)).ffill().reindex(cal).fillna(fallback)
            return out, sym
        except Exception as e:  # noqa: BLE001
            log.warning("cash yield %s failed (%s); using %.1f%%", sym, e, fallback * 100)
    return pd.Series(fallback, index=cal), f"constant {fallback * 100:.1f}%"


# ---------------------------------------------------------------- signals (vectorized)

def _rolling_pct_rank(s: pd.Series, window: int, min_periods: int) -> pd.Series:
    return s.rolling(window, min_periods=min_periods).apply(lambda w: (w <= w[-1]).mean() * 100.0, raw=True)


def signal_frame(hist: pd.DataFrame, rules: dict, vol_index: pd.Series | None = None,
                 stock_iv_mult: float = 1.15) -> pd.DataFrame:
    """Per-day signals as the live scanner computes them on that day's close."""
    th, rg, ivc, bt = rules["thresholds"], rules["regime"], rules["iv_rank"], rules["backtest"]
    c = hist["close"].astype(float)
    f = pd.DataFrame(index=c.index)
    f["close"] = c
    w = th.get("spike_hv_window", 20)
    hv20 = signals.hv(c, w)
    hv60 = signals.hv(c, bt.get("stock_iv_hv_long", 60))
    f["hv20"] = hv20
    k_pre = th["spike_max_days"] if th.get("iv_hv_pre_move") else 0
    f["hv_ref"] = hv20.shift(k_pre)

    # spikes: z_k = (c_t - c_{t-k}) / (HV20_{t-k} * c_{t-k} / sqrt(252) * sqrt(k))
    down = pd.Series(0.0, index=c.index)
    up = pd.Series(0.0, index=c.index)
    for k in range(1, th["spike_max_days"] + 1):
        base = c.shift(k)
        sig = hv20.shift(k) * base / math.sqrt(TD) * math.sqrt(k)
        z = (c - base) / sig
        down = np.fmax(down, (-z).fillna(0))
        up = np.fmax(up, z.fillna(0))
    f["down"], f["up"] = down, up

    # IV and IV rank
    proxy = _rolling_pct_rank(hv20, ivc["lookback_days"], 20)
    model_iv = stock_iv_mult * np.fmax(hv20, hv60.fillna(hv20))
    f["iv"], f["iv_raw"], f["ivr"], f["gate"] = model_iv, model_iv, proxy, False
    if vol_index is not None and len(vol_index):
        vi = (vol_index.reindex(c.index.union(vol_index.index)).ffill().reindex(c.index) / 100.0)
        lb = ivc["lookback_days"]
        lo = vi.rolling(lb, min_periods=ivc.get("min_history_days", 60)).min()
        hi = vi.rolling(lb, min_periods=ivc.get("min_history_days", 60)).max()
        vi_rank = ((vi - lo) / (hi - lo).where(hi - lo > 1e-12) * 100).clip(0, 100)
        has = vi.notna() & vi_rank.notna()
        ratio = bt.get("vol_index_atm_ratio", 0.9)
        f["iv"] = np.where(has, vi * ratio, f["iv"])
        f["iv_raw"] = np.where(has, vi, f["iv_raw"])
        f["ivr"] = np.where(has, vi_rank, f["ivr"])
        f["gate"] = has

    # regime from the close/SMA200 extension percentile
    ratio200 = c / c.rolling(rg["sma_window"]).mean()
    ext = _rolling_pct_rank(ratio200, rg["lookback_days"], rg["min_days"])
    f["regime"] = np.where(ext.isna(), "Mid", np.where(ext < rg["low_below"], "Low",
                                                       np.where(ext > rg["high_above"], "High", "Mid")))
    return f


# ---------------------------------------------------------------- engine

@dataclass
class Opt:
    sym: str
    cp: str          # "P" or "C"
    strike: float
    qty: float       # shares (contracts x 100), fractional
    opened: pd.Timestamp
    expiry: pd.Timestamp
    entry_mid: float
    rolls: int = 0


class Sim:
    """One variant over one window. `frames` = {sym: signal_frame}, all on the same calendar."""

    def __init__(self, variant: dict, frames: dict, meta: dict, rates: pd.Series, rules: dict, start, end):
        self.v, self.frames, self.meta, self.rates, self.rules = variant, frames, meta, rates, rules
        self.bt = rules["backtest"]
        self.cal = rates.index[(rates.index >= start) & (rates.index <= end)]
        self.syms = [s for s in variant["symbols"] if s in frames]
        # per-day records (fast row access) and forward-filled closes for marking
        self.recs, self.ffclose, self.elig_from = {}, {}, {}
        min_bars = rules["backtest"].get("min_history_days", 260)
        for s in self.syms:
            f = frames[s].reindex(self.cal)
            self.recs[s] = f.to_dict("records")
            self.ffclose[s] = frames[s]["close"].ffill().reindex(self.cal).to_numpy()
            valid = frames[s]["close"].dropna()
            self.elig_from[s] = valid.index[min_bars - 1] if len(valid) >= min_bars else None
        self.last_atm: dict = {}
        self.cash = float(self.bt["account"])
        self.shares = {s: 0.0 for s in self.syms}
        self.basis = {s: 0.0 for s in self.syms}
        self.opts: list[Opt] = []
        self.last_put: dict = {}       # sym -> (day index, strike, expected move)
        self.last_call_day: dict = {}
        self.cf = {s: 0.0 for s in self.syms}   # per-name cash flow (P&L attribution)
        self.stats = {k: 0 for k in ("puts_sold", "calls_sold", "closed_profit", "closed_21dte", "rolled",
                                     "assigned", "called_away", "expired_worthless", "breaker_days")}
        self.premium = 0.0
        self.peak = self.cash
        self.equity, self.deployed, self.short_open, self.in_shares = [], [], [], []

    # --- helpers
    def _slip(self, sym: str) -> float:
        idx = sym in self.meta["index_syms"]
        return self.bt["costs"]["slippage_pct_index" if idx else "slippage_pct_stock"] / 100

    def _comm(self) -> float:
        return self.bt["costs"]["per_contract"] / 100.0

    def _slope(self, sym: str) -> float:
        return self.bt["skew_slope"]["index" if sym in self.meta["vol_index_syms"] else "stock"]

    def _mark(self, o: Opt, S: float, atm: float, d: pd.Timestamp, r: float) -> float:
        T = max((o.expiry - d).days, 0) / 365.0
        return bs_price(S, o.strike, T, skew_iv(atm, S, o.strike, self._slope(o.sym)), o.cp, r)

    def _row(self, sym: str, i: int) -> dict | None:
        row = self.recs[sym][i]
        if not np.isfinite(row["close"]) or not np.isfinite(row["iv"]) or row["iv"] <= 0:
            return None
        return row

    def _eligible(self, sym: str, d) -> bool:
        e = self.elig_from[sym]
        return e is not None and d >= e

    def _cap(self, key: str, default: float) -> float:
        caps = self.v.get("caps") or {}
        return caps.get(key, default)

    def _entry_frac(self, sym: str) -> float:
        e = self.v.get("entry_pct", self.rules["sizing"]["entry_pct"])
        if isinstance(e, dict):
            e = e.get(self.meta["bucket"].get(sym), e.get("default", self.rules["sizing"]["entry_pct"]))
        return e / 100.0

    def _exposure(self, prices: dict) -> tuple[dict, float]:
        by_sym = {s: self.shares[s] * prices[s] for s in self.syms}
        for o in self.opts:
            if o.cp == "P":
                by_sym[o.sym] += o.strike * o.qty
        return by_sym, sum(by_sym.values())

    def _room(self, sym: str, by_sym: dict, total: float, E: float) -> float:
        bucket = self.meta["bucket"].get(sym)
        u = self.rules
        name_cap = (u["per_name_cap_index"] if sym in self.meta["index_syms"] else u["per_name_cap"])
        name_cap = self._cap(sym, self._cap("per_name", name_cap)) / 100
        bcap = self._cap(bucket, u["universe"].get(bucket, {}).get("cap", 100)) / 100
        tcap = self._cap("total", u["total_deployed_cap"]) / 100
        in_bucket = sum(v for s, v in by_sym.items() if self.meta["bucket"].get(s) == bucket)
        collateral = sum(o.strike * o.qty for o in self.opts if o.cp == "P")
        free_cash = self.cash - collateral
        return min(name_cap * E - by_sym[sym], bcap * E - in_bucket, tcap * E - total, free_cash)

    # --- main loop
    def run(self) -> "Sim":
        rules, th, bt = self.rules, self.rules["thresholds"], self.bt
        mgmt = rules["management"]
        tp = mgmt["take_profit_pct"] / 100
        decide_dte = mgmt["decide_dte"]
        dte = bt.get("dte", rules["strikes"]["dte_target"])
        mode = self.v["mode"]
        cb = bt.get("circuit_breakers") or {}
        prev_d = None
        for i, d in enumerate(self.cal):
            r = float(self.rates.loc[d])
            if prev_d is not None:
                self.cash *= 1 + r * (d - prev_d).days / 365.0
            prev_d = d
            rows = {s: self._row(s, i) for s in self.syms}
            prices = {s: float(self.ffclose[s][i]) for s in self.syms}
            prices = {s: (p if np.isfinite(p) else 0.0) for s, p in prices.items()}
            atms = {s: (float(rows[s]["iv"]) if rows[s] is not None else None) for s in self.syms}
            for s, a in atms.items():
                if a is not None:
                    self.last_atm[s] = a

            self.cur_price = prices
            self._manage(d, i, prices, atms, r, tp, decide_dte, dte)
            E = self._equity(d, prices, atms, r)
            self.peak = max(self.peak, E)
            dd = 1 - E / self.peak if self.peak > 0 else 0.0
            size_mult, index_only = 1.0, False
            if cb and dd * 100 >= cb.get("half_size_dd", 101):
                size_mult = 0.5
                self.stats["breaker_days"] += 1
            if cb and dd * 100 >= cb.get("index_only_dd", 101):
                index_only = True

            order = sorted(self.syms, key=lambda s: -(float(rows[s]["down"]) if rows[s] is not None else 0))
            for s in order:
                row = rows[s]
                if row is None or prices[s] <= 0 or not self._eligible(s, d):
                    continue
                self._maybe_put(s, row, d, i, E, prices, r, dte, size_mult, index_only, mode)
                self._maybe_call(s, row, d, i, E, r, dte, mode)

            E = self._equity(d, prices, atms, r)
            by_sym, total = self._exposure(prices)
            self.equity.append(E)
            self.deployed.append(total / E if E > 0 else 0.0)
            self.short_open.append(bool(self.opts))
            self.in_shares.append(sum(self.shares[s] * prices[s] for s in self.syms) / E if E > 0 else 0.0)
        self.final_prices = {s: (float(self.ffclose[s][-1]) if np.isfinite(self.ffclose[s][-1]) else 0.0)
                             for s in self.syms}
        return self

    def _equity(self, d, prices, atms, r) -> float:
        E = self.cash + sum(self.shares[s] * prices[s] for s in self.syms)
        for o in self.opts:
            E -= o.qty * self._mark(o, prices[o.sym], self.last_atm.get(o.sym, 0.2), d, r)
        return E

    def _manage(self, d, i, prices, atms, r, tp, decide_dte, dte):
        keep = []
        reopen = []
        for o in self.opts:
            S = prices[o.sym]
            left = (o.expiry - d).days
            itm = S < o.strike if o.cp == "P" else S > o.strike
            if left <= 0:
                if itm and o.cp == "P":
                    self._assign(o, S)
                elif itm:
                    self.shares[o.sym] -= o.qty
                    self.cash += o.strike * o.qty
                    self.cf[o.sym] += o.strike * o.qty
                    self.stats["called_away"] += 1
                else:
                    self.stats["expired_worthless"] += 1
                continue
            atm = atms.get(o.sym)
            if atm is None:          # no quote today: hold
                keep.append(o)
                continue
            mark = self._mark(o, S, atm, d, r)
            if mark <= (1 - tp) * o.entry_mid:
                self._buy_back(o, mark)
                self.stats["closed_profit"] += 1
            elif left <= decide_dte and not itm:
                self._buy_back(o, mark)
                self.stats["closed_21dte"] += 1
            elif left <= decide_dte and self.bt.get("decide_itm") == "roll" and o.rolls < self.bt.get("max_rolls", 1):
                self._buy_back(o, mark)
                self.stats["rolled"] += 1
                reopen.append((o, atm))
            else:
                keep.append(o)
        self.opts = keep
        for o, atm in reopen:
            n = self._sell(o.sym, o.cp, o.strike, o.qty, d, atm, r, dte, count=False)
            if n:
                n.rolls = o.rolls + 1

    def _assign(self, o: Opt, S: float):
        s = o.sym
        held = self.shares[s]
        self.basis[s] = ((self.basis[s] * held) + (o.strike - o.entry_mid) * o.qty) / (held + o.qty)
        self.shares[s] += o.qty
        self.cash -= o.strike * o.qty
        self.cf[s] -= o.strike * o.qty
        self.stats["assigned"] += 1

    def _buy_back(self, o: Opt, mark: float):
        px = mark + max(mark * self._slip(o.sym), 0.01 if mark > 0.01 else 0.0) + self._comm()
        self.cash -= px * o.qty
        self.cf[o.sym] -= px * o.qty

    def _sell(self, sym, cp, K, qty, d, atm, r, dte, count=True) -> Opt | None:
        S = self.cur_price[sym]
        T = dte / 365.0
        mid = bs_price(S, K, T, skew_iv(atm, S, K, self._slope(sym)), cp, r)
        if mid <= 0.0005 * S:
            return None
        px = mid - max(mid * self._slip(sym), 0.01) - self._comm()
        if px <= 0:
            return None
        o = Opt(sym, cp, K, qty, d, d + pd.Timedelta(days=dte), mid)
        self.opts.append(o)
        self.cash += px * qty
        self.cf[sym] += px * qty
        self.premium += px * qty
        if count:
            self.stats["puts_sold" if cp == "P" else "calls_sold"] += 1
        return o

    def _put_delta(self, regime: str) -> float:
        pd_ = self.v.get("put_delta")
        if pd_ is None:
            pd_ = self.rules["strikes"]["put_delta"][regime]
        elif isinstance(pd_, dict):
            pd_ = pd_[regime]
        return pd_ / 100

    def _call_delta(self, regime: str) -> float:
        cd = self.v.get("call_delta")
        if cd is None:
            cd = self.rules["strikes"]["call_delta"][regime]
        elif isinstance(cd, dict):
            cd = cd[regime]
        return cd / 100

    def _iv_hv_ok(self, row) -> bool:
        if not bool(row["gate"]) or not self.v.get("iv_hv_gate", True):
            return True
        hv_ref = row["hv_ref"]
        return bool(np.isfinite(hv_ref) and hv_ref > 0 and row["iv_raw"] / hv_ref >= self.rules["thresholds"]["min_iv_hv_ratio"])

    def _maybe_put(self, s, row, d, i, E, prices, r, dte, size_mult, index_only, mode):
        th, bt = self.rules["thresholds"], self.bt
        ivr, regime = float(row["ivr"]) if np.isfinite(row["ivr"]) else float("nan"), row["regime"]
        if index_only and not (s in self.meta["index_syms"] and regime == "Low"):
            return
        S = float(row["close"])
        open_puts = [o for o in self.opts if o.sym == s and o.cp == "P"]
        last = self.last_put.get(s)
        if mode == "spike":
            ivr_min = self.v.get("min_ivr", th["ivr_sell"])
            if not (np.isfinite(ivr) and ivr >= ivr_min and row["down"] >= th["spike_sigma"] and self._iv_hv_ok(row)):
                return
            if len(open_puts) >= self.v.get("max_rungs", self.rules["sizing"]["ladder_rungs"]):
                return
            if open_puts and last is not None:
                li, lk, lem = last
                if not (S <= lk - lem or i - li >= bt.get("ladder_spacing_days", 5)):
                    return
        elif mode == "always":
            if np.isfinite(ivr) and ivr < self.v.get("min_ivr", 0):
                return
            if last is not None and i - last[0] < self.v.get("entry_every_days", 5):
                return
        else:
            return
        atm = float(row["iv"])
        T = dte / 365.0
        K = strike_for_delta(S, T, atm, self._put_delta(regime), "P", self._slope(s), r)
        want = self._entry_frac(s) * E * size_mult
        by_sym, total = self._exposure(prices)
        room = self._room(s, by_sym, total, E)
        notional = min(want, room)
        if notional < 0.5 * want or notional <= 0:
            return
        o = self._sell(s, "P", K, notional / K, d, atm, r, dte)
        if o:
            em_iv = max(atm, float(row["hv20"])) if s in self.rules.get("weekend_gap_names", []) else atm
            self.last_put[s] = (i, K, S * em_iv * math.sqrt(self.rules["sizing"]["ladder_dte"] / 365))

    def _maybe_call(self, s, row, d, i, E, r, dte, mode):
        th = self.rules["thresholds"]
        if self.shares[s] <= 1e-9:
            return
        cov = self.rules["momentum_max_call_coverage"] / 100 if s in self.rules["momentum_names"] else 1.0
        covered = sum(o.qty for o in self.opts if o.sym == s and o.cp == "C")
        qty = self.shares[s] * cov - covered
        S = float(row["close"])
        if qty * S < 0.005 * E:
            return
        ivr, regime = float(row["ivr"]) if np.isfinite(row["ivr"]) else float("nan"), row["regime"]
        calls_mode = self.v.get("calls", "spike" if mode == "spike" else "always")
        if calls_mode == "spike":
            if not (np.isfinite(ivr) and ivr >= th["ivr_sell"] and row["up"] >= th["spike_sigma"] and self._iv_hv_ok(row)):
                return
        atm = float(row["iv"])
        T = dte / 365.0
        K = strike_for_delta(S, T, atm, self._call_delta(regime), "C", self._slope(s), r)
        if regime in self.bt.get("call_floor_regimes", ["Low", "Mid"]):
            K = max(K, self.basis[s])
        if self._sell(s, "C", K, qty, d, atm, r, dte):
            self.last_call_day[s] = i

    # --- results
    def result(self) -> dict:
        eq = pd.Series(self.equity, index=self.cal)
        out = metrics(eq, self.rates.reindex(self.cal), self.bt)
        out["avg_deployed_pct"] = round(float(np.mean(self.deployed)) * 100, 1)
        out["avg_shares_pct"] = round(float(np.mean(self.in_shares)) * 100, 1)
        out["days_with_shorts_pct"] = round(float(np.mean(self.short_open)) * 100, 1)
        yrs = max(len(eq) / TD, 1e-9)
        out["premium_per_year_pct"] = round(self.premium / yrs / float(eq.mean()) * 100, 2)
        out["stats"] = dict(self.stats)
        out["puts_per_year"] = round(self.stats["puts_sold"] / yrs, 1)
        last_d = self.cal[-1]
        atms = {s: self.last_atm.get(s, 0.2) for s in self.syms}
        pnl = dict(self.cf)
        for s in self.syms:
            pnl[s] += self.shares[s] * self.final_prices[s]
        for o in self.opts:
            pnl[o.sym] -= o.qty * self._mark(o, self.final_prices[o.sym], atms[o.sym], last_d, float(self.rates.loc[last_d]))
        out["pnl_by_symbol"] = {s: round(v) for s, v in sorted(pnl.items(), key=lambda kv: kv[1]) if abs(v) >= 1}
        out["equity_weekly"] = weekly(eq)
        return out


def run_hold(variant: dict, frames: dict, meta: dict, rates: pd.Series, rules: dict, start, end) -> dict:
    """Buy-and-hold at `weight`% (rest in T-bills), equal weight across eligible names, monthly rebalance."""
    bt = rules["backtest"]
    cal = rates.index[(rates.index >= start) & (rates.index <= end)]
    syms = [s for s in variant["symbols"] if s in frames]
    w = variant.get("weight", 100) / 100
    # forward-filled: a missing bar for one name must not value the holding at zero
    closes = pd.DataFrame({s: frames[s]["close"] for s in syms}).ffill().reindex(cal)
    held = {s: 0.0 for s in syms}
    cash = float(bt["account"])
    eq, prev_d, last_month = [], None, None
    min_bars = bt.get("min_history_days", 260)
    for d in cal:
        if prev_d is not None:
            cash *= 1 + float(rates.loc[d]) * (d - prev_d).days / 365.0
        prev_d = d
        px = {s: closes.at[d, s] for s in syms}
        px_ok = {s: p for s, p in px.items() if np.isfinite(p) and p > 0}
        E = cash + sum(held[s] * px_ok.get(s, 0.0) for s in syms)
        if d.month != last_month:
            last_month = d.month
            elig = [s for s in px_ok if frames[s]["close"].loc[meta["first_date"][s]:d].count() >= min_bars]
            if elig:
                for s in syms:
                    if held[s] and s in px_ok:
                        cash += held[s] * px_ok[s]
                        held[s] = 0.0
                tgt = E * w / len(elig)
                for s in elig:
                    held[s] = tgt / px_ok[s]
                    cash -= tgt
        eq.append(cash + sum(held[s] * px_ok.get(s, 0.0) for s in syms))
    eqs = pd.Series(eq, index=cal)
    out = metrics(eqs, rates.reindex(cal), bt)
    out["avg_deployed_pct"] = round(w * 100, 1)
    out["equity_weekly"] = weekly(eqs)
    return out


def weekly(eq: pd.Series) -> list:
    w = eq.resample("W-FRI").last().dropna()
    return [[d.strftime("%Y-%m-%d"), round(float(v))] for d, v in w.items()]


def metrics(eq: pd.Series, rates: pd.Series, bt: dict) -> dict:
    eq = eq.dropna()
    ret = eq.pct_change().dropna()
    days = (eq.index[-1] - eq.index[0]).days
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (365.25 / max(days, 1)) - 1
    vol = float(ret.std() * math.sqrt(TD)) if len(ret) > 1 else float("nan")
    rf = rates.reindex(ret.index).fillna(0) / TD
    ex = ret - rf
    sharpe = float(ex.mean() / ret.std() * math.sqrt(TD)) if ret.std() > 0 else float("nan")
    dd = eq / eq.cummax() - 1
    trough = dd.idxmin()
    under = (dd < 0).astype(int)
    longest = int(under.groupby((under == 0).cumsum()).sum().max()) if len(under) else 0
    yearly = {}
    for y, g in eq.groupby(eq.index.year):
        prev = eq[eq.index.year < y]
        base = prev.iloc[-1] if len(prev) else g.iloc[0]
        yearly[str(y)] = round((g.iloc[-1] / base - 1) * 100, 1)
    periods = {}
    for name, (a, b) in (bt.get("periods") or {}).items():
        seg = eq.loc[str(a):str(b)]
        if len(seg) > 5:
            pdd = seg / seg.cummax() - 1
            periods[name] = {"return_pct": round((seg.iloc[-1] / seg.iloc[0] - 1) * 100, 1),
                             "max_dd_pct": round(float(pdd.min()) * 100, 1)}
    full_years = {y: v for y, v in yearly.items() if (eq.index.year == int(y)).sum() > 200}
    return {
        "start": eq.index[0].strftime("%Y-%m-%d"), "end": eq.index[-1].strftime("%Y-%m-%d"),
        "final": round(float(eq.iloc[-1])), "cagr_pct": round(cagr * 100, 2), "vol_pct": round(vol * 100, 1),
        "sharpe": round(sharpe, 2), "max_dd_pct": round(float(dd.min()) * 100, 1),
        "max_dd_date": trough.strftime("%Y-%m-%d"), "longest_underwater_days": longest,
        "worst_year_pct": min(full_years.values()) if full_years else None,
        "yearly_pct": yearly, "periods": periods,
    }


# ---------------------------------------------------------------- orchestration

def resolve_symbols(spec, rules: dict) -> list[str]:
    if spec == "universe":
        return [u["symbol"] for u in universe(rules)]
    return list(spec)


def run(rules: dict, cache: Path | None = None, out_dir: Path | None = None) -> dict:
    bt = rules["backtest"]
    uni = universe(rules)
    bucket = {u["symbol"]: u["bucket"] for u in uni}
    index_syms = set(rules["universe"].get("Index", {}).get("core", []) or []) | set(
        rules["universe"].get("Index", {}).get("opportunistic", []) or [])
    vol_map = dict(bt.get("vol_index", {}))
    variants = bt["variants"]
    syms = sorted({s for v in variants for s in resolve_symbols(v["symbols"], rules)})
    hists, info = {}, {}
    for s in syms + sorted(set(vol_map.values())):
        try:
            df, src = load_history(s, rules["data"], cache)
            df, notes = clean_ticks(df)
            if not s.startswith("_"):
                floor = (bt.get("listing_dates") or {}).get(s) or bt.get("data_start")
                if floor and df.index[0] < pd.Timestamp(floor):
                    df = df.loc[str(floor):]
                    notes.append(f"bars before {floor} dropped")
                df, n1 = last_listing(df, bt.get("max_gap_days", 30))
                df, n2 = fix_splits(df)
                notes += n1 + n2
            hists[s] = df
            info[s] = {"source": src, "first": df.index[0].strftime("%Y-%m-%d"),
                       "last": df.index[-1].strftime("%Y-%m-%d"), "bars": len(df), "notes": notes}
            lr = np.log(df["close"]).diff().abs()
            print(f"data: {s:6s} {src:6s} {info[s]['first']} -> {info[s]['last']} ({len(df)} bars)"
                  f"  biggest 1-day move {math.expm1(lr.max()) * 100:+.0f}% on {lr.idxmax().date()}"
                  + (f"  {'; '.join(notes)}" if notes else ""), flush=True)
        except Exception as e:  # noqa: BLE001
            info[s] = {"error": str(e)}
            print(f"data: {s:6s} FAILED {e}", flush=True)

    cal_sym = bt.get("calendar_symbol", "SPY")
    cal = hists[cal_sym].index
    rates, rate_src = cash_rate_series(cal, bt, rules["data"], cache)
    print(f"cash yield: {rate_src}", flush=True)
    mults = bt.get("stock_iv_mults", [1.15])
    base_mult = bt.get("stock_iv_mult", 1.15)

    def frames_for(mult):
        fr = {}
        for s in syms:
            if s not in hists:
                continue
            vi = hists[vol_map[s]]["close"] if s in vol_map and vol_map[s] in hists else None
            fr[s] = signal_frame(hists[s], rules, vi, mult).reindex(cal)
        return fr

    frames_by_mult = {m: frames_for(m) for m in sorted(set(mults) | {base_mult})}
    meta = {"bucket": bucket, "index_syms": index_syms,
            "vol_index_syms": {s for s in vol_map if vol_map[s] in hists},
            "first_date": {s: hists[s].index[0] for s in syms if s in hists}}

    results = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "data": info,
               "cash_yield": rate_src, "stock_iv_mult": base_mult, "windows": {}}
    for wname, w in bt["windows"].items():
        start = pd.Timestamp(w["start"])
        end = pd.Timestamp(w.get("end") or cal[-1])
        wres = {"start": str(start.date()), "end": str(end.date()), "label": w.get("label", wname), "variants": {}}
        for v in variants:
            v = {**v, "symbols": resolve_symbols(v["symbols"], rules)}
            uses_stock_iv = any(s not in meta["vol_index_syms"] for s in v["symbols"])
            run_mults = (mults if (uses_stock_iv and v["mode"] != "hold") else [base_mult])
            for m in run_mults:
                key = v["name"] if m == base_mult else f"{v['name']}@{m:g}"
                fr = frames_by_mult[m]
                if v["mode"] == "hold":
                    res = run_hold(v, fr, meta, rates, rules, start, end)
                else:
                    res = Sim(v, fr, meta, rates, rules, start, end).run().result()
                res["label"] = v.get("label", v["name"]) + ("" if m == base_mult else f" (stock IV {m:g}x HV)")
                res["stock_iv_mult"] = m if uses_stock_iv else None
                if m != base_mult:
                    res.pop("equity_weekly", None)
                wres["variants"][key] = res
                print(f"{wname:7s} {key:22s} CAGR {res['cagr_pct']:6.2f}%  maxDD {res['max_dd_pct']:6.1f}%  "
                      f"Sharpe {res['sharpe']:5.2f}  deployed {res['avg_deployed_pct']:5.1f}%"
                      + (f"  puts/yr {res['puts_per_year']}" if "puts_per_year" in res else ""), flush=True)
        results["windows"][wname] = wres
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(results, separators=(",", ":")))
        (out_dir / "report.md").write_text(report(results, rules))
    return results


def _pct(x) -> str:
    return "–" if x is None else f"{x:.1f}%"


def report(res: dict, rules: dict) -> str:
    bt = rules["backtest"]
    pnames = list((bt.get("periods") or {}).keys())
    lines = ["# vol-wheel backtest", "",
             f"Generated {res['generated']} by `python -m vol_wheel.backtest` (workflow `backtest`). "
             f"Account ${bt['account']:,}, cash yield {res['cash_yield']}. Single-stock IV is modelled as "
             f"{res['stock_iv_mult']:g}× max(HV20, HV60) unless a row says otherwise.", "",
             "Deployed = average put collateral + shares as % of the account; In shares = the part held as "
             "assigned stock; Premium/yr = option credits (after costs) per year as % of average equity.", ""]
    for wname, w in res["windows"].items():
        lines += [f"## {w['label']} ({w['start']} → {w['end']})", "",
                  "| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | " + " | ".join(pnames)
                  + " | Deployed | Puts/yr | Assigned | Premium/yr | In shares |",
                  "|---|---|---|---|---|---|" + "---|" * len(pnames) + "---|---|---|---|---|"]
        for key, v in w["variants"].items():
            per = " | ".join(f"{v['periods'][p]['return_pct']:+.1f}%" if p in v.get("periods", {}) else "–"
                             for p in pnames)
            st = v.get("stats", {})
            lines.append(f"| {v['label']} | {v['cagr_pct']:.1f}% | {v['vol_pct']:.1f}% | {v['sharpe']:.2f} | "
                         f"{v['max_dd_pct']:.1f}% | {_pct(v['worst_year_pct'])} | "
                         f"{per} | {v['avg_deployed_pct']:.0f}% | {v.get('puts_per_year', '–')} | "
                         f"{st.get('assigned', '–')} | {_pct(v.get('premium_per_year_pct'))} | "
                         f"{_pct(v.get('avg_shares_pct'))} |")
        lines.append("")
        for key, v in w["variants"].items():
            if v.get("pnl_by_symbol") and "@" not in key and len(v["pnl_by_symbol"]) > 1:
                parts = ", ".join(f"{s} {p / 1000:+,.0f}k" for s, p in v["pnl_by_symbol"].items())
                lines.append(f"- **{v['label']}** P&L by name (excl. interest): {parts}")
        lines.append("")
    lines += ["## Data", ""]
    for s, i in res["data"].items():
        lines.append(f"- {s}: " + (i.get("error") or f"{i['source']} {i['first']} → {i['last']} ({i['bars']} bars)"
                                    + (f"; {'; '.join(i['notes'])}" if i.get("notes") else "")))
    lines += ["", "## Caveats", "",
              "- Option prices are Black-Scholes, not market quotes. Index names use VXN/VIX/GVZ × "
              f"{bt.get('vol_index_atm_ratio', 0.9)} as ATM IV with a fixed skew; single stocks use an assumed IV/HV "
              "multiple, so their premium (and the basket's edge) is a modelling choice: read the sensitivity rows.",
              "- The basket is today's universe applied to the past (hindsight and survivorship bias in its favour).",
              "- Prices exclude dividends (buy-and-hold is understated by ~0.6%/yr for QQQ, ~1.5% for SPY).",
              "- Earnings IV, early assignment, rolling for credit beyond `max_rolls`, and integer contract sizes are not modelled.",
              "- Trades fill at the signal day's close; the live scanner alerts intraday on delayed quotes."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, help="directory to cache downloaded histories")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "backtest")
    ap.add_argument("--rules", type=Path)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rules = load_rules(args.rules)
    res = run(rules, args.cache, args.out)
    print(report(res, rules))
    return 0


if __name__ == "__main__":
    sys.exit(main())
