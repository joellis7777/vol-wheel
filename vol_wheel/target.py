"""Target-allocation scaling (Jordan, 2026-10-12): hold more shares the further price is below its
high, more cash near highs, and move toward that target either by trading the stock or with laddered
options. One underlying.

Target share % of the account = linear interpolation of `alloc` ([[drawdown % from the high, share
%], ...]) at today's drawdown from the running high. Execution:
  stock   - buy/sell shares toward the target whenever the gap exceeds `band_pct` of the account
  options - while below target, sell cash-secured puts in slices of `slice_pct` of the account (one
            per `every_days`, plus an extra slice on a down-spike) until open puts cover the gap; while
            above target, sell calls on slices of the excess shares (extra slice on an up-spike), never
            on the core position. Each new slice is struck off today's price, so strikes ladder with
            the move. Puts/calls: 45 DTE at the regime deltas, closed at 50% profit; at 21 DTE closed
            if OTM, else held to expiry so assignment moves the account toward the target.
Cash earns the T-bill yield. Options are Black-Scholes on the backtest's IV (VXN-based for QQQ,
modelled for single stocks).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .backtest import bs_price, metrics, skew_iv, strike_for_delta, weekly


def target_fraction(dd_pct: float, alloc: list) -> float:
    """dd_pct = drawdown from the high in % (positive). alloc = [[dd %, share %], ...]."""
    pts = sorted(alloc)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return float(np.interp(dd_pct, xs, ys)) / 100.0


class Target:
    def __init__(self, variant: dict, frame: pd.DataFrame, rates: pd.Series, rules: dict, start, end,
                 slope: float = 0.8):
        self.v, self.rules, self.bt = variant, rules, rules["backtest"]
        self.cfg = {**(self.bt.get("target") or {}), **variant}
        self.cal = rates.index[(rates.index >= start) & (rates.index <= end)]
        self.rates = rates.reindex(self.cal).to_numpy()
        close = frame["close"].dropna()
        lb = self.cfg.get("high_lookback_days")
        high = close.rolling(lb, min_periods=1).max() if lb else close.cummax()
        f = frame.copy()
        f["dd_pct"] = (1 - close / high) * 100
        sma = close.rolling(self.cfg.get("trend_sma", 200)).mean()
        f["downtrend"] = (close < sma) & (sma.diff(20) < 0)
        f = f.reindex(self.cal)
        f["close"] = f["close"].ffill()
        f["iv"] = f["iv"].ffill()
        f["dd_pct"] = f["dd_pct"].ffill().fillna(0)
        f["downtrend"] = f["downtrend"].astype("boolean").ffill().fillna(False).astype(bool)
        self.rows = f.to_dict("records")
        self.slope = slope
        self.cash = float(self.bt["account"])
        self.shares = 0.0
        self.opts: list[dict] = []
        self.premium = 0.0
        self.stock_traded = 0.0
        self.equity, self.in_shares, self.dd = [], [], []
        self.stats = {k: 0 for k in ("puts_sold", "calls_sold", "assigned", "called_away", "closed_profit",
                                     "closed_21dte", "stock_trades")}
        self.last_put_i = self.last_call_i = -10**9

    # --- helpers
    def _px(self, S, K, days, iv, cp, r):
        return bs_price(S, K, max(days, 0) / 365.0, skew_iv(iv, S, K, self.slope), cp, r)

    def _slip(self, mid):
        c = self.bt["costs"]
        pct = c["slippage_pct_index"] if self.cfg.get("index", True) else c["slippage_pct_stock"]
        return max(mid * pct / 100, 0.01) + c["per_contract"] / 100

    def _delta(self, side, regime):
        key = "put_delta" if side == "P" else "call_delta"
        d = self.cfg.get(key)
        if d is None:
            d = self.rules["strikes"][key][regime]
        elif isinstance(d, dict):
            d = d[regime]
        return d / 100

    def _opt_value(self, S, d, iv, r):
        return sum(o["qty"] * self._px(S, o["K"], (o["exp"] - d).days, iv, o["cp"], r) for o in self.opts)

    # --- option lifecycle
    def _manage(self, S, d, iv, r):
        mg = self.rules["management"]
        keep = []
        for o in self.opts:
            days = (o["exp"] - d).days
            itm = S < o["K"] if o["cp"] == "P" else S > o["K"]
            if days <= 0:
                if itm and o["cp"] == "P":
                    self.shares += o["qty"]
                    self.cash -= o["K"] * o["qty"]
                    self.stats["assigned"] += 1
                elif itm:
                    self.shares -= o["qty"]
                    self.cash += o["K"] * o["qty"]
                    self.stats["called_away"] += 1
                continue
            mid = self._px(S, o["K"], days, iv, o["cp"], r)
            if mid <= (1 - mg["take_profit_pct"] / 100) * o["mid"] or (days <= mg["decide_dte"] and not itm):
                self.cash -= (mid + self._slip(mid)) * o["qty"]
                self.stats["closed_profit" if mid <= (1 - mg["take_profit_pct"] / 100) * o["mid"] else "closed_21dte"] += 1
                continue
            keep.append(o)
        self.opts = keep

    def _sell(self, cp, qty, S, d, iv, r, regime, delta=None):
        dte = self.cfg.get("dte", 45)
        K = strike_for_delta(S, dte / 365, iv, delta or self._delta(cp, regime), cp, self.slope, r)
        mid = self._px(S, K, dte, iv, cp, r)
        credit = mid - self._slip(mid)
        if credit <= 0 or qty <= 0:
            return
        self.cash += credit * qty
        self.premium += credit * qty
        self.opts.append({"cp": cp, "K": K, "qty": qty, "exp": d + pd.Timedelta(days=dte), "mid": mid})
        self.stats["puts_sold" if cp == "P" else "calls_sold"] += 1

    # --- loop
    def run(self) -> "Target":
        band = self.cfg.get("band_pct", 5) / 100
        slice_frac = self.cfg.get("slice_pct", 10) / 100
        every = self.cfg.get("every_days", 5)
        sigma = self.rules["thresholds"]["spike_sigma"]
        cost_bps = self.cfg.get("stock_cost_bps", 5) / 1e4
        prev = None
        for i, d in enumerate(self.cal):
            row, r = self.rows[i], float(self.rates[i])
            S, iv = row["close"], row["iv"]
            if prev is not None:
                self.cash *= 1 + r * (d - prev).days / 365.0
            prev = d
            if not (np.isfinite(S) and np.isfinite(iv) and iv > 0):
                self.equity.append(self.equity[-1] if self.equity else self.cash)
                self.in_shares.append(self.in_shares[-1] if self.in_shares else 0.0)
                self.dd.append(0.0)
                continue
            self._manage(S, d, iv, r)
            E = self.cash + self.shares * S - self._opt_value(S, d, iv, r)
            frac = target_fraction(row["dd_pct"], self.cfg["alloc"])
            if self.cfg.get("trend_cap_pct") is not None and row["downtrend"]:
                # below a falling 200-day: don't scale in past the cap (a drawdown level isn't a low)
                frac = min(frac, self.cfg["trend_cap_pct"] / 100)
            tgt = frac * E
            cur = self.shares * S
            regime = row.get("regime") if isinstance(row.get("regime"), str) else "Mid"
            if self.cfg.get("exec", "options") == "stock":
                if abs(tgt - cur) > band * E:
                    dq = (tgt - cur) / S
                    self.shares += dq
                    self.cash -= dq * S + abs(dq) * S * cost_bps
                    self.stock_traded += abs(dq * S)
                    self.stats["stock_trades"] += 1
            else:
                put_notional = sum(o["K"] * o["qty"] for o in self.opts if o["cp"] == "P")
                call_shares = sum(o["qty"] for o in self.opts if o["cp"] == "C")
                deficit = tgt - cur - put_notional
                free_cash = self.cash - put_notional
                down_spike = (row.get("down") or 0) >= sigma
                up_spike = (row.get("up") or 0) >= sigma
                if deficit > band * E and (i - self.last_put_i >= every or down_spike):
                    notional = min(slice_frac * E, deficit, free_cash)
                    if notional > 0.01 * E:
                        dte = self.cfg.get("dte", 45)
                        K = strike_for_delta(S, dte / 365, iv, self._delta("P", regime), "P", self.slope, r)
                        self._sell("P", notional / K, S, d, iv, r, regime)
                        self.last_put_i = i
                excess = cur - tgt - call_shares * S
                cc = self.cfg.get("core_calls")
                if cc and excess <= band * E and regime in cc.get("regimes", ["Low"]) \
                        and call_shares < self.shares * cc.get("max_pct", 25) / 100 and i - self.last_call_i >= every:
                    # income calls on part of the core while price consolidates at the lows; the premium
                    # stays in cash and funds more puts through the target
                    qty = min(slice_frac * E / S, self.shares * cc.get("max_pct", 25) / 100 - call_shares)
                    if qty * S > 0.01 * E:
                        self._sell("C", qty, S, d, iv, r, regime, delta=cc.get("delta", 10) / 100)
                        self.last_call_i = i
                        self.stats["core_calls"] = self.stats.get("core_calls", 0) + 1
                if excess > band * E and (i - self.last_call_i >= every or up_spike):
                    qty = min(slice_frac * E, excess) / S
                    qty = min(qty, self.shares - call_shares)
                    if qty * S > 0.01 * E:
                        self._sell("C", qty, S, d, iv, r, regime)
                        self.last_call_i = i
            E = self.cash + self.shares * S - self._opt_value(S, d, iv, r)
            self.equity.append(E)
            self.in_shares.append(self.shares * S / E if E > 0 else 0.0)
            self.dd.append(row["dd_pct"])
        return self

    def result(self) -> dict:
        eq = pd.Series(self.equity, index=self.cal)
        out = metrics(eq, pd.Series(self.rates, index=self.cal), self.bt)
        yrs = max(len(eq) / 252, 1e-9)
        out["avg_deployed_pct"] = round(float(np.mean(self.in_shares)) * 100, 1)
        out["avg_shares_pct"] = out["avg_deployed_pct"]
        out["premium_per_year_pct"] = round(self.premium / yrs / float(eq.mean()) * 100, 2)
        out["turnover_per_year_pct"] = round(self.stock_traded / yrs / float(eq.mean()) * 100, 1)
        sh, dd = pd.Series(self.in_shares), pd.Series(self.dd)
        buckets = {"near high (<10%)": dd < 10, "10-30% down": (dd >= 10) & (dd < 30), ">30% down": dd >= 30}
        out["shares_by_drawdown_pct"] = {k: round(float(sh[m].mean()) * 100, 1) for k, m in buckets.items() if m.any()}
        out["stats"] = dict(self.stats)
        m = pd.Series(self.in_shares, index=self.cal).groupby([self.cal.year, self.cal.month]).mean()
        out["shares_monthly"] = {f"{y}-{mo:02d}": round(float(x) * 100) for (y, mo), x in m.items()}
        out["equity_weekly"] = weekly(eq)
        out["_eq"] = eq
        return out
