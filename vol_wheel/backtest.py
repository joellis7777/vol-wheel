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

def vix_cap(vix: float, bands: list) -> float | None:
    """Total-deployment cap (% of account) for a VIX level: bands = [[vix_at_or_above, cap_pct], ...]."""
    if vix is None or not np.isfinite(vix) or not bands:
        return None
    cap = None
    for lo, pct in sorted(bands):
        if vix >= lo:
            cap = pct
    return cap


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
    dte0: int = 45   # DTE at entry; options opened at or inside the decision DTE are held to expiry
    wing: float | None = None   # long put strike when this is a put credit spread (IRA defined risk)

    @property
    def collateral(self) -> float:
        """Cash it ties up: the strike for a cash-secured put, the width for a spread."""
        return (self.strike - self.wing if self.wing is not None else self.strike) * self.qty


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
        # scale-in sizing: each new put's size x a multiplier set by the name's drawdown from its N-day high
        sbd = variant.get("size_by_dd")
        self.size_dd = {}
        if sbd:
            look = int(variant.get("size_dd_lookback", 252))
            for s in self.syms:
                c = frames[s]["close"].ffill()
                self.size_dd[s] = (1 - c / c.rolling(look, min_periods=20).max()).reindex(self.cal).fillna(0).to_numpy() * 100
        self.last_atm: dict = {}
        vix = meta.get("vix")
        self.vix = (vix.reindex(vix.index.union(self.cal)).ffill().reindex(self.cal).to_numpy()
                    if vix is not None else np.full(len(self.cal), np.nan))
        bands = variant.get("vix_caps")
        self.vix_bands = rules.get("deployment", {}).get("vix_caps") if bands is True else bands
        self.lead_regime: list = []        # regime of the first symbol, for the scaling check
        self.cash = float(self.bt["account"])
        self.shares = {s: 0.0 for s in self.syms}
        self.basis = {s: 0.0 for s in self.syms}
        self.opts: list[Opt] = []
        self.last_put: dict = {}       # sym -> (day index, strike, expected move)
        self.last_call_day: dict = {}
        self.cf = {s: 0.0 for s in self.syms}   # per-name cash flow (P&L attribution)
        self.stats = {k: 0 for k in ("puts_sold", "calls_sold", "closed_profit", "closed_21dte", "closed_21dte_itm", "rolled",
                                     "rolled_puts", "rolled_calls",
                                     "assigned", "called_away", "expired_worthless", "spread_loss", "breaker_days")}
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
        m = bs_price(S, o.strike, T, skew_iv(atm, S, o.strike, self._slope(o.sym)), o.cp, r)
        if o.wing is not None:
            m -= bs_price(S, o.wing, T, skew_iv(atm, S, o.wing, self._slope(o.sym)), o.cp, r)
        return m

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
                by_sym[o.sym] += o.collateral
        return by_sym, sum(by_sym.values())

    def _room(self, sym: str, by_sym: dict, total: float, E: float) -> float:
        bucket = self.meta["bucket"].get(sym)
        u = self.rules
        name_cap = (u["per_name_cap_index"] if sym in self.meta["index_syms"] else u["per_name_cap"])
        name_cap = self._cap(sym, self._cap("per_name", name_cap)) / 100
        bcap = self._cap(bucket, u["universe"].get(bucket, {}).get("cap", 100)) / 100
        tcap = self._cap("total", u["total_deployed_cap"]) / 100
        if self.vix_bands:
            vc = vix_cap(self.vix[self.i], self.vix_bands)
            if vc is not None:
                tcap = vc / 100
        in_bucket = sum(v for s, v in by_sym.items() if self.meta["bucket"].get(s) == bucket)
        collateral = sum(o.collateral for o in self.opts if o.cp == "P")
        free_cash = self.cash - collateral
        return min(name_cap * E - by_sym[sym], bcap * E - in_bucket, tcap * E - total, free_cash)

    # --- main loop
    def run(self) -> "Sim":
        rules, th, bt = self.rules, self.rules["thresholds"], self.bt
        mgmt = rules["management"]
        tp = self.v.get("take_profit_pct", mgmt["take_profit_pct"]) / 100
        decide_dte = self.v.get("decide_dte", mgmt["decide_dte"])
        dte = bt.get("dte", rules["strikes"]["dte_target"])
        mode = self.v["mode"]
        cb = bt.get("circuit_breakers") or {}
        prev_d = None
        for i, d in enumerate(self.cal):
            self.i = i
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
                self._maybe_put(s, row, d, i, E, prices, r, self._dte(row["regime"], dte), size_mult, index_only, mode)
                self._maybe_call(s, row, d, i, E, r, self._dte(row["regime"], dte), mode)

            E = self._equity(d, prices, atms, r)
            by_sym, total = self._exposure(prices)
            self.equity.append(E)
            self.deployed.append(total / E if E > 0 else 0.0)
            self.short_open.append(bool(self.opts))
            self.in_shares.append(sum(self.shares[s] * prices[s] for s in self.syms) / E if E > 0 else 0.0)
            lead = rows.get(self.syms[0]) if self.syms else None
            self.lead_regime.append(lead["regime"] if lead is not None else None)
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
                if o.wing is not None:                 # spread: cash-settled at the width it lost
                    loss = (max(o.strike - S, 0.0) - max(o.wing - S, 0.0)) * o.qty
                    self.cash -= loss
                    self.cf[o.sym] -= loss
                    self.stats["spread_loss" if loss > 0 else "expired_worthless"] += 1
                elif itm and o.cp == "P":
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
            decide = left <= decide_dte and o.dte0 > decide_dte
            if mark <= (1 - tp) * o.entry_mid:
                self._buy_back(o, mark)
                self.stats["closed_profit"] += 1
            elif decide and itm and self._roll_itm_ok(o, i):
                keep.append(self._roll_for_credit(o, mark, S, atm, d, r) or o)
            elif decide and not itm:
                self._buy_back(o, mark)
                self.stats["closed_21dte"] += 1
            elif decide and self.v.get("decide_itm", self.bt.get("decide_itm")) == "close":
                self._buy_back(o, mark)            # tastytrade: close every trade at 21 DTE, never take assignment
                self.stats["closed_21dte_itm"] += 1
            elif decide and self.v.get("decide_itm", self.bt.get("decide_itm")) == "roll" \
                    and o.wing is None and o.rolls < self.bt.get("max_rolls", 1):
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

    def _roll_itm_ok(self, o: Opt, i: int) -> bool:
        """'Roll until you're right': variant roll_itm = {puts, calls, max_rolls, call_regimes}."""
        ri = self.v.get("roll_itm")
        if not ri or o.wing is not None or o.rolls >= ri.get("max_rolls", 6):
            return False
        if o.cp == "P":
            return bool(ri.get("puts"))
        if not ri.get("calls"):
            return False
        regimes = ri.get("call_regimes")
        row = self.recs[o.sym][i]
        return not regimes or row["regime"] in regimes

    def _roll_for_credit(self, o: Opt, mark: float, S: float, atm: float, d, r: float) -> "Opt | None":
        """Buy back an ITM option and sell the same side `roll_itm.dte` days out at the most favourable strike
        (lower for puts, higher for calls) that still takes in at least the buyback cost. None (and
        nothing traded) when no strike gives a net credit; the option is then held to expiry."""
        ri = self.v["roll_itm"]
        dte = ri.get("dte", 45)
        T = dte / 365.0
        slope = self._slope(o.sym)
        cost = mark + max(mark * self._slip(o.sym), 0.01) + self._comm()

        def credit(K):
            mid = bs_price(S, K, T, skew_iv(atm, S, K, slope), o.cp, r)
            return mid - max(mid * self._slip(o.sym), 0.01) - self._comm(), mid

        if credit(o.strike)[0] < cost:
            return None
        step = 0.005 * S * (-1 if o.cp == "P" else 1)
        K = o.strike
        while 0 < K + step and credit(K + step)[0] >= cost:
            K += step
        cr, mid = credit(K)
        self.cash += (cr - cost) * o.qty
        self.cf[o.sym] += (cr - cost) * o.qty
        self.premium += cr * o.qty
        self.stats["rolled_" + ("puts" if o.cp == "P" else "calls")] += 1
        return Opt(o.sym, o.cp, K, o.qty, d, d + pd.Timedelta(days=dte), mid, o.rolls + 1, dte)

    def _assign(self, o: Opt, S: float):
        s = o.sym
        held = self.shares[s]
        self.basis[s] = ((self.basis[s] * held) + (o.strike - o.entry_mid) * o.qty) / (held + o.qty)
        self.shares[s] += o.qty
        self.cash -= o.strike * o.qty
        self.cf[s] -= o.strike * o.qty
        self.stats["assigned"] += 1

    def _buy_back(self, o: Opt, mark: float):
        legs = 2 if o.wing is not None else 1
        px = mark + legs * (max(mark * self._slip(o.sym), 0.01 if mark > 0.01 else 0.0) + self._comm())
        self.cash -= px * o.qty
        self.cf[o.sym] -= px * o.qty

    def _sell(self, sym, cp, K, qty, d, atm, r, dte, count=True, wing=None) -> Opt | None:
        S = self.cur_price[sym]
        T = dte / 365.0
        mid = bs_price(S, K, T, skew_iv(atm, S, K, self._slope(sym)), cp, r)
        if mid <= 0.0005 * S:
            return None
        px = mid - max(mid * self._slip(sym), 0.01) - self._comm()
        if wing is not None:
            wmid = bs_price(S, wing, T, skew_iv(atm, S, wing, self._slope(sym)), cp, r)
            mid -= wmid
            px -= wmid + max(wmid * self._slip(sym), 0.01) + self._comm()
        if px <= 0:
            return None
        o = Opt(sym, cp, K, qty, d, d + pd.Timedelta(days=dte), mid, dte0=dte, wing=wing)
        self.opts.append(o)
        self.cash += px * qty
        self.cf[sym] += px * qty
        self.premium += px * qty
        if count:
            self.stats["puts_sold" if cp == "P" else "calls_sold"] += 1
        return o

    def _dd_mult(self, s: str, i: int) -> float:
        """`size_by_dd` [[drawdown %, multiplier], ...]: start small, size up as the name falls (step function)."""
        bands = self.v.get("size_by_dd")
        if not bands or s not in self.size_dd:
            return 1.0
        dd = float(self.size_dd[s][i])
        m = bands[0][1]
        for lvl, mult in bands:
            if dd >= lvl:
                m = mult
        return float(m)

    def _dte(self, regime: str, default: int) -> int:
        d = self.v.get("dte")
        if d is None:
            return default
        return int(d.get(regime, default)) if isinstance(d, dict) else int(d)

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
        wing = None
        if self.v.get("put_wing_delta"):
            wing = strike_for_delta(S, T, atm, self.v["put_wing_delta"] / 100, "P", self._slope(s), r)
            if not 0 < wing < K:
                return
        want = self._entry_frac(s) * E * size_mult * self._dd_mult(s, i)   # spreads: entry_pct = max loss per trade
        by_sym, total = self._exposure(prices)
        room = self._room(s, by_sym, total, E)
        notional = min(want, room)
        if notional < 0.5 * want or notional <= 0:
            return
        o = self._sell(s, "P", K, notional / (K - wing if wing else K), d, atm, r, dte, wing=wing)
        if o:
            em_iv = max(atm, float(row["hv20"])) if s in self.rules.get("weekend_gap_names", []) else atm
            self.last_put[s] = (i, K, S * em_iv * math.sqrt(self.rules["sizing"]["ladder_dte"] / 365))

    def _maybe_call(self, s, row, d, i, E, r, dte, mode):
        th = self.rules["thresholds"]
        if self.shares[s] <= 1e-9:
            return
        cov = self.rules["momentum_max_call_coverage"] / 100 if s in self.rules["momentum_names"] else 1.0
        if self.v.get("call_coverage") is not None:
            cov = min(cov, self.v["call_coverage"] / 100)
        if self.v.get("call_regimes") and row["regime"] not in self.v["call_regimes"]:
            return
        covered = sum(o.qty for o in self.opts if o.sym == s and o.cp == "C")
        qty = self.shares[s] * cov - covered
        S = float(row["close"])
        if qty * S < 0.005 * E:
            return
        ivr, regime = float(row["ivr"]) if np.isfinite(row["ivr"]) else float("nan"), row["regime"]
        calls_mode = self.v.get("calls", "spike" if mode == "spike" else "always")
        if calls_mode not in ("spike", "always", "none"):
            raise ValueError(f"calls: {calls_mode!r} (expected spike, always or none)")
        if calls_mode == "none":          # puts only: assigned shares are held, never written against
            return
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
        sh = pd.Series(self.in_shares)
        rg = pd.Series(self.lead_regime)
        out["shares_by_regime_pct"] = {k: round(float(sh[rg == k].mean()) * 100, 1)
                                       for k in ("Low", "Mid", "High") if (rg == k).any()}
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
        # where the book stands on the last day: shares and put collateral per name, % of equity
        E_last = float(eq.iloc[-1]) if len(eq) else 0.0
        if E_last > 0:
            fp = self.final_prices
            out["final_pct"] = {s: {"shares": round(100 * self.shares[s] * fp[s] / E_last, 1),
                                    "puts": round(100 * sum(o.collateral for o in self.opts
                                                            if o.sym == s and o.cp == "P") / E_last, 1)}
                                for s in self.syms}
        out["equity_weekly"] = weekly(eq)
        out["_eq"] = eq
        return out


def _zero_cost_call(S: float, T: float, atm: float, slope: float, r: float, target: float) -> float:
    """Lowest call strike >= S whose premium is no more than `target` (the put it finances)."""
    lo, hi = S, S * 4
    if bs_price(S, lo, T, skew_iv(atm, S, lo, slope), "C", r) <= target:
        return lo
    for _ in range(60):
        mid = (lo + hi) / 2
        if bs_price(S, mid, T, skew_iv(atm, S, mid, slope), "C", r) > target:
            lo = mid
        else:
            hi = mid
    return hi


def run_hold(variant: dict, frames: dict, meta: dict, rates: pd.Series, rules: dict, start, end) -> dict:
    """Buy-and-hold at `weight`% (rest in T-bills), monthly rebalance. Weights: equal across eligible
    names, or `weights` {sym: %} renormalized over the eligible ones. `rotate` {lookback, top, abs}:
    each month hold only the `top` names with the best trailing `lookback`-day return, and only those
    beating T-bills over the same span when `abs` (dual momentum); otherwise T-bills.
    Defensive exit, checked at each monthly rebalance:
      `trend_sma`     a name closing below its N-day average gets its weight in T-bills (or `trend_to`)
                      until it closes back above
      `trend_falling` exit only while that average is also lower than 20 days earlier (true = every
                      name; a list = only those names, the rest use the plain exit)
      `trend_arm`     {symbols, high_within_days}: for those names an exit also needs the High regime
                      within the last N days (the market was stretched before it broke)
      `trend_to`      {symbols, lookback, top}: the exited weight goes to the defensive name(s) with the
                      best trailing `lookback`-day return, if beating T-bills; else T-bills
    `collar` {put_otm_pct, dte, roll_days, call, call_otm_pct, regimes}: a put `put_otm_pct` below on each
    holding, financed by a call (zero-cost strike unless `call_otm_pct`; `call: false` = puts only),
    re-struck every `roll_days`; new collars only while the name's regime is in `regimes` when given, and
    only on `symbols` when given."""
    bt = rules["backtest"]
    cal = rates.index[(rates.index >= start) & (rates.index <= end)]
    syms = [s for s in variant["symbols"] if s in frames]
    tt = variant.get("trend_to") or {}
    dsyms = [s for s in tt.get("symbols", []) if s in frames and s not in syms]
    allsyms = syms + dsyms
    w = variant.get("weight", 100) / 100
    # forward-filled: a missing bar for one name must not value the holding at zero
    closes_all = pd.DataFrame({s: frames[s]["close"] for s in allsyms}).ffill()
    closes = closes_all.reindex(cal)
    held = {s: 0.0 for s in allsyms}
    weights = variant.get("weights")
    rot = variant.get("rotate")
    tsma = variant.get("trend_sma")
    arm = variant.get("trend_arm") or {}
    arm_syms = set(arm.get("symbols") or syms)
    arm_days = arm.get("high_within_days")
    tfall = variant.get("trend_falling")
    fall_syms = set(syms) if tfall is True else set(tfall or [])
    regs = pd.DataFrame({s: frames[s]["regime"] if "regime" in frames[s] else "Mid" for s in syms})
    col = variant.get("collar")
    if col:
        ivs = pd.DataFrame({s: frames[s]["iv"] for s in syms}).ffill().reindex(cal)
        regs_cal = regs.reindex(cal)
        vol_syms = meta.get("vol_index_syms") or set()
        liquid = set(bt.get("liquid_option_syms") or []) | set(meta.get("index_syms") or set())
    legs: list[dict] = []
    collar_flow, collar_days = 0.0, 0

    def term_slope(sym, days):
        # skew_slope is fitted to ~45-DTE options; longer expiries' skew flattens about as 1/sqrt(T)
        ref = bt.get("skew_term_days", 45)
        return bt["skew_slope"]["index" if sym in vol_syms else "stock"] * math.sqrt(ref / max(days, ref))

    def leg_px(o, S, iv, d, r):
        days = max((o["exp"] - d).days, 0)
        return bs_price(S, o["K"], days / 365.0, skew_iv(iv, S, o["K"], term_slope(o["s"], days)), o["cp"], r)

    def leg_slip(o, mid):
        c = bt["costs"]
        pct = c["slippage_pct_index"] if o["s"] in liquid else c["slippage_pct_stock"]
        return abs(o["qty"]) * (max(mid * pct / 100, 0.01) + c["per_contract"] / 100)

    months_in = {s: 0 for s in allsyms}
    months_cash = 0
    off_now: set = set()
    cash = float(bt["account"])
    eq, prev_d, last_month = [], None, None
    min_bars = bt.get("min_history_days", 260)
    for d in cal:
        r = float(rates.loc[d])
        if prev_d is not None:
            cash *= 1 + r * (d - prev_d).days / 365.0
        prev_d = d
        px = {s: closes.at[d, s] for s in allsyms}
        px_ok = {s: p for s, p in px.items() if np.isfinite(p) and p > 0}
        if col and legs:
            # settle expired legs, close legs due for a re-strike
            keep = []
            for o in legs:
                S, iv = px_ok.get(o["s"]), ivs.at[d, o["s"]]
                if S is None or not np.isfinite(iv):
                    keep.append(o)
                    continue
                if d >= o["exp"]:
                    flow = o["qty"] * max(0.0, (o["K"] - S) if o["cp"] == "P" else (S - o["K"]))
                elif (d - o["opened"]).days >= col.get("roll_days", 91):
                    mid = leg_px(o, S, iv, d, r)
                    flow = o["qty"] * mid - leg_slip(o, mid)
                else:
                    keep.append(o)
                    continue
                cash += flow
                collar_flow += flow
            legs = keep

        def leg_value():
            tot = 0.0
            for o in legs:
                S, iv = px_ok.get(o["s"]), ivs.at[d, o["s"]]
                if S is not None and np.isfinite(iv):
                    tot += o["qty"] * leg_px(o, S, iv, d, r)
            return tot

        E = cash + sum(held[s] * px_ok.get(s, 0.0) for s in allsyms) + (leg_value() if legs else 0.0)
        if d.month != last_month:
            last_month = d.month
            elig = [s for s in syms if s in px_ok
                    and frames[s]["close"].loc[meta["first_date"][s]:d].count() >= min_bars]
            elig_all = elig
            off: list = []
            dest: list = []
            if tsma and elig:
                past = closes_all.loc[:d]
                for s in elig:
                    p = past[s].dropna()
                    if len(p) < tsma or p.iloc[-1] >= p.iloc[-tsma:].mean():
                        continue
                    if s not in off_now:   # entering an exit; staying out needs only the close below
                        if s in fall_syms and len(p) >= tsma + 20 \
                                and p.iloc[-tsma:].mean() >= p.iloc[-tsma - 20:-20].mean():
                            continue
                        if arm_days and s in arm_syms and not (regs[s].loc[:d].iloc[-arm_days:] == "High").any():
                            continue
                    off.append(s)
                off_now = set(off)
                if off and dsyms:
                    lb = tt.get("lookback", 126)
                    rf = float(rates.loc[:d].iloc[-lb:].mean()) * lb / 252
                    mom = {}
                    for s in dsyms:
                        p = past[s].dropna()
                        if s in px_ok and len(p) > lb:
                            mom[s] = p.iloc[-1] / p.iloc[-1 - lb] - 1
                    dest = sorted((s for s in mom if mom[s] > rf), key=mom.get, reverse=True)[:tt.get("top", 1)]
                for s in elig:
                    if s not in off:
                        months_in[s] += 1
                for s in dest:
                    months_in[s] += len(off) / len(dest)
                if not dest:
                    months_cash += len(off)
                elig = [s for s in elig if s not in off]
            if rot and elig:
                lb = rot.get("lookback", 252)
                past = closes_all.loc[:d]
                mom = {s: past[s].iloc[-1] / past[s].iloc[-1 - lb] - 1 for s in elig if past[s].count() > lb}
                rf = float(rates.loc[:d].iloc[-lb:].mean()) * lb / 252 if len(rates.loc[:d]) else 0.0
                ranked = sorted(mom, key=mom.get, reverse=True)[:rot.get("top", 1)]
                elig = [s for s in ranked if not rot.get("abs", True) or mom[s] > rf]
                for s in elig:
                    months_in[s] += 1
                if not elig:
                    months_cash += 1
            for s in allsyms:
                if held[s] and s in px_ok:
                    cash += held[s] * px_ok[s]
                    held[s] = 0.0
            base = elig_all if tsma else elig
            if weights:
                tot = sum(weights.get(s, 0) for s in base) or 1.0
                wts = {s: weights.get(s, 0) / tot for s in base}
            else:
                wts = {s: 1 / len(base) for s in base} if base else {}
            for s in elig:
                tgt = E * w * wts[s]
                held[s] = tgt / px_ok[s]
                cash -= tgt
            if dest:
                off_w = sum(wts.get(s, 0) for s in off)
                for s in dest:
                    tgt = E * w * off_w / len(dest)
                    held[s] = tgt / px_ok[s]
                    cash -= tgt
            if col and legs:
                # collars follow the rebalanced holding: resized to the new share count, and a name sold
                # out of (trend exit, rotation) takes its collar with it
                keep = []
                for o in legs:
                    S, iv = px_ok.get(o["s"]), ivs.at[d, o["s"]]
                    if S is None or not np.isfinite(iv):
                        keep.append(o)
                        continue
                    new_qty = held.get(o["s"], 0.0) * (1 if o["qty"] > 0 else -1)
                    delta_q = o["qty"] - new_qty            # contracts to close (negative = add)
                    if abs(delta_q) > 1e-9:
                        mid = leg_px(o, S, iv, d, r)
                        flow = delta_q * mid - leg_slip({**o, "qty": delta_q}, mid)
                        cash += flow
                        collar_flow += flow
                        o["qty"] = new_qty
                    if abs(o["qty"]) > 1e-9:
                        keep.append(o)
                legs = keep
        if col:
            covered = {o["s"] for o in legs}
            regimes = col.get("regimes")
            col_syms = col.get("symbols") or syms
            for s in syms:
                S, iv = px_ok.get(s), ivs.at[d, s]
                if s not in col_syms or not held[s] or s in covered or S is None or not np.isfinite(iv) or iv <= 0:
                    continue
                if regimes and regs_cal.at[d, s] not in regimes:
                    continue
                dte = col.get("dte", 182)
                exp = d + pd.Timedelta(days=dte)
                slope = term_slope(s, dte)
                put = {"s": s, "cp": "P", "K": S * (1 - col.get("put_otm_pct", 10) / 100), "qty": held[s],
                       "exp": exp, "opened": d}
                new = [put]
                pmid = leg_px(put, S, iv, d, r)
                if col.get("call", True):
                    K = S * (1 + col["call_otm_pct"] / 100) if col.get("call_otm_pct") is not None else \
                        _zero_cost_call(S, dte / 365, iv, slope, r, pmid)
                    new.append({"s": s, "cp": "C", "K": K, "qty": -held[s], "exp": exp, "opened": d})
                for o in new:
                    mid = leg_px(o, S, iv, d, r)
                    flow = -o["qty"] * mid - leg_slip(o, mid)
                    cash += flow
                    collar_flow += flow
                legs += new
            collar_days += bool(legs)
        eq.append(cash + sum(held[s] * px_ok.get(s, 0.0) for s in allsyms) + (leg_value() if legs else 0.0))
    eqs = pd.Series(eq, index=cal)
    out = metrics(eqs, rates.reindex(cal), bt)
    out["avg_deployed_pct"] = round(w * 100, 1)
    if rot or tsma:
        n = max(sum(months_in.values()) + months_cash, 1)
        out["months_held_pct"] = {**{s: round(100 * c / n) for s, c in months_in.items()},
                                  "T-bills": round(100 * months_cash / n)}
    if col:
        yrs = max(len(eqs) / 252, 1e-9)
        open_val = 0.0
        if legs:
            d = cal[-1]
            for o in legs:
                S, iv = closes.at[d, o["s"]], ivs.at[d, o["s"]]
                if np.isfinite(S) and np.isfinite(iv):
                    open_val += o["qty"] * leg_px(o, S, iv, d, float(rates.loc[d]))
        out["collar_pnl_per_year_pct"] = round((collar_flow + open_val) / yrs / float(eqs.mean()) * 100, 2)
        out["collared_days_pct"] = round(100 * collar_days / max(len(eqs), 1))
    out["equity_weekly"] = weekly(eqs)
    out["_eq"] = eqs
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
    monthly = eq.groupby([eq.index.year, eq.index.month]).last()
    mret = monthly.pct_change().dropna()
    roll12 = eq.pct_change(TD).dropna()
    return {
        "start": eq.index[0].strftime("%Y-%m-%d"), "end": eq.index[-1].strftime("%Y-%m-%d"),
        "final": round(float(eq.iloc[-1])), "cagr_pct": round(cagr * 100, 2), "vol_pct": round(vol * 100, 1),
        "sharpe": round(sharpe, 2), "max_dd_pct": round(float(dd.min()) * 100, 1),
        "max_dd_date": trough.strftime("%Y-%m-%d"), "longest_underwater_days": longest,
        "worst_year_pct": min(full_years.values()) if full_years else None,
        "yearly_pct": yearly, "periods": periods,
        "positive_months_pct": round(float((mret > 0).mean()) * 100, 1) if len(mret) else None,
        "worst_12m_pct": round(float(roll12.min()) * 100, 1) if len(roll12) else None,
    }


# ---------------------------------------------------------------- orchestration

def resolve_symbols(spec, rules: dict) -> list[str]:
    if spec == "universe":
        return [u["symbol"] for u in universe(rules)]
    return list(spec)


def trend_states(close: pd.Series, sma_n: int = 200, slope_days: int = 20, neutral: float = 0.5) -> pd.Series:
    """KISS-style three-state trend signal per day: 1 above a rising N-day average, `neutral` when only
    one of (above, rising) holds, 0 below a falling one. NaN until the average exists."""
    sma = close.rolling(sma_n).mean()
    above = close > sma
    rising = sma > sma.shift(slope_days)
    out = np.where(above & rising, 1.0, np.where(above | rising, neutral, 0.0))
    return pd.Series(out, index=close.index).where(sma.shift(slope_days).notna())


def run_states(variant: dict, frames: dict, meta: dict, rates: pd.Series, rules: dict, start, end) -> dict:
    """Signal-scaled fixed weights, checked daily (42 Macro's KISS shape). Each name's exposure = weight x
    its trend state (`states`: {sma, slope_days, neutral}) x the regime multiplier; the rest earns T-bills.
    Signals use yesterday's close and trade at today's close (`lag_days`). A name is re-traded whenever its
    multiplier changes; everything is rebalanced to target monthly. `regime_vote` {symbols, halve, mult}:
    risk-off (a majority of `symbols` at state 0) scales the `halve` names by `mult` (default 0.5).
    Stock trades cost `stock_cost_bps` of notional."""
    bt = rules["backtest"]
    cal = rates.index[(rates.index >= start) & (rates.index <= end)]
    syms = [s for s in variant["symbols"] if s in frames]
    cfg = variant.get("states") or {}
    lag = cfg.get("lag_days", 1)
    cost = variant.get("stock_cost_bps", 5) / 1e4
    wts = variant.get("weights") or {s: 1 for s in syms}
    tot = sum(wts.get(s, 0) for s in syms) or 1.0
    w = {s: wts.get(s, 0) / tot * variant.get("weight", 100) / 100 for s in syms}
    closes = pd.DataFrame({s: frames[s]["close"] for s in syms}).ffill()

    def st(c):
        return trend_states(c.dropna(), cfg.get("sma", 200), cfg.get("slope_days", 20),
                            cfg.get("neutral", 0.5)).reindex(closes.index).ffill()
    states = pd.DataFrame({s: st(closes[s]) for s in syms}).shift(lag)
    rv = variant.get("regime_vote") or {}
    if rv:
        vote = pd.DataFrame({s: st(frames[s]["close"].reindex(closes.index).ffill()) for s in rv["symbols"]
                             if s in frames}).shift(lag)
        risk_off = (vote == 0).sum(axis=1) > vote.notna().sum(axis=1) / 2
    closes, states = closes.reindex(cal), states.reindex(cal)
    held = {s: 0.0 for s in syms}
    cur = {s: None for s in syms}
    cash = float(bt["account"])
    eq, prev_d, last_month = [], None, None
    invested: list = []
    trades = 0
    state_days = {s: {"full": 0, "half": 0, "out": 0} for s in syms}
    for d in cal:
        r = float(rates.loc[d])
        if prev_d is not None:
            cash *= 1 + r * (d - prev_d).days / 365.0
        prev_d = d
        px = {s: closes.at[d, s] for s in syms}
        ok = {s: p for s, p in px.items() if np.isfinite(p) and p > 0}
        E = cash + sum(held[s] * ok.get(s, 0.0) for s in syms)
        mult = {}
        for s in syms:
            m = states.at[d, s]
            m = 0.0 if not np.isfinite(m) else float(m)
            if rv and s in rv.get("halve", []) and bool(risk_off.get(d, False)):
                m *= rv.get("mult", 0.5)
            mult[s] = m
            state_days[s]["full" if m >= 0.99 else "out" if m <= 0.01 else "half"] += 1
        monthly = d.month != last_month
        last_month = d.month
        for s in syms:
            if s not in ok or not (monthly or mult[s] != cur[s]):
                continue
            tgt = E * w[s] * mult[s] / ok[s]
            dq = tgt - held[s]
            if abs(dq) * ok[s] > 1e-6 * E:
                cash -= dq * ok[s] + abs(dq) * ok[s] * cost
                held[s] = tgt
                trades += 1
            cur[s] = mult[s]
        inv = sum(held[s] * ok.get(s, 0.0) for s in syms)
        eq.append(cash + inv)
        invested.append(inv / eq[-1] if eq[-1] > 0 else 0.0)
    eqs = pd.Series(eq, index=cal)
    out = metrics(eqs, rates.reindex(cal), bt)
    n = max(len(cal), 1)
    out["avg_deployed_pct"] = round(100 * float(np.mean(invested)), 1)
    out["state_days_pct"] = {s: {k: round(100 * v / n) for k, v in sd.items()} for s, sd in state_days.items()}
    out["trades_per_year"] = round(trades / max(len(cal) / TD, 1e-9), 1)
    out["equity_weekly"] = weekly(eqs)
    out["_eq"] = eqs
    return out


def run_blend(v: dict, parts: dict, rates: pd.Series, bt: dict, start, end, dds: dict | None = None) -> dict:
    """Fixed-weight mix of other variants' daily equity curves (plus "tbills" at the cash yield),
    rebalanced to `weights` every `rebalance` ("M" monthly, "Q" quarterly, "Y" yearly; default M).
    Rebalancing is free: the parts are separate sleeves of one account, so moving cash between them
    costs nothing beyond what each sleeve already pays.
    `tilt` {k, max_mult}: rotate toward the laggards. At each rebalance a part's weight is scaled by
    (1 + k x its underlying's drawdown from the all-time high, as a fraction), capped at max_mult, then all
    weights renormalized; `dds` = {part: drawdown % series} supplied by the caller."""
    cal = rates.index[(rates.index >= start) & (rates.index <= end)]
    w = {k: float(x) for k, x in v["weights"].items()}
    tot = sum(w.values())
    w = {k: x / tot for k, x in w.items()}
    rets = {}
    for k in w:
        if k == "tbills":
            d = pd.Series(cal, index=cal).diff().dt.days.fillna(0)
            rets[k] = rates.reindex(cal).fillna(0) * d / 365.0
        else:
            rets[k] = parts[k].reindex(cal).ffill().pct_change().fillna(0.0)
    R = pd.DataFrame(rets).fillna(0.0)
    period = {"M": cal.to_period("M"), "Q": cal.to_period("Q"), "Y": cal.to_period("Y")}[v.get("rebalance", "M")]
    E = float(bt["account"])
    hold = {k: E * w[k] for k in w}
    eq = []
    prev = None
    tilt = v.get("tilt") or {}
    ddm = {k: dds[k].reindex(cal).ffill().fillna(0).to_numpy() for k in (dds or {}) if k in w}
    tilt_sum, tilt_n = {k: 0.0 for k in w}, 0

    def weights_at(i):
        if not tilt or not ddm:
            return w
        raw = {k: w[k] * min(1 + tilt.get("k", 1.0) * (ddm[k][i] / 100 if k in ddm else 0.0), tilt.get("max_mult", 3.0))
               for k in w}
        t = sum(raw.values()) or 1.0
        return {k: x / t for k, x in raw.items()}
    for i, d in enumerate(cal):
        if prev is not None and period[i] != prev:
            E = sum(hold.values())
            wt = weights_at(i - 1)              # yesterday's drawdowns: no look-ahead
            hold = {k: E * wt[k] for k in w}
            for k in w:
                tilt_sum[k] += wt[k]
            tilt_n += 1
        prev = period[i]
        if i:
            for k in hold:
                hold[k] *= 1 + float(R.iat[i, R.columns.get_loc(k)])
        eq.append(sum(hold.values()))
    eqs = pd.Series(eq, index=cal)
    out = metrics(eqs, rates.reindex(cal), bt)
    out["avg_deployed_pct"] = round(100 * (1 - w.get("tbills", 0.0)), 1)
    out["blend_weights_pct"] = {k: round(x * 100, 1) for k, x in w.items()}
    if tilt and tilt_n:
        out["avg_tilted_weights_pct"] = {k: round(100 * tilt_sum[k] / tilt_n, 1) for k in w}
    out["equity_weekly"] = weekly(eqs)
    out["_eq"] = eqs
    return out


def run_rolling(cfg: dict, names: list, run_named, cal: pd.DatetimeIndex) -> dict:
    """Start-date robustness: every variant re-run from each January (`first_year` on) for each window
    length in `years`; reports the median / worst / best CAGR, the worst max drawdown and how often the
    variant beat `benchmark` over the same window. Path-dependent strategies (a put wheel that keeps its
    assigned shares) can look very different depending on where a single backtest starts."""
    out = {"years": cfg.get("years", [3, 5]), "benchmark": cfg.get("benchmark"), "variants": {}}
    last = cal[-1]
    for n_years in out["years"]:
        starts = []
        y = int(cfg.get("first_year", cal[0].year))
        while True:
            jan = cal[cal >= pd.Timestamp(f"{y}-01-01")]
            if not len(jan):
                break
            s0 = jan[0]
            e0 = s0 + pd.DateOffset(years=n_years)
            if e0 > last:
                break
            starts.append((s0, cal[cal <= e0][-1]))
            y += 1
        for s0, e0 in starts:
            memo: dict = {}
            bench = cfg.get("benchmark")
            b = run_named(bench, s0, e0, memo)["cagr_pct"] if bench else None
            for n in names:
                r = run_named(n, s0, e0, memo)
                if r["start"] > (s0 + pd.Timedelta(days=10)).strftime("%Y-%m-%d"):
                    continue                  # the variant starts later (e.g. bitcoin from 2015)
                rec = out["variants"].setdefault(n, {}).setdefault(str(n_years), [])
                rec.append({"start": r["start"], "cagr": r["cagr_pct"], "max_dd": r["max_dd_pct"], "bench": b})
            print(f"rolling {n_years}y from {s0.date()}: done", flush=True)
    summary = {}
    for n, by_len in out["variants"].items():
        summary[n] = {}
        for k, rows in by_len.items():
            c = np.array([x["cagr"] for x in rows])
            beat = [x["cagr"] > x["bench"] for x in rows if x["bench"] is not None]
            summary[n][k] = {"windows": len(rows), "median": round(float(np.median(c)), 1),
                             "worst": round(float(c.min()), 1), "best": round(float(c.max()), 1),
                             "worst_dd": round(min(x["max_dd"] for x in rows), 1),
                             "beat_bench_pct": round(100 * sum(beat) / len(beat)) if beat else None,
                             "worst_start": rows[int(c.argmin())]["start"]}
    out["summary"] = summary
    return out


def run(rules: dict, cache: Path | None = None, out_dir: Path | None = None) -> dict:
    bt = rules["backtest"]
    uni = universe(rules)
    bucket = {u["symbol"]: u["bucket"] for u in uni}
    index_syms = set(rules["universe"].get("Index", {}).get("core", []) or []) | set(
        rules["universe"].get("Index", {}).get("opportunistic", []) or [])
    vol_map = dict(bt.get("vol_index", {}))
    variants = bt["variants"]
    syms = sorted({s for v in variants for s in resolve_symbols(v.get("symbols", []), rules)}
                  | {s for v in variants for s in (v.get("trend_to") or {}).get("symbols", [])}
                  | {s for v in variants for s in (v.get("regime_vote") or {}).get("symbols", [])}
                  | set(bt.get("correlation_symbols") or []))
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
            "vix": hists["_VIX"]["close"] if "_VIX" in hists else None,
            "vol_index_syms": {s for s in vol_map if vol_map[s] in hists},
            "first_date": {s: hists[s].index[0] for s in syms if s in hists}}

    corr_syms = [s for s in (bt.get("correlation_symbols") or []) if s in hists]
    corr = {}
    if corr_syms:
        m = pd.DataFrame({s: hists[s]["close"] for s in corr_syms})
        m = m[m.index >= pd.Timestamp(bt.get("correlation_start", "2015-10-01"))]
        mret = m.groupby([m.index.year, m.index.month]).last().pct_change(fill_method=None)
        c = mret.corr(min_periods=24).round(2)
        y22 = {s: round(float(m[s].loc["2022"].dropna().iloc[-1] / m[s].loc["2021"].dropna().iloc[-1] - 1) * 100, 1)
               for s in corr_syms if m[s].loc["2021"].notna().any() and m[s].loc["2022"].notna().any()}
        corr = {"symbols": corr_syms, "matrix": c.where(c.notna(), None).values.tolist(), "y2022": y22,
                "start": bt.get("correlation_start", "2015-10-01")}
        print("correlations (monthly returns since " + corr["start"] + "):", flush=True)
        print(c.to_string(), flush=True)
        print("2022 returns:", y22, flush=True)

    results = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "data": info, "correlations": corr,
               "cash_yield": rate_src, "stock_iv_mult": base_mult, "windows": {}}
    by_name = {v["name"]: v for v in variants}

    def run_one(v: dict, m: float, vs, end_) -> dict:
        """One (non-blend) variant at one stock-IV multiple over [vs, end_]."""
        fr = frames_by_mult[m]
        if v["mode"] == "hold" and v.get("states") is not None:
            return run_states(v, fr, meta, rates, rules, vs, end_)
        if v["mode"] == "hold":
            return run_hold(v, fr, meta, rates, rules, vs, end_)
        if v["mode"] == "target":
            from .target import Target
            sym = v["symbols"][0]
            slope = bt["skew_slope"]["index" if sym in meta["vol_index_syms"] else "stock"]
            return Target({**v, "index": sym in meta["index_syms"]}, fr[sym], rates, rules, vs, end_, slope).run().result()
        if v["mode"] == "multi":
            from .multi import Multi
            slopes = {s: bt["skew_slope"]["index" if s in meta["vol_index_syms"] else "stock"] for s in v["symbols"]}
            liquid = set(bt.get("liquid_option_syms") or []) | meta["index_syms"]
            return Multi(v, fr, rates, rules, vs, end_, slopes, liquid).run().result()
        if v["mode"] == "sleeve":
            from .sleeve import Sleeve
            sym = v["symbols"][0]
            slope = bt["skew_slope"]["index" if sym in meta["vol_index_syms"] else "stock"]
            return Sleeve(v, fr[sym], rates, rules, vs, end_, slope).run().result()
        if v["mode"] == "pmcc":
            from .pmcc import PMCC
            sym = v["symbols"][0]
            return PMCC(v, fr[sym], rates, rules, vs, end_, bt["skew_slope"]["index"]).run().result()
        return Sim(v, fr, meta, rates, rules, vs, end_).run().result()

    def run_named(name: str, start_, end_, cache_: dict) -> dict:
        """Base-multiple result for a variant (blends included), memoised per window."""
        if name in cache_:
            return cache_[name]
        v = by_name[name]
        vs = max(start_, pd.Timestamp(v["start"])) if v.get("start") else start_
        if vs >= end_ - pd.Timedelta(days=60):          # the variant's history begins after this window
            cache_[name] = {"start": "9999-12-31", "cagr_pct": float("nan"), "max_dd_pct": float("nan")}
            return cache_[name]
        if v["mode"] == "blend":
            parts = {c: (None if c == "tbills" else run_named(c, start_, end_, cache_)["_eq"]) for c in v["weights"]}
            dds = None
            if v.get("tilt"):
                dds = {}
                for c in v["weights"]:
                    if c == "tbills":
                        continue
                    sym = resolve_symbols(by_name[c]["symbols"], rules)[0]
                    cl = frames_by_mult[base_mult][sym]["close"].dropna()
                    dds[c] = (1 - cl / cl.cummax()) * 100
            res = run_blend(v, parts, rates, bt, vs, end_, dds)
        else:
            v = {**v, "symbols": resolve_symbols(v["symbols"], rules)}
            res = run_one(v, base_mult, vs, end_)
        cache_[name] = res
        return res

    for wname, w in bt["windows"].items():
        start = pd.Timestamp(w["start"])
        end = pd.Timestamp(w.get("end") or cal[-1])
        wres = {"start": str(start.date()), "end": str(end.date()), "label": w.get("label", wname), "variants": {}}
        memo: dict = {}
        for v in variants:
            if v["mode"] == "blend":
                run_mults = [base_mult]
                uses_stock_iv = False
            else:
                v = {**v, "symbols": resolve_symbols(v["symbols"], rules)}
                uses_stock_iv = any(s not in meta["vol_index_syms"] for s in v["symbols"])
                no_options = v["mode"] == "hold" or (v["mode"] in ("target", "multi") and v.get("exec") == "stock")
                run_mults = (mults if (uses_stock_iv and not no_options) else [base_mult])
            for m in run_mults:
                key = v["name"] if m == base_mult else f"{v['name']}@{m:g}"
                vs = max(start, pd.Timestamp(v["start"])) if v.get("start") else start
                res = dict(run_named(v["name"], start, end, memo) if m == base_mult else run_one(v, m, vs, end))
                res.pop("_eq", None)
                res["label"] = v.get("label", v["name"]) + ("" if m == base_mult else f" (stock IV {m:g}x HV)")
                res["stock_iv_mult"] = m if uses_stock_iv else None
                if m != base_mult:
                    res.pop("equity_weekly", None)
                wres["variants"][key] = res
                if res.get("shares_monthly") and "@" not in key and v["symbols"][0] == "MSTR":
                    sm = res["shares_monthly"]
                    path = " ".join(f"{k[2:]}:{sm[k]}" for k in sm if "2021-01" <= k <= "2023-06")
                    print(f"{wname:7s} {key:22s} shares% by month 2021-01..2023-06: {path}", flush=True)
                print(f"{wname:7s} {key:22s} CAGR {res['cagr_pct']:6.2f}%  maxDD {res['max_dd_pct']:6.1f}%  "
                      f"Sharpe {res['sharpe']:5.2f}  deployed {res.get('avg_deployed_pct', 0):5.1f}%"
                      + (f"  puts/yr {res['puts_per_year']}" if "puts_per_year" in res else ""), flush=True)
        results["windows"][wname] = wres

    roll = bt.get("rolling") or {}
    if roll.get("variants"):
        results["rolling"] = run_rolling(roll, [n for n in roll["variants"] if n in by_name], run_named, cal)
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
        scal = [f"{v['label']}: Low {v['shares_by_regime_pct'].get('Low', 0):.0f}% · "
                f"Mid {v['shares_by_regime_pct'].get('Mid', 0):.0f}% · High {v['shares_by_regime_pct'].get('High', 0):.0f}%"
                for k, v in w["variants"].items() if v.get("shares_by_regime_pct") and "@" not in k]
        if scal:
            lines += [f"Share of the account held as stock, by the first name's regime (scaling in at lows, out at highs):", ""]
            lines += [f"- {x}" for x in scal] + [""]
        rt = [(k, v) for k, v in w["variants"].items() if "months_held_pct" in v]
        if rt:
            lines += ["Rotation variants (share of months holding each):", ""]
            lines += [f"- {v['label']}: " + ", ".join(f"{s} {p}%" for s, p in v["months_held_pct"].items())
                      for k, v in rt] + [""]
        cl = [(k, v) for k, v in w["variants"].items() if "collar_pnl_per_year_pct" in v]
        if cl:
            lines += ["Collar variants (net option P&L per year as % of equity; share of days with a collar on):", ""]
            lines += [f"- {v['label']}: collar P&L {v['collar_pnl_per_year_pct']:+.2f}%/yr, collared "
                      f"{v['collared_days_pct']}% of days" for k, v in cl] + [""]
        mb = [(k, v) for k, v in w["variants"].items() if "avg_weights_pct" in v and "@" not in k]
        if mb:
            lines += ["Multi-asset core variants (average weights; option premium and stock turnover per year, % of equity):", ""]
            for k, v in mb:
                st = v["stats"]
                wts = " · ".join(f"{s} {x:.0f}%" for s, x in v["avg_weights_pct"].items())
                lines.append(f"- {v['label']}: {wts}; premium {v['premium_per_year_pct']:.1f}%/yr, "
                             f"stock turnover {v['turnover_per_year_pct']:.0f}%/yr, {st['puts_sold']} puts / "
                             f"{st['calls_sold']} calls, assigned {st['assigned']}, called away {st['called_away']}; "
                             f"positive months {v['positive_months_pct']:.0f}%, worst 12 months {v['worst_12m_pct']:+.1f}%")
            lines.append("")
        tg = [(k, v) for k, v in w["variants"].items() if "shares_by_drawdown_pct" in v and "@" not in k]
        if tg:
            lines += ["Target-allocation variants (shares held by distance below the high; consistency = % of "
                      "positive months and the worst 12-month return):", ""]
            for k, v in tg:
                b = " · ".join(f"{n} {x:.0f}%" for n, x in v["shares_by_drawdown_pct"].items())
                st = v["stats"]
                extra = (f"premium {v['premium_per_year_pct']:.1f}%/yr, {st['puts_sold']} puts / {st['calls_sold']} calls, "
                         f"assigned {st['assigned']}, called away {st['called_away']}"
                         if st["puts_sold"] + st["calls_sold"] else f"stock turnover {v['turnover_per_year_pct']:.0f}%/yr")
                lines.append(f"- {v['label']}: in shares {b}; positive months {v['positive_months_pct']:.0f}%, "
                             f"worst 12 months {v['worst_12m_pct']:+.1f}%; {extra}")
            lines.append("")
        sl = [(k, v) for k, v in w["variants"].items() if "sleeve" in v]
        if sl:
            lines += ["Long-call sleeve variants (Deployed = average sleeve value as % of the account; payoff = "
                      "everything sold / everything paid; multiples per position):", ""]
            for k, v in sl:
                s_ = v["sleeve"]
                ex = ", ".join(f"{n} {c}" for n, c in s_["exits"].items())
                top = "; ".join(f"{t['opened']}→{t['closed']} {t['multiple']:.1f}x (stock {t['move_pct']:+.0f}%)"
                                for t in s_["top"])
                lines.append(f"- {v['label']}: {s_['trades']} positions, {s_['wins']} winners, payoff "
                             f"{s_['payoff_multiple']}x, median {s_['median_multiple']}x, best {s_['best_multiple']}x, "
                             f"net {s_['net_pnl']:+,}, avg {s_['avg_days']} days, in the market "
                             f"{v['in_market_pct']:.0f}% of days; exits: {ex}; best: {top}")
            lines.append("")
        pm = [(k, v) for k, v in w["variants"].items() if "call_pnl_per_year_pct" in v]
        if pm:
            lines += ["LEAP / poor man's covered call variants (Deployed = notional exposure; call P&L = premium "
                      "kept after buybacks, per year as % of equity):", ""]
            for k, v in pm:
                st = v["stats"]
                lines.append(f"- {v['label']}: in the market {v['in_market_pct']:.0f}% of days, call premium "
                             f"{v['premium_per_year_pct']:.1f}%/yr, call P&L {v['call_pnl_per_year_pct']:+.1f}%/yr, "
                             f"{st['entries']} entries; exits: target {st['exit_target']}, early {st['exit_half']}, "
                             f"stop {st['exit_stop']}, LEAP at 120 DTE {st['exit_dte']}")
            lines.append("")
        for key, v in w["variants"].items():
            if v.get("pnl_by_symbol") and "@" not in key and len(v["pnl_by_symbol"]) > 1:
                parts = ", ".join(f"{s} {p / 1000:+,.0f}k" for s, p in v["pnl_by_symbol"].items())
                lines.append(f"- **{v['label']}** P&L by name (excl. interest): {parts}")
        bl = [(k, v) for k, v in w["variants"].items() if "blend_weights_pct" in v]
        if bl:
            lines += ["Blends (fixed weights of other variants, rebalanced monthly):", ""]
            lines += [f"- {v['label']}: " + " · ".join(f"{n} {x:.0f}%" for n, x in v["blend_weights_pct"].items())
                      for k, v in bl] + [""]
        lines.append("")
    ro = res.get("rolling") or {}
    if ro.get("summary"):
        labels = {k: v["label"] for w in res["windows"].values() for k, v in w["variants"].items()}
        lines += ["## Start-date robustness (re-run from every January)", "",
                  f"Each variant re-run from each January for {' and '.join(str(y) for y in ro['years'])} years. "
                  f"Beat = share of windows with a higher CAGR than {labels.get(ro.get('benchmark'), ro.get('benchmark'))}.", ""]
        for y in ro["years"]:
            lines += [f"### {y}-year windows", "", "| Variant | Windows | Median CAGR | Worst | Best | Worst max DD | Beat | Worst start |",
                      "|---|---|---|---|---|---|---|---|"]
            for n, by_len in ro["summary"].items():
                r = by_len.get(str(y))
                if r:
                    beat = "–" if r["beat_bench_pct"] is None else f"{r['beat_bench_pct']}%"
                    lines.append(f"| {labels.get(n, n)} | {r['windows']} | {r['median']:.1f}% | {r['worst']:.1f}% | "
                                 f"{r['best']:.1f}% | {r['worst_dd']:.1f}% | {beat} | {r['worst_start']} |")
            lines.append("")
    cr = res.get("correlations") or {}
    if cr.get("symbols"):
        ss = cr["symbols"]
        lines += [f"## Correlations (monthly returns since {cr['start']}) and 2022 returns", "",
                  "| | " + " | ".join(ss) + " | 2022 |", "|---|" + "---|" * (len(ss) + 1)]
        for s, row in zip(ss, cr["matrix"]):
            cells = " | ".join("–" if x is None else f"{x:.2f}" for x in row)
            lines.append(f"| {s} | {cells} | {cr['y2022'].get(s, '–')}% |")
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
    ap.add_argument("--only", help="comma-separated variant names to run (local iteration; pair with --out)")
    ap.add_argument("--no-rolling", action="store_true", help="skip the start-date robustness runs")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    rules = load_rules(args.rules)
    if args.no_rolling:
        rules["backtest"].pop("rolling", None)
    if args.only:
        names = set(args.only.split(","))
        allv = {v["name"]: v for v in rules["backtest"]["variants"]}
        todo = list(names)
        while todo:                                   # blends need their components
            v = allv.get(todo.pop())
            for c in (v or {}).get("weights", {}) if (v or {}).get("mode") == "blend" else []:
                if c != "tbills" and c not in names:
                    names.add(c)
                    todo.append(c)
        ro = rules["backtest"].get("rolling") or {}
        if ro.get("variants"):
            ro["variants"] = [n for n in ro["variants"] if n in names]
            if ro.get("benchmark"):
                names.add(ro["benchmark"])
        rules["backtest"]["variants"] = [v for v in rules["backtest"]["variants"] if v["name"] in names]
        missing = names - {v["name"] for v in rules["backtest"]["variants"]}
        if missing:
            ap.error(f"unknown variants: {', '.join(sorted(missing))}")
    res = run(rules, args.cache, args.out)
    print(report(res, rules))
    return 0


if __name__ == "__main__":
    sys.exit(main())
