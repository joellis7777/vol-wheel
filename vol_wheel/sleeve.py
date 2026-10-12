"""Long-call convexity sleeve (backtest `mode: sleeve`), one underlying.

A small, premium-sized position in long-dated calls (or a call debit spread); the rest of the account
sits in T-bills. Built to test Soliel's 2026 long-call rule against Jordan's deep-OTM idea:
  entry   buy `entry_delta` calls ~`dte` days out, spending `debit_pct` of equity, only when the entry
          filter passes: `sma200` (close > 200-day), `hhhl` (last confirmed swing high and low both above
          the previous ones), `max_runup_pct` (not after a pump: N-day return below this)
  spread  `short_delta`: also sell a call at that delta, same expiry (a wide call debit spread)
  exits   `half_off_pct`: sell half once the position is worth (1 + x%) of its cost (once per position);
          `exit_delta`: close all once the long call's delta reaches it ("ride 40 to 60 delta");
          `short_exit_delta`: spreads close once the short leg reaches it;
          `exit_dte`: close all at this many days to expiry (never hold long options inside 90 DTE);
          `stop_pct`: optional stop on the position's value vs cost.
  After a full exit the sleeve re-enters (the next session or later) when the filter passes again, so
  exits at `exit_delta` or `exit_dte` act as rolls while the trend holds.
Options are Black-Scholes on the backtest's IV (stock names: `stock_iv_mult` x max(HV20, HV60)) with
the stock skew slope, or `call_skew` when given (0 = flat; negative = OTM calls priced richer, as on
MSTR in bitcoin rallies), scaled by sqrt(skew_term_days / DTE) for long expiries. Far-OTM call prices hinge on that assumption, so run it at several values.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .backtest import bs_delta, bs_price, metrics, skew_iv, weekly


def hhhl_series(close: pd.Series, order: int = 5) -> pd.Series:
    """True where the last two *confirmed* swing highs and lows are rising. A swing at bar j is a bar
    higher (lower) than `order` bars each side; it is known only at bar j + order, so no look-ahead."""
    c = close.astype(float)
    win = 2 * order + 1
    is_hi = c == c.rolling(win, center=True).max()
    is_lo = c == c.rolling(win, center=True).min()
    hi = c.where(is_hi).shift(order)          # known `order` bars later
    lo = c.where(is_lo).shift(order)
    out = np.zeros(len(c), dtype=bool)
    highs: list[float] = []
    lows: list[float] = []
    for i, (h, l) in enumerate(zip(hi.to_numpy(), lo.to_numpy())):
        if np.isfinite(h) and not (highs and h == highs[-1]):    # a flat top is one swing, not two
            highs = (highs + [h])[-2:]
        if np.isfinite(l) and not (lows and l == lows[-1]):
            lows = (lows + [l])[-2:]
        out[i] = len(highs) == 2 and len(lows) == 2 and highs[1] > highs[0] and lows[1] > lows[0]
    return pd.Series(out, index=c.index)


class Sleeve:
    def __init__(self, variant: dict, frame: pd.DataFrame, rates: pd.Series, rules: dict, start, end,
                 slope: float):
        self.v = variant
        self.cfg = {**(rules["backtest"].get("sleeve") or {}), **variant}
        self.bt = rules["backtest"]
        self.cal = rates.index[(rates.index >= start) & (rates.index <= end)]
        self.rates = rates.reindex(self.cal).to_numpy()
        close = frame["close"].dropna()
        f = frame.reindex(self.cal).copy()
        f["close"] = f["close"].ffill()
        f["iv"] = f["iv"].ffill()
        f["sma200"] = close.rolling(200).mean().reindex(self.cal)
        n = self.cfg.get("runup_days", 20)
        f["runup"] = (close / close.shift(n) - 1).reindex(self.cal) * 100
        f["hhhl"] = hhhl_series(close, self.cfg.get("swing_order", 5)).reindex(self.cal).fillna(False)
        self.rows = f.to_dict("records")
        self.slope = self.cfg["call_skew"] if self.cfg.get("call_skew") is not None else slope
        self.slip_pct = self.cfg.get("slippage_pct", self.bt["costs"]["slippage_pct_stock"])
        self.cash = float(self.bt["account"])
        self.pos = None
        self.equity, self.invested = [], []
        self.trades: list[dict] = []
        self.stats = {k: 0 for k in ("entries", "exit_half", "exit_delta", "exit_short_delta", "exit_dte",
                                     "exit_stop", "exit_end")}

    # --- pricing
    def _iv(self, iv, S, K, days):
        # the skew slope is fitted to ~45-DTE options; longer expiries flatten about as 1/sqrt(T)
        # (same rule as the collars in run_hold)
        ref = self.bt.get("skew_term_days", 45)
        slope = self.slope * math.sqrt(ref / max(days, ref))
        return min(skew_iv(iv, S, K, slope), 3 * iv)          # cap upside skew at 3x ATM

    def _leg(self, S, K, days, iv, r):
        return bs_price(S, K, max(days, 0) / 365.0, self._iv(iv, S, K, days), "C", r)

    def _delta(self, S, K, days, iv, r):
        return bs_delta(S, K, max(days, 0) / 365.0, self._iv(iv, S, K, days), "C", r)

    def _strike(self, S, days, iv, delta, r):
        """Strike with the given call delta under this sleeve's skew, by bisection (the fixed-point solver
        in backtest.py diverges when OTM calls carry more IV than ATM)."""
        lo, hi = S * 0.05, S * 50
        for _ in range(80):
            mid = (lo * hi) ** 0.5
            if self._delta(S, mid, days, iv, r) > delta:
                lo = mid
            else:
                hi = mid
        return (lo * hi) ** 0.5

    def _unit(self, S, d, iv, r):
        p = self.pos
        days = (p["expiry"] - d).days
        v = self._leg(S, p["K"], days, iv, r)
        if p["Ks"] is not None:
            v -= self._leg(S, p["Ks"], days, iv, r)
        return max(v, 0.0)

    def _cost(self, mid, legs):
        # slippage per leg on each leg's mid, plus commissions
        return mid * self.slip_pct / 100 + legs * self.bt["costs"]["per_contract"] / 100

    # --- trades
    def _open(self, S, d, iv, r, E):
        dte = self.cfg.get("dte", 456)
        K = self._strike(S, dte, iv, self.cfg.get("entry_delta", 40) / 100, r)
        Ks = None
        long_mid = self._leg(S, K, dte, iv, r)
        mid, gross = long_mid, long_mid
        if self.cfg.get("short_delta"):
            Ks = self._strike(S, dte, iv, self.cfg["short_delta"] / 100, r)
            if Ks <= K:
                return
            short_mid = self._leg(S, Ks, dte, iv, r)
            mid, gross = long_mid - short_mid, long_mid + short_mid
        px = mid + self._cost(gross, 2 if Ks else 1)
        if px <= 0:
            return
        qty = self.cfg.get("debit_pct", 5) / 100 * E / px
        self.cash -= qty * px
        self.pos = {"K": K, "Ks": Ks, "expiry": d + pd.Timedelta(days=dte), "qty": qty, "px": px,
                    "cost": qty * px, "proceeds": 0.0, "halved": False, "opened": d, "S0": S}
        self.stats["entries"] += 1

    def _sell(self, frac, S, d, iv, r, reason):
        p = self.pos
        days = (p["expiry"] - d).days
        long_mid = self._leg(S, p["K"], days, iv, r)
        short_mid = self._leg(S, p["Ks"], days, iv, r) if p["Ks"] is not None else 0.0
        mid = max(long_mid - short_mid, 0.0)
        net = max(mid - self._cost(long_mid + short_mid, 2 if p["Ks"] else 1), 0.0)
        q = p["qty"] * frac
        self.cash += q * net
        p["proceeds"] += q * net
        p["qty"] -= q
        self.stats[f"exit_{reason}"] += 1
        if frac >= 1:
            self.trades.append({"opened": str(p["opened"].date()), "closed": str(d.date()), "reason": reason,
                                "days": (d - p["opened"]).days, "cost": p["cost"], "proceeds": p["proceeds"],
                                "multiple": p["proceeds"] / p["cost"] if p["cost"] else 0.0,
                                "move_pct": (S / p["S0"] - 1) * 100})
            self.pos = None

    def _filter_ok(self, row) -> bool:
        f = self.cfg.get("entry_filter") or []
        if isinstance(f, str):
            f = [f]
        if "sma200" in f and not (np.isfinite(row["sma200"]) and row["close"] > row["sma200"]):
            return False
        if "hhhl" in f and not row["hhhl"]:
            return False
        mx = self.cfg.get("max_runup_pct")
        if mx is not None and np.isfinite(row["runup"]) and row["runup"] > mx:
            return False
        return True

    # --- loop
    def run(self) -> "Sleeve":
        prev = None
        closed_today = False
        for i, d in enumerate(self.cal):
            row, r = self.rows[i], float(self.rates[i])
            S, iv = row["close"], row["iv"]
            if prev is not None:
                self.cash *= 1 + r * (d - prev).days / 365.0
            prev = d
            if not (np.isfinite(S) and np.isfinite(iv) and iv > 0):
                self.equity.append(self.equity[-1] if self.equity else self.cash)
                self.invested.append(0.0)
                continue
            closed_today = False
            if self.pos:
                p = self.pos
                days = (p["expiry"] - d).days
                unit = self._unit(S, d, iv, r)
                ld = self._delta(S, p["K"], days, iv, r)
                sd = self._delta(S, p["Ks"], days, iv, r) if p["Ks"] is not None else 0.0
                ex_d, ex_sd = self.cfg.get("exit_delta"), self.cfg.get("short_exit_delta")
                half, stop = self.cfg.get("half_off_pct"), self.cfg.get("stop_pct")
                if days <= self.cfg.get("exit_dte", 90):
                    self._sell(1, S, d, iv, r, "dte")
                elif ex_d and ld >= ex_d / 100:
                    self._sell(1, S, d, iv, r, "delta")
                elif ex_sd and p["Ks"] is not None and sd >= ex_sd / 100:
                    self._sell(1, S, d, iv, r, "short_delta")
                elif stop is not None and unit <= p["px"] * (1 + stop / 100):
                    self._sell(1, S, d, iv, r, "stop")
                elif half and not p["halved"] and unit >= p["px"] * (1 + half / 100):
                    self._sell(0.5, S, d, iv, r, "half")
                    p["halved"] = True
                closed_today = self.pos is None
            if self.pos is None and not closed_today and self._filter_ok(row):
                E = self.cash
                self._open(S, d, iv, r, E)
            val = self.pos["qty"] * self._unit(S, d, iv, r) if self.pos else 0.0
            E = self.cash + val
            self.equity.append(E)
            self.invested.append(val / E if E > 0 else 0.0)
        if self.pos:                            # mark the open position out at the last close
            row = self.rows[-1]
            self._sell(1, row["close"], self.cal[-1], row["iv"], float(self.rates[-1]), "end")
        return self

    def result(self) -> dict:
        eq = pd.Series(self.equity, index=self.cal)
        out = metrics(eq, pd.Series(self.rates, index=self.cal), self.bt)
        tr = self.trades
        cost = sum(t["cost"] for t in tr)
        proceeds = sum(t["proceeds"] for t in tr)
        mults = sorted(t["multiple"] for t in tr)
        out["avg_deployed_pct"] = round(float(np.mean(self.invested)) * 100, 1)
        out["in_market_pct"] = round(float(np.mean([x > 0 for x in self.invested])) * 100, 1)
        out["sleeve"] = {
            "trades": len(tr), "wins": sum(t["multiple"] > 1 for t in tr),
            "payoff_multiple": round(proceeds / cost, 2) if cost else None,
            "best_multiple": round(mults[-1], 2) if mults else None,
            "median_multiple": round(float(np.median(mults)), 2) if mults else None,
            "net_pnl": round(proceeds - cost), "avg_days": round(float(np.mean([t["days"] for t in tr]))) if tr else None,
            "exits": {k[5:]: v for k, v in self.stats.items() if k.startswith("exit_") and v},
            "top": sorted(tr, key=lambda t: -t["proceeds"] + t["cost"])[:3],
        }
        out["equity_weekly"] = weekly(eq)
        out["_eq"] = eq
        return out
