"""Multi-asset target weights rebalanced with options or stock (Jordan, 2026-10-12): a small core
(e.g. QQQ / GLD / bitcoin / XLE) held at fixed weights of the invested part of the account.

Start: buy every target with stock (the core is assumed already held). Then, daily per asset:
  stock   - trade the stock back to target when it drifts more than `band_pct` of the account
  options - below target: sell cash-secured puts in slices (`slice_pct` of the account, one per
            `every_days` plus one on a down-spike day) until open puts cover the gap; above target:
            sell calls on slices of the excess shares only (extra slice on an up-spike day). 45 DTE at
            the regime deltas, closed at 50% profit; at 21 DTE closed if OTM, else held so assignment
            does the rebalancing. `stock_gap_pct` (hybrid): any gap beyond it is traded in stock.
Options are Black-Scholes on the backtest IV (VXN/GVZ-based for QQQ/GLD, modelled elsewhere).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import bs_price, metrics, skew_iv, strike_for_delta, weekly


class Multi:
    def __init__(self, variant: dict, frames: dict, rates: pd.Series, rules: dict, start, end,
                 slopes: dict, liquid: set):
        self.v, self.rules, self.bt = variant, rules, rules["backtest"]
        self.cfg = {**(self.bt.get("target") or {}), **variant}
        self.cal = rates.index[(rates.index >= start) & (rates.index <= end)]
        self.rates = rates.reindex(self.cal).to_numpy()
        w = variant["weights"]
        self.syms = [s for s in w if s in frames]
        tot = sum(w[s] for s in self.syms)
        self.w = {s: w[s] / tot for s in self.syms}
        self.inv = self.cfg.get("invested_pct", 100) / 100
        self.rows, self.px = {}, {}
        for s in self.syms:
            f = frames[s].reindex(self.cal)
            f["iv"] = f["iv"].ffill()
            self.px[s] = frames[s]["close"].ffill().reindex(self.cal).to_numpy()
            self.rows[s] = f.to_dict("records")
        self.slopes, self.liquid = slopes, liquid
        self.cash = float(self.bt["account"])
        self.shares = {s: 0.0 for s in self.syms}
        self.opts: list[dict] = []
        self.premium = self.stock_traded = 0.0
        self.last_put = {s: -10**9 for s in self.syms}
        self.last_call = {s: -10**9 for s in self.syms}
        self.equity, self.weights_hist = [], []
        self.stats = {k: 0 for k in ("puts_sold", "calls_sold", "assigned", "called_away", "stock_trades")}

    def _px(self, s, S, K, days, iv, cp, r):
        return bs_price(S, K, max(days, 0) / 365.0, skew_iv(iv, S, K, self.slopes[s]), cp, r)

    def _slip(self, s, mid):
        c = self.bt["costs"]
        pct = c["slippage_pct_index"] if s in self.liquid else c["slippage_pct_stock"]
        return max(mid * pct / 100, 0.01) + c["per_contract"] / 100

    def _iv(self, s, i):
        iv = self.rows[s][i].get("iv")
        return iv if iv is not None and np.isfinite(iv) and iv > 0 else None

    def _delta(self, cp, regime):
        key = "put_delta" if cp == "P" else "call_delta"
        d = self.cfg.get(key) or self.rules["strikes"][key]
        return (d[regime] if isinstance(d, dict) else d) / 100

    def _opt_value(self, i, d, r):
        tot = 0.0
        for o in self.opts:
            iv = self._iv(o["s"], i) or o["iv"]
            tot += o["qty"] * self._px(o["s"], self.px[o["s"]][i], o["K"], (o["exp"] - d).days, iv, o["cp"], r)
        return tot

    def _trade_stock(self, s, value, S):
        dq = value / S
        self.shares[s] += dq
        self.cash -= dq * S + abs(dq * S) * self.cfg.get("stock_cost_bps", 5) / 1e4
        self.stock_traded += abs(dq * S)
        self.stats["stock_trades"] += 1

    def _manage(self, i, d, r):
        mg = self.rules["management"]
        keep = []
        for o in self.opts:
            s, S = o["s"], self.px[o["s"]][i]
            days = (o["exp"] - d).days
            itm = S < o["K"] if o["cp"] == "P" else S > o["K"]
            if days <= 0:
                if itm and o["cp"] == "P":
                    self.shares[s] += o["qty"]
                    self.cash -= o["K"] * o["qty"]
                    self.stats["assigned"] += 1
                elif itm:
                    self.shares[s] -= o["qty"]
                    self.cash += o["K"] * o["qty"]
                    self.stats["called_away"] += 1
                continue
            iv = self._iv(s, i)
            if iv is None:
                keep.append(o)
                continue
            mid = self._px(s, S, o["K"], days, iv, o["cp"], r)
            if mid <= (1 - mg["take_profit_pct"] / 100) * o["mid"] or (days <= mg["decide_dte"] and not itm):
                self.cash -= (mid + self._slip(s, mid)) * o["qty"]
                continue
            keep.append(o)
        self.opts = keep

    def _sell(self, s, cp, qty, S, iv, d, r, regime):
        dte = self.cfg.get("dte", 45)
        K = strike_for_delta(S, dte / 365, iv, self._delta(cp, regime), cp, self.slopes[s], r)
        mid = self._px(s, S, K, dte, iv, cp, r)
        credit = mid - self._slip(s, mid)
        if credit <= 0 or qty <= 0:
            return None
        self.cash += credit * qty
        self.premium += credit * qty
        self.opts.append({"s": s, "cp": cp, "K": K, "qty": qty, "exp": d + pd.Timedelta(days=dte), "mid": mid, "iv": iv})
        self.stats["puts_sold" if cp == "P" else "calls_sold"] += 1
        return K

    def run(self) -> "Multi":
        band = self.cfg.get("band_pct", 2) / 100
        slice_frac = self.cfg.get("slice_pct", 5) / 100
        every = self.cfg.get("every_days", 5)
        sigma = self.rules["thresholds"]["spike_sigma"]
        gap_cap = self.cfg.get("stock_gap_pct")
        exec_mode = self.cfg.get("exec", "options")
        prev = None
        for i, d in enumerate(self.cal):
            r = float(self.rates[i])
            if prev is not None:
                self.cash *= 1 + r * (d - prev).days / 365.0
            prev = d
            self._manage(i, d, r)
            E = self.cash + sum(self.shares[s] * self.px[s][i] for s in self.syms if np.isfinite(self.px[s][i])) \
                - self._opt_value(i, d, r)
            live = [s for s in self.syms if np.isfinite(self.px[s][i]) and self.px[s][i] > 0]
            wsum = sum(self.w[s] for s in live) or 1.0
            if i == 0:
                for s in live:
                    self._trade_stock(s, self.w[s] / wsum * self.inv * E, self.px[s][i])
            else:
                put_notional = {s: 0.0 for s in self.syms}
                call_qty = {s: 0.0 for s in self.syms}
                for o in self.opts:
                    if o["cp"] == "P":
                        put_notional[o["s"]] += o["K"] * o["qty"]
                    else:
                        call_qty[o["s"]] += o["qty"]
                for s in live:
                    S = self.px[s][i]
                    tgt = self.w[s] / wsum * self.inv * E
                    cur = self.shares[s] * S
                    row = self.rows[s][i]
                    if exec_mode == "stock":
                        if abs(tgt - cur) > band * E:
                            self._trade_stock(s, tgt - cur, S)
                        continue
                    if gap_cap is not None and abs(tgt - cur) > gap_cap / 100 * E:
                        # hybrid: the part of a big gap beyond the cap is traded in stock
                        excess_gap = abs(tgt - cur) - gap_cap / 100 * E
                        self._trade_stock(s, excess_gap if tgt > cur else -min(excess_gap, cur - call_qty[s] * S), S)
                        cur = self.shares[s] * S
                    iv = self._iv(s, i)
                    if iv is None:
                        continue
                    regime = row.get("regime") if isinstance(row.get("regime"), str) else "Mid"
                    free_cash = self.cash - sum(put_notional.values())
                    deficit = tgt - cur - put_notional[s]
                    if deficit > band * E and (i - self.last_put[s] >= every or (row.get("down") or 0) >= sigma):
                        notional = min(slice_frac * E, deficit, free_cash)
                        if notional > 0.005 * E:
                            dte = self.cfg.get("dte", 45)
                            K = strike_for_delta(S, dte / 365, iv, self._delta("P", regime), "P", self.slopes[s], r)
                            if self._sell(s, "P", notional / K, S, iv, d, r, regime):
                                put_notional[s] += notional
                                self.last_put[s] = i
                    excess = cur - tgt - call_qty[s] * S
                    if excess > band * E and (i - self.last_call[s] >= every or (row.get("up") or 0) >= sigma):
                        qty = min(min(slice_frac * E, excess) / S, self.shares[s] - call_qty[s])
                        if qty * S > 0.005 * E and self._sell(s, "C", qty, S, iv, d, r, regime):
                            self.last_call[s] = i
            E = self.cash + sum(self.shares[s] * self.px[s][i] for s in self.syms if np.isfinite(self.px[s][i])) \
                - self._opt_value(i, d, r)
            self.equity.append(E)
            self.weights_hist.append({s: (self.shares[s] * self.px[s][i] / E if E > 0 and np.isfinite(self.px[s][i]) else 0.0)
                                      for s in self.syms})
        return self

    def result(self) -> dict:
        eq = pd.Series(self.equity, index=self.cal)
        out = metrics(eq, pd.Series(self.rates, index=self.cal), self.bt)
        yrs = max(len(eq) / 252, 1e-9)
        wh = pd.DataFrame(self.weights_hist)
        out["avg_weights_pct"] = {s: round(float(wh[s].mean()) * 100, 1) for s in self.syms}
        out["avg_deployed_pct"] = round(float(wh.sum(axis=1).mean()) * 100, 1)
        out["premium_per_year_pct"] = round(self.premium / yrs / float(eq.mean()) * 100, 2)
        out["turnover_per_year_pct"] = round(self.stock_traded / yrs / float(eq.mean()) * 100, 1)
        out["stats"] = dict(self.stats)
        out["equity_weekly"] = weekly(eq)
        out["_eq"] = eq
        return out
