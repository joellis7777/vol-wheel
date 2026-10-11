"""Poor man's covered call simulation (Tom King's "dynamic" PMCC and comparisons), one underlying.

Long leg: a deep-ITM LEAP call (e.g. 85 delta, ~12 months) or shares, sized so its notional
(shares controlled x price) equals `exposure_pct` of the account; the rest of the account sits in
T-bills. Short leg (calls), one of:
  trend  - Tom King: 1-2 week calls whose delta follows the 8/21 EMA trend (uptrend OTM ~25Δ,
           neutral ATM ~50Δ, downtrend ITM ~65Δ); bought back once `roll_at_captured_pct` of the
           extrinsic is captured or on the day before expiry, then re-sold at the current trend's delta
  spike  - the rulebook: a 45-DTE call at the regime call delta only on an up-spike (IVR >= 50,
           >= 1.5 sigma), managed like the wheel (50% profit, 21-DTE decision)
  none   - long leg only
Entry filter (`entry_filter: tom`): close > SMA200, RSI14 > 35, EMA8 > EMA21. Exits (LEAP legs):
total P&L (long leg + calls) vs the LEAP debit >= target, or >= half the target within half the
expected days, or <= the stop; the LEAP is also closed at `leap_exit_dte`. After an exit the
position is reopened when the filter passes. Options are Black-Scholes on the same IV as the main
backtest (VXN x ratio for QQQ, with skew).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .backtest import bs_price, metrics, skew_iv, strike_for_delta, weekly


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def trend_frame(close: pd.Series, cfg: dict) -> pd.DataFrame:
    f = pd.DataFrame(index=close.index)
    f["ema_fast"] = close.ewm(span=cfg.get("ema_fast", 8), adjust=False).mean()
    f["ema_slow"] = close.ewm(span=cfg.get("ema_slow", 21), adjust=False).mean()
    f["sma200"] = close.rolling(200).mean()
    f["rsi"] = rsi(close, cfg.get("rsi_n", 14))
    gap = f["ema_fast"] / f["ema_slow"] - 1
    band = cfg.get("neutral_band_pct", 0.5) / 100
    f["trend"] = np.where(gap > band, "up", np.where(gap < -band, "down", "neutral"))
    return f


def entry_ok(row: dict, cfg: dict) -> bool:
    return bool(np.isfinite(row["sma200"]) and row["close"] > row["sma200"]
                and row["rsi"] > cfg.get("rsi_min", 35) and row["ema_fast"] > row["ema_slow"])


class PMCC:
    def __init__(self, variant: dict, frame: pd.DataFrame, rates: pd.Series, rules: dict, start, end,
                 slope: float = 0.8):
        self.v, self.rules = variant, rules
        self.cfg = {**(rules["backtest"].get("pmcc") or {}), **variant}
        self.bt = rules["backtest"]
        self.cal = rates.index[(rates.index >= start) & (rates.index <= end)]
        self.rates = rates.reindex(self.cal).to_numpy()
        tf = trend_frame(frame["close"].dropna(), self.cfg)
        f = frame.join(tf, how="left").reindex(self.cal)
        f["close"] = f["close"].ffill()
        f["iv"] = f["iv"].ffill()
        self.rows = f.to_dict("records")
        self.slope = slope
        self.cash = float(self.bt["account"])
        self.long = None      # {"kind", "K", "expiry", "qty", "cost", "opened", "calls_pnl"}
        self.call = None      # {"K", "expiry", "qty", "entry", "extrinsic", "opened"}
        self.equity, self.exposure = [], []
        self.stats = {k: 0 for k in ("entries", "exit_target", "exit_half", "exit_stop", "exit_dte",
                                     "calls_sold", "calls_bought_itm")}
        self.call_pnl = 0.0
        self.long_pnl = 0.0
        self.premium = 0.0

    # --- pricing helpers
    def _px(self, S, K, days, iv, cp, r):
        return bs_price(S, K, max(days, 0) / 365.0, skew_iv(iv, S, K, self.slope), cp, r)

    def _slip(self, px, leap=False):
        pct = self.cfg.get("slippage_pct_leap", 1.0) if leap else self.bt["costs"]["slippage_pct_index"]
        return max(px * pct / 100, 0.01) + self.bt["costs"]["per_contract"] / 100

    def _long_value(self, S, d, iv, r):
        lg = self.long
        if lg is None:
            return 0.0
        if lg["kind"] == "shares":
            return lg["qty"] * S
        return lg["qty"] * self._px(S, lg["K"], (lg["expiry"] - d).days, iv, "C", r)

    def _civ(self, iv):
        """IV for the short calls: weekly expiries sit below the 30-day index in calm markets."""
        return iv * (self.cfg.get("weekly_iv_ratio", 1.0) if self.cfg.get("calls", "trend") == "trend" else 1.0)

    def _call_value(self, S, d, iv, r):
        c = self.call
        if c is None:
            return 0.0
        return c["qty"] * self._px(S, c["K"], (c["expiry"] - d).days, self._civ(iv), "C", r)

    # --- legs
    def _open_long(self, S, d, iv, r, E):
        qty = self.cfg.get("exposure_pct", 100) / 100 * E / S
        if self.cfg.get("long", "leap") == "shares":
            self.long = {"kind": "shares", "qty": qty, "cost": qty * S, "opened": d, "calls_pnl": 0.0}
            self.cash -= qty * S
        else:
            dte = self.cfg.get("leap_dte", 365)
            K = strike_for_delta(S, dte / 365, iv, self.cfg.get("leap_delta", 85) / 100, "C", self.slope, r)
            px = self._px(S, K, dte, iv, "C", r) + self._slip(self._px(S, K, dte, iv, "C", r), leap=True)
            self.long = {"kind": "leap", "K": K, "expiry": d + pd.Timedelta(days=dte), "qty": qty,
                         "cost": qty * px, "opened": d, "calls_pnl": 0.0}
            self.cash -= qty * px
        self.stats["entries"] += 1

    def _close_long(self, S, d, iv, r, reason):
        lg = self.long
        if self.call:
            self._close_call(S, d, iv, r)
        if lg["kind"] == "shares":
            proceeds = lg["qty"] * S
        else:
            px = self._px(S, lg["K"], (lg["expiry"] - d).days, iv, "C", r)
            proceeds = lg["qty"] * max(px - self._slip(px, leap=True), 0.0)
        self.cash += proceeds
        self.long_pnl += proceeds - lg["cost"]
        self.stats[f"exit_{reason}"] += 1
        self.long = None

    def _sell_call(self, S, d, iv, r, delta, dte):
        iv = self._civ(iv)
        K = strike_for_delta(S, dte / 365, iv, delta, "C", self.slope, r)
        if self.long["kind"] == "leap":
            K = max(K, self.long["K"])           # never below the long strike
        mid = self._px(S, K, dte, iv, "C", r)
        credit = mid - self._slip(mid)
        if credit <= 0:
            return
        qty = self.long["qty"] * self.cfg.get("call_coverage", 100) / 100
        self.cash += credit * qty
        self.premium += credit * qty
        self.call = {"K": K, "expiry": d + pd.Timedelta(days=dte), "qty": qty, "entry": credit,
                     "mid": mid, "extrinsic": mid - max(S - K, 0.0), "opened": d}
        self.stats["calls_sold"] += 1

    def _close_call(self, S, d, iv, r):
        iv = self._civ(iv)
        c = self.call
        days = (c["expiry"] - d).days
        mid = self._px(S, c["K"], days, iv, "C", r) if days > 0 else max(S - c["K"], 0.0)
        cost = mid + (self._slip(mid) if mid > 0 else 0.0)
        self.cash -= cost * c["qty"]
        pnl = (c["entry"] - cost) * c["qty"]
        self.call_pnl += pnl
        if self.long:
            self.long["calls_pnl"] += pnl
        if S > c["K"]:
            self.stats["calls_bought_itm"] += 1
        self.call = None

    def _call_delta(self, row) -> tuple[float, int] | None:
        mode = self.cfg.get("calls", "trend")
        if mode == "trend":
            deltas = self.cfg.get("trend_call_delta", {"up": 25, "neutral": 50, "down": 65})
            return deltas[row["trend"]] / 100, self.cfg.get("call_dte", 10)
        if mode == "spike":
            th = self.rules["thresholds"]
            if (np.isfinite(row.get("ivr", np.nan)) and row["ivr"] >= th["ivr_sell"]
                    and row.get("up", 0) >= th["spike_sigma"]):
                return self.rules["strikes"]["call_delta"][row["regime"]] / 100, self.rules["strikes"]["dte_target"]
        return None

    # --- loop
    def run(self) -> "PMCC":
        mgmt = self.rules["management"]
        prev = None
        for i, d in enumerate(self.cal):
            row, r = self.rows[i], float(self.rates[i])
            S, iv = row["close"], row["iv"]
            if prev is not None:
                self.cash *= 1 + r * (d - prev).days / 365.0
            prev = d
            if not (np.isfinite(S) and np.isfinite(iv) and iv > 0):
                self.equity.append(self.equity[-1] if self.equity else self.cash)
                self.exposure.append(0.0)
                continue

            # short call management
            if self.call:
                c = self.call
                days = (c["expiry"] - d).days
                mid = self._px(S, c["K"], days, self._civ(iv), "C", r)
                ext = mid - max(S - c["K"], 0.0)
                if self.cfg.get("calls", "trend") == "trend":
                    captured = 1 - ext / c["extrinsic"] if c["extrinsic"] > 0 else 1
                    if captured >= self.cfg.get("roll_at_captured_pct", 85) / 100 or days <= 1:
                        self._close_call(S, d, iv, r)
                else:
                    if mid <= (1 - mgmt["take_profit_pct"] / 100) * c["mid"] or days <= mgmt["decide_dte"] or days <= 0:
                        self._close_call(S, d, iv, r)

            # long leg exits
            if self.long:
                lv = self._long_value(S, d, iv, r)
                cv = self._call_value(S, d, iv, r)
                lg = self.long
                if lg["kind"] == "leap":
                    pnl = (lv - lg["cost"] + lg["calls_pnl"]) / lg["cost"]
                    # an open short call: count its credit minus its current value
                    if self.call:
                        pnl += (self.call["entry"] * self.call["qty"] - cv) / lg["cost"]
                    held = (d - lg["opened"]).days
                    ex = self.cfg.get("exits") or {}
                    reason = None
                    if (lg["expiry"] - d).days <= self.cfg.get("leap_exit_dte", 120):
                        reason = "dte"
                    elif ex and pnl >= ex.get("target_pct", 1e9) / 100:
                        reason = "target"
                    elif ex and pnl >= ex.get("target_pct", 1e9) / 200 and held <= ex.get("expected_days", 365) / 2:
                        reason = "half"
                    elif ex and pnl <= ex.get("stop_pct", -1e9) / 100:
                        reason = "stop"
                    if reason:
                        self._close_long(S, d, iv, r, reason)

            # entries
            E = self.cash + self._long_value(S, d, iv, r) - self._call_value(S, d, iv, r)
            if self.long is None:
                if self.cfg.get("entry_filter") != "tom" or entry_ok(row, self.cfg):
                    self._open_long(S, d, iv, r, E)
            if self.long is not None and self.call is None:
                pick = self._call_delta(row)
                if pick and self.long["kind"] == "shares":
                    # keep shares at exposure_pct of equity (call buybacks are paid by trimming
                    # shares, not by borrowing)
                    E = self.cash + self.long["qty"] * S
                    tgt = self.cfg.get("exposure_pct", 100) / 100 * E / S
                    self.cash -= (tgt - self.long["qty"]) * S
                    self.long["qty"] = tgt
                if pick:
                    self._sell_call(S, d, iv, r, *pick)

            E = self.cash + self._long_value(S, d, iv, r) - self._call_value(S, d, iv, r)
            self.equity.append(E)
            self.exposure.append((self.long["qty"] * S / E) if (self.long and E > 0) else 0.0)
        return self

    def result(self) -> dict:
        eq = pd.Series(self.equity, index=self.cal)
        out = metrics(eq, pd.Series(self.rates, index=self.cal), self.bt)
        yrs = max(len(eq) / 252, 1e-9)
        out["avg_deployed_pct"] = round(float(np.mean(self.exposure)) * 100, 1)
        out["in_market_pct"] = round(float(np.mean([x > 0 for x in self.exposure])) * 100, 1)
        out["premium_per_year_pct"] = round(self.premium / yrs / float(eq.mean()) * 100, 2)
        out["call_pnl_per_year_pct"] = round(self.call_pnl / yrs / float(eq.mean()) * 100, 2)
        out["stats"] = dict(self.stats)
        out["equity_weekly"] = weekly(eq)
        return out
