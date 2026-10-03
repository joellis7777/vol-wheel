"""Synthetic fixtures: price paths and a Black-Scholes option chain in CBOE JSON shape."""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vol_wheel.config import load_rules  # noqa: E402

ASOF = date(2026, 10, 2)  # a Friday


def _ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(price, strike, t, iv, cp):
    """Black-Scholes (r=0) price and delta."""
    if t <= 0 or iv <= 0:
        intrinsic = max(price - strike, 0) if cp == "C" else max(strike - price, 0)
        return intrinsic, (1.0 if price > strike else 0.0) if cp == "C" else (-1.0 if price < strike else 0.0)
    d1 = (math.log(price / strike) + 0.5 * iv * iv * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    if cp == "C":
        return price * _ncdf(d1) - strike * _ncdf(d2), _ncdf(d1)
    return strike * _ncdf(-d2) - price * _ncdf(-d1), _ncdf(d1) - 1


def make_history(n=800, start=100.0, drift=0.0004, vol=0.015, seed=1, end=ASOF, shocks=None) -> pd.DataFrame:
    """Business-day OHLC ending at `end`. shocks: {index_from_end: pct_return} applied to closes."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    for k, r in (shocks or {}).items():
        rets[n - k] = r
    close = start * np.exp(np.cumsum(rets))
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    high = close * (1 + np.abs(rng.normal(0, vol / 2, n)))
    low = close * (1 - np.abs(rng.normal(0, vol / 2, n)))
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": 1e6},
                        index=pd.DatetimeIndex(idx, name="date"))


def third_friday(y, m):
    d = date(y, m, 15)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def make_chain_payload(sym="TEST", price=100.0, atm_iv=0.30, asof=ASOF, expiries=None, oi=500,
                       skew=-0.15, smile=0.4, spread_frac=0.04, iv_bumps=None) -> dict:
    """CBOE-shaped options payload. iv(K) = atm + skew*x + smile*x^2 with x = ln(K/S)."""
    if expiries is None:
        expiries = [asof + timedelta(days=d) for d in (7, 14, 21, 28)]
        expiries += [third_friday(2026, 11), third_friday(2026, 12), third_friday(2027, 1)]
        expiries += [third_friday(2027, 12), third_friday(2028, 1)]
    iv_bumps = iv_bumps or {}
    opts = []
    step = 1.0 if price < 200 else 5.0
    strikes = np.arange(round(price * 0.5 / step) * step, price * 1.5 + step, step)
    for e in expiries:
        t = (e - asof).days / 365.0
        for k in strikes:
            x = math.log(k / price)
            iv = atm_iv + skew * x + smile * x * x + iv_bumps.get(float(k), 0.0)
            for cp in ("C", "P"):
                px, delta = bs(price, k, t, iv, cp)
                mid = max(px, 0.01)
                half = max(mid * spread_frac / 2, 0.01)
                occ = f"{sym}{e:%y%m%d}{cp}{int(round(k * 1000)):08d}"
                opts.append({"option": occ, "bid": round(max(mid - half, 0.0), 2), "ask": round(mid + half, 2),
                             "iv": round(iv, 4), "open_interest": oi, "delta": round(delta, 4), "volume": 10})
    return {"timestamp": f"{asof:%Y-%m-%d} 16:15:00",
            "data": {"symbol": sym, "current_price": price, "iv30": atm_iv * 100, "close": price,
                     "high": price * 1.01, "low": price * 0.99, "open": price, "prev_day_close": price,
                     "options": opts}}


@pytest.fixture
def rules():
    return load_rules()
