"""Scale-in / scale-out ladder executed with limit orders or with options at the same levels (Jordan,
2026-10-25: "a $250 put is the $250 buy limit I'd place anyway, plus the premium").

One underlying. The account starts at `base_pct` in shares. Rungs (all levels are prices):
  buy rungs   `buy_rungs` [[drawdown % from the running high, % of equity added], ...]: rung i sits at
              high x (1 - dd_i). A filled rung is a lot that is trimmed one rung up: at high x (1 - dd_{i-1})
              (rung 0 = the high itself), using the high at the time it filled.
  scale-out   `scale_out` [[gain % from the lowest close of `gain_lookback_days`, % of equity sold], ...]:
              rung j sits at low x (1 + g_j); a filled one is bought back `rebuy_pct` below its sale price.
Execution:
  limit    resting orders fill when the day's range touches the level (open -> nearer extreme -> other
           extreme -> close; a gap through a level fills at the open).
  options  a cash-secured put (buy rungs, rebuys) or covered call (trims, scale-outs) struck at the level
           (never in the money: at most today's price), `dte` days, held to expiry with no debit paid
           unless `take_profit_pct` is set; assignment fills the rung. `put_rungs_ahead` = how many unfilled
           buy rungs carry a put at once. Expired-worthless options are re-sold the next session at the
           (possibly moved) level.
  dip_buy  (options only) on the first day of a down-spike, close every short call and buy the next
           `dip_rungs` unfilled buy rungs with stock when price is within `dip_near_pct` of the rung, using cash not securing puts; open puts stay and move to
           the next unfilled rungs. No new calls are sold while the spike lasts.
Cash earns the T-bill yield. Options are Black-Scholes on the backtest's IV with the skew slope.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import bs_price, metrics, skew_iv


class Ladder:
    def __init__(self, variant: dict, frame: pd.DataFrame, rates: pd.Series, rules: dict, start, end,
                 slope: float = 0.8):
        self.v, self.rules, self.bt = variant, rules, rules["backtest"]
        self.cfg = {**(self.bt.get("ladder") or {}), **variant}
        self.cal = rates.index[(rates.index >= start) & (rates.index <= end)]
        self.rates = rates.reindex(self.cal).to_numpy()
        close = frame["close"].dropna()
        lb = self.cfg.get("high_lookback_days")
        f = frame.copy()
        f["H"] = close.rolling(lb, min_periods=1).max() if lb else close.cummax()
        f["L"] = close.rolling(int(self.cfg.get("gain_lookback_days", 756)), min_periods=20).min()
        f = f.reindex(self.cal)
        for c in ("close", "iv", "H", "L"):
            f[c] = f[c].ffill()
        for c in ("open", "high", "low"):
            f[c] = f[c].fillna(f["close"]) if c in f else f["close"]
        self.rows = f.to_dict("records")
        self.slope = slope
        self.buy = sorted(self.cfg["buy_rungs"])
        self.out = sorted(self.cfg.get("scale_out") or [])
        self.cash = float(self.bt["account"])
        self.shares = 0.0
        self.lots: dict[int, dict] = {}       # filled buy rungs: {rung: {qty, exit}}
        self.outs: dict[int, dict] = {}       # filled scale-out rungs: {rung: {qty, rebuy}}
        self.opts: list[dict] = []
        self.in_dip = False
        self.premium = 0.0
        self.equity, self.in_shares = [], []
        self.stats = {k: 0 for k in ("buy_fills", "trims", "scale_outs", "rebuys", "puts_sold", "calls_sold",
                                     "puts_expired", "calls_expired", "dip_buys", "calls_closed_on_dips")}

    # --- levels
    def _buy_level(self, i, H):
        return H * (1 - self.buy[i][0] / 100)

    def _trim_level(self, i, H):
        return H * (1 - (self.buy[i - 1][0] if i > 0 else 0) / 100)

    def _out_level(self, j, L):
        return L * (1 + self.out[j][0] / 100)

    def _next_buys(self, k):
        return [i for i in range(len(self.buy)) if i not in self.lots][:k]

    def _next_out(self):
        free = [j for j in range(len(self.out)) if j not in self.outs]
        return free[0] if free else None

    # --- stock fills
    def _buy_stock(self, qty, px):
        qty = min(qty, max(self.cash, 0) / px)
        self.shares += qty
        self.cash -= qty * px * (1 + self.cost)
        return qty

    def _sell_stock(self, qty, px):
        qty = min(qty, self.shares)
        self.shares -= qty
        self.cash += qty * px * (1 - self.cost)
        return qty

    def _fill_buy(self, i, qty, H):
        self.lots[i] = {"qty": qty, "exit": self._trim_level(i, H)}
        self.stats["buy_fills"] += 1

    def _fill_out(self, j, qty, px):
        self.outs[j] = {"qty": qty, "rebuy": px * (1 - self.cfg.get("rebuy_pct", 25) / 100)}
        self.stats["scale_outs"] += 1

    # --- limit execution: walk the day's path and fill resting orders it touches
    def _limit_day(self, row, prev_close, E):
        H, L = row["H_prev"], row["L_prev"]
        o, hi, lo, c = row["open"], row["high"], row["low"], row["close"]
        path = [prev_close, o] + ([lo, hi] if abs(o - lo) <= abs(hi - o) else [hi, lo]) + [c]
        for a, b in zip(path[:-1], path[1:]):
            if b < a:                                         # falling: buy rungs, rebuys (highest first)
                while True:
                    ev = []
                    nb = self._next_buys(1)
                    if nb and self._buy_level(nb[0], H) >= b:
                        ev.append((self._buy_level(nb[0], H), "buy", nb[0]))
                    ev += [(x["rebuy"], "rebuy", j) for j, x in self.outs.items() if x["rebuy"] >= b]
                    if not ev:
                        break
                    lvl, kind, k = max(ev)
                    px = min(lvl, a)
                    if kind == "buy":
                        q = self._buy_stock(self.buy[k][1] / 100 * E / px, px)
                        self._fill_buy(k, q, H)
                        if q <= 0:
                            break
                    else:
                        self._buy_stock(self.outs.pop(k)["qty"], px)
                        self.stats["rebuys"] += 1
            elif b > a:                                       # rising: trims, scale-outs (lowest first)
                while True:
                    ev = [(x["exit"], "trim", i) for i, x in self.lots.items() if x["exit"] <= b]
                    j = self._next_out()
                    if j is not None and self._out_level(j, L) <= b:
                        ev.append((self._out_level(j, L), "out", j))
                    if not ev:
                        break
                    lvl, kind, k = min(ev)
                    px = max(lvl, a)
                    if kind == "trim":
                        self._sell_stock(self.lots.pop(k)["qty"], px)
                        self.stats["trims"] += 1
                    else:
                        q = self._sell_stock(self.out[k][1] / 100 * E / px, px)
                        self._fill_out(k, q, px)
                        if q <= 0:
                            break

    # --- options
    def _px(self, S, K, days, iv, cp, r):
        return bs_price(S, K, max(days, 0) / 365.0, skew_iv(iv, S, K, self.slope), cp, r)

    def _slip(self, mid):
        c = self.bt["costs"]
        pct = c["slippage_pct_index"] if self.cfg.get("index", True) else c["slippage_pct_stock"]
        return max(mid * pct / 100, 0.01) + c["per_contract"] / 100

    def _opt_value(self, S, d, iv, r):
        return sum(o["qty"] * self._px(S, o["K"], (o["exp"] - d).days, iv, o["cp"], r) for o in self.opts)

    def _sell(self, cp, K, qty, tag, S, d, iv, r):
        dte = self.cfg.get("dte", 45)
        K = min(K, S) if cp == "P" else max(K, S)
        mid = self._px(S, K, dte, iv, cp, r)
        credit = mid - self._slip(mid)
        if credit <= 0 or qty <= 0:
            return
        self.cash += credit * qty
        self.premium += credit * qty
        self.opts.append({"cp": cp, "K": K, "qty": qty, "exp": d + pd.Timedelta(days=dte), "mid": mid, "tag": tag})
        self.stats["puts_sold" if cp == "P" else "calls_sold"] += 1

    def _close(self, o, S, d, iv, r):
        mid = self._px(S, o["K"], (o["exp"] - d).days, iv, o["cp"], r)
        self.cash -= (mid + self._slip(mid)) * o["qty"]

    def _expire(self, S, d, iv, r, H):
        tp = self.cfg.get("take_profit_pct")
        keep = []
        for o in self.opts:
            days = (o["exp"] - d).days
            kind, k = o["tag"]
            if days > 0:
                if tp and self._px(S, o["K"], days, iv, o["cp"], r) <= (1 - tp / 100) * o["mid"]:
                    self._close(o, S, d, iv, r)
                    continue
                keep.append(o)
                continue
            itm = S < o["K"] if o["cp"] == "P" else S > o["K"]
            if not itm:
                self.stats["puts_expired" if o["cp"] == "P" else "calls_expired"] += 1
                continue
            if o["cp"] == "P":
                self.shares += o["qty"]
                self.cash -= o["K"] * o["qty"]
                if kind == "buy" and k not in self.lots:
                    self._fill_buy(k, o["qty"], o["H"])
                elif kind == "rebuy":
                    self.outs.pop(k, None)
                    self.stats["rebuys"] += 1
                else:                                         # rung already filled by a dip buy: next free rung
                    nb = self._next_buys(1)
                    if nb:
                        self._fill_buy(nb[0], o["qty"], o["H"])
                    else:
                        self.lots[max(self.lots)]["qty"] += o["qty"]
            else:
                q = min(o["qty"], self.shares)
                self.shares -= q
                self.cash += o["K"] * q
                if kind == "trim":
                    self.lots.pop(k, None)
                    self.stats["trims"] += 1
                else:
                    self._fill_out(k, q, o["K"])
        self.opts = keep

    def _options_day(self, row, S, d, iv, r, E):
        H, L = row["H"], row["L"]
        dip = bool(self.cfg.get("dip_buy")) and (row.get("down") or 0) >= self.rules["thresholds"]["spike_sigma"]
        if dip and not self.in_dip:
            calls = [o for o in self.opts if o["cp"] == "C"]
            for o in calls:
                self._close(o, S, d, iv, r)
                self.stats["calls_closed_on_dips"] += 1
            self.opts = [o for o in self.opts if o["cp"] == "P"]
            secured = sum(o["K"] * o["qty"] for o in self.opts if o["cp"] == "P")
            near = 1 + self.cfg.get("dip_near_pct", 5) / 100
            for i in self._next_buys(int(self.cfg.get("dip_rungs", 1))):
                if S > self._buy_level(i, H) * near:           # only at a level: within dip_near_pct of the rung
                    break
                free = self.cash - secured
                q = min(self.buy[i][1] / 100 * E / S, max(free, 0) / S)
                if q * S < 0.005 * E:
                    break
                self._buy_stock(q, S)
                self._fill_buy(i, q, H)
                self.stats["dip_buys"] += 1
            # open puts move to the next unfilled rungs (kept, not closed: no whipsaw)
            free_rungs = self._next_buys(len(self.buy))
            for o, i in zip([o for o in self.opts if o["tag"][0] == "buy"], free_rungs):
                o["tag"] = ("buy", i)
        self.in_dip = dip                                     # one close/buy per sell-off; no new calls during it
        tagged = {o["tag"] for o in self.opts}
        secured = sum(o["K"] * o["qty"] for o in self.opts if o["cp"] == "P")
        # puts: next unfilled buy rungs, then rebuys of scale-outs
        want = [(("buy", i), self._buy_level(i, H), self.buy[i][1] / 100 * E / self._buy_level(i, H))
                for i in self._next_buys(int(self.cfg.get("put_rungs_ahead", 1)))]
        want += [(("rebuy", j), x["rebuy"], x["qty"]) for j, x in self.outs.items()]
        for tag, K, qty in want:
            if tag in tagged:
                continue
            Kp = min(K, S)
            qty = min(qty, max(self.cash - secured, 0) / Kp)
            if qty * Kp < 0.005 * E:
                continue
            n0 = len(self.opts)
            self._sell("P", K, qty, tag, S, d, iv, r)
            if len(self.opts) > n0:
                self.opts[-1]["H"] = H
                secured += self.opts[-1]["K"] * qty
        # calls: trims of filled lots, then the next scale-out rung
        covered = sum(o["qty"] for o in self.opts if o["cp"] == "C")
        want = [(("trim", i), x["exit"], x["qty"]) for i, x in self.lots.items()]
        j = self._next_out()
        if j is not None:
            lvl = self._out_level(j, L)
            want.append((("out", j), lvl, self.out[j][1] / 100 * E / lvl))
        for tag, K, qty in want:
            if tag in tagged or dip:
                continue
            qty = min(qty, self.shares - covered)
            if qty * S < 0.005 * E:
                continue
            n0 = len(self.opts)
            self._sell("C", K, qty, tag, S, d, iv, r)
            if len(self.opts) > n0:
                covered += qty

    # --- loop
    def run(self) -> "Ladder":
        self.cost = self.cfg.get("stock_cost_bps", 5) / 1e4
        limit = self.cfg.get("exec", "options") == "limit"
        prev, prev_close, prev_H, prev_L = None, None, None, None
        for i, d in enumerate(self.cal):
            row, r = dict(self.rows[i]), float(self.rates[i])
            S, iv = row["close"], row["iv"]
            if prev is not None:
                self.cash *= 1 + r * (d - prev).days / 365.0
            prev = d
            if not (np.isfinite(S) and np.isfinite(iv) and iv > 0):
                self.equity.append(self.equity[-1] if self.equity else self.cash)
                self.in_shares.append(self.in_shares[-1] if self.in_shares else 0.0)
                continue
            if prev_close is None:                            # day one: buy the base position
                self._buy_stock(self.cfg.get("base_pct", 60) / 100 * self.cash / S, S)
            elif limit:
                row["H_prev"], row["L_prev"] = prev_H, prev_L
                E0 = self.cash + self.shares * prev_close
                self._limit_day(row, prev_close, E0)
            else:
                self._expire(S, d, iv, r, row["H"])
                E0 = self.cash + self.shares * S - self._opt_value(S, d, iv, r)
                self._options_day(row, S, d, iv, r, E0)
            prev_close, prev_H, prev_L = S, row["H"], row["L"]
            E = self.cash + self.shares * S - self._opt_value(S, d, iv, r)
            self.equity.append(E)
            self.in_shares.append(self.shares * S / E if E > 0 else 0.0)
        return self

    def result(self) -> dict:
        eq = pd.Series(self.equity, index=self.cal)
        out = metrics(eq, pd.Series(self.rates, index=self.cal), self.bt)
        yrs = max(len(eq) / 252, 1e-9)
        out["avg_deployed_pct"] = round(float(np.mean(self.in_shares)) * 100, 1)
        out["avg_shares_pct"] = out["avg_deployed_pct"]
        out["premium_per_year_pct"] = round(self.premium / yrs / float(eq.mean()) * 100, 2)
        out["ladder"] = {k: round(v / yrs, 1) for k, v in self.stats.items()}
        out["_eq"] = eq
        return out
