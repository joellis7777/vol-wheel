"""Index futures exposure in an IRA (backtest `mode: futures`, Jordan 2026-10-28).

Schwab IRAs may hold futures (NLV >= $25k, margin + option-spreads approval, held to 125% of the exchange's
initial margin) but may not sell naked options on futures. So an IRA can't sell MES puts with leverage; what it
can lever is the exposure itself: long MES / MNQ contracts worth more than the account. This mode tests how much
of that is survivable and whether it pays.

  exposure  `lev` (notional / equity, constant), or `alloc` [[drawdown % from the all-time high, lev]]
            (a dip ladder, checked daily), or `trend` {sma, slope_days, lev_down}: `lev` while the index is not
            below a falling `sma`-day average, `lev_down` while it is (checked at each month start, like the
            hold-mode exits). `trend` and `alloc` combine: the ladder's lev is used above, `lev_down` below.
  contracts `contract` {mult, per_share}: one contract = mult x per_share x ETF price (MES: $5 x SPX, SPX ~ 10 x
            SPY; MNQ: $2 x NDX, NDX ~ 41 x QQQ). With `whole_contracts: true` positions are whole contracts on
            `account` dollars, so a $100k account steps in ~38% chunks; otherwise fractional.
  carry     a future earns the index's price return minus (T-bill rate - `div_yield_pct`): the basis rolls
            down to spot. Cash earns T-bills except the part held as margin (`margin_earns: false`).
  margin    maintenance % of notional = `margin.base_pct` + `margin.per_vol_pct` x the vol index (VIX/VXN,
            lagged a day; calibrated to ES at ~4% in calm markets and ~9.5% in March 2020); initial = x
            `init_ratio`; the IRA requirement = initial x `ira_mult` x `stress` (a stress multiple for
            crash-time margin hikes). New contracts only while the requirement fits the equity; when it doesn't,
            the broker sells contracts until it does (a forced cut, no new adds until the next month start).
  costs     `cost_per_contract` per contract traded (commission + exchange fees + half a tick), and a calendar
            roll every quarter (`roll_cost_per_contract`).
The equity curve starts at `account`. Known biases: a constant dividend yield, a linear margin model, fills at
the close (forced cuts in a crash would often fill worse).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .backtest import TD, metrics, weekly


class Futures:
    def __init__(self, variant: dict, frame: pd.DataFrame, rates: pd.Series, rules: dict, start, end):
        self.bt = rules["backtest"]
        self.cfg = {**(self.bt.get("futures") or {}), **variant}
        c = self.cfg
        self.cal = rates.index[(rates.index >= start) & (rates.index <= end)]
        self.rates = rates.reindex(self.cal).fillna(0).to_numpy()
        close_all = frame["close"].dropna()
        self.close = close_all.reindex(self.cal).ffill().to_numpy()
        self.dd = ((close_all / close_all.cummax() - 1) * 100).reindex(self.cal).ffill().fillna(0).to_numpy()
        vol = frame["iv_raw"].reindex(self.cal).ffill() * 100          # vol index in points (VIX / VXN)
        self.vol = vol.shift(1).bfill().fillna(20).to_numpy()
        t = c.get("trend")
        if t:
            sma = close_all.rolling(t.get("sma", 200)).mean()
            down = (close_all < sma) & (sma < sma.shift(t.get("slope_days", 20)))
            self.down = down.reindex(self.cal).fillna(False).to_numpy()
        else:
            self.down = np.zeros(len(self.cal), dtype=bool)
        idx = self.cal
        self.month_start = np.r_[True, idx.month[1:] != idx.month[:-1]]
        # quarterly roll ~a week before the third-Friday expiry: first session on/after the 10th of Mar/Jun/Sep/Dec
        q = np.isin(idx.month, [3, 6, 9, 12]) & (idx.day >= 10)
        self.roll_day = q & ~np.r_[False, q[:-1]]
        ct = c.get("contract") or {"mult": 5, "per_share": 10}
        self.cn_per_price = ct["mult"] * ct["per_share"]               # contract notional per $1 of ETF price
        m = c.get("margin") or {}
        self.m_base, self.m_vol = m.get("base_pct", 3.0), m.get("per_vol_pct", 0.08)
        self.m_mult = m.get("init_ratio", 1.1) * m.get("ira_mult", 1.25) * m.get("stress", 1.0)
        self.whole = bool(c.get("whole_contracts"))
        self.div = c.get("div_yield_pct", 1.8) / 100
        self.E = float(c.get("account", self.bt["account"]))
        self.n = 0.0
        self.cooldown = False
        self.equity, self.levs, self.events = [], [], []
        self.stats = {"trades": 0, "contracts_traded": 0.0, "costs": 0.0, "rolls": 0, "forced_cuts": 0,
                      "wiped": None, "margin_bound_days": 0}

    # ------------------------------------------------------------------ helpers
    def req_frac(self, i: int) -> float:
        """IRA margin requirement as a fraction of notional on day i."""
        return (self.m_base + self.m_vol * self.vol[i]) / 100 * self.m_mult

    def target_lev(self, i: int) -> float:
        c = self.cfg
        if self.down[i] and c.get("trend"):
            return float(c["trend"].get("lev_down", 1.0))
        if c.get("alloc"):
            pts = sorted(c["alloc"], key=lambda p: -p[0])               # drawdown 0, -20, -40 ...
            xs = [-p[0] for p in pts]
            return float(np.interp(-self.dd[i], xs, [p[1] for p in pts]))
        return float(c.get("lev", 1.0))

    def trade(self, new_n: float, cn: float, forced: bool = False) -> None:
        d = abs(new_n - self.n)
        if d < 1e-9:
            return
        cost = d * self.cfg.get("cost_per_contract", 4.0)
        self.E -= cost
        self.stats["costs"] += cost
        self.stats["trades"] += 1
        self.stats["contracts_traded"] += d
        self.n = new_n

    def size(self, x: float) -> float:
        return math.floor(x + 1e-9) if self.whole else max(x, 0.0)

    # ------------------------------------------------------------------ run
    def run(self) -> "Futures":
        c = self.cfg
        band = c.get("band_pct", 10) / 100
        for i in range(len(self.cal)):
            px = self.close[i]
            cn = self.cn_per_price * px
            if i > 0 and self.E > 0:
                prev_cn = self.cn_per_price * self.close[i - 1]
                r = self.rates[i] / TD
                ret = px / self.close[i - 1] - 1
                pnl = self.n * prev_cn * (ret - (self.rates[i] - self.div) / TD)
                held = self.n * prev_cn * self.req_frac(i - 1)
                cash_base = self.E if c.get("margin_earns", False) else max(self.E - held, 0.0)
                self.E += pnl + cash_base * r
                if self.roll_day[i] and self.n > 0:
                    cost = self.n * c.get("roll_cost_per_contract", 6.0)
                    self.E -= cost
                    self.stats["costs"] += cost
                    self.stats["rolls"] += 1
            if self.E <= 0:
                if self.stats["wiped"] is None:
                    self.stats["wiped"] = self.cal[i].strftime("%Y-%m-%d")
                    self.events.append({"date": self.stats["wiped"], "type": "wiped"})
                self.E, self.n = 0.0, 0.0
                self.equity.append(0.0)
                self.levs.append(0.0)
                continue
            rf = self.req_frac(i)
            max_n = self.E / (cn * rf)                     # contracts the margin allows
            if self.n > max_n + 1e-9:                      # margin call: the broker sells down to fit
                new_n = self.size(max_n)
                self.events.append({"date": self.cal[i].strftime("%Y-%m-%d"), "type": "forced",
                                    "lev_before": round(self.n * cn / self.E, 2), "lev_after": round(new_n * cn / self.E, 2),
                                    "dd_index_pct": round(float(self.dd[i]), 1), "vol": round(float(self.vol[i]), 1)})
                self.trade(new_n, cn, forced=True)
                self.stats["forced_cuts"] += 1
                self.cooldown = True
            if self.month_start[i]:
                self.cooldown = False
            check = self.month_start[i] or (c.get("alloc") and not self.down[i])
            if check:
                want = self.target_lev(i) * self.E / cn
                if want > max_n:
                    self.stats["margin_bound_days"] += 1
                want = min(want, max_n)
                if self.cooldown:
                    want = min(want, self.n)
                new_n = self.size(want)
                if self.whole:
                    move = abs(new_n - self.n) >= 1
                else:
                    move = abs(new_n - self.n) * cn > band * self.E or (self.month_start[i] and new_n != self.n)
                if move:
                    self.trade(new_n, cn)
            self.equity.append(self.E)
            self.levs.append(self.n * cn / self.E if self.E > 0 else 0.0)
        return self

    def result(self) -> dict:
        eq = pd.Series(self.equity, index=self.cal)
        if (eq <= 0).any():                                  # metrics need a positive curve; keep a cent
            eq = eq.clip(lower=0.01)
        out = metrics(eq, pd.Series(self.rates, index=self.cal), self.bt)
        lev = np.asarray(self.levs)
        out["avg_deployed_pct"] = round(float(lev.mean()) * 100, 1)
        out["futures"] = {
            "avg_lev": round(float(lev.mean()), 2), "max_lev": round(float(lev.max()), 2),
            "forced_cuts": self.stats["forced_cuts"], "wiped": self.stats["wiped"],
            "margin_bound_days": self.stats["margin_bound_days"], "rolls": self.stats["rolls"],
            "costs_pct_per_year": round(self.stats["costs"] / float(eq.mean()) / max(len(eq) / TD, 1e-9) * 100, 2),
            "events": self.events[:12],
        }
        out["equity_weekly"] = weekly(eq)
        out["_eq"] = eq
        return out
