"""Signal math: IV rank, realized vol, spikes, extension regime, consolidation, bull gate.

All functions take plain pandas Series/DataFrames so they can be tested on synthetic data.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def iv_rank(current: float, history: pd.Series | np.ndarray) -> float:
    """(current - 52w low) / (52w high - 52w low) * 100, clipped to 0..100."""
    h = pd.Series(history, dtype=float).dropna()
    if not np.isfinite(current) or h.empty:
        return float("nan")
    lo, hi = min(h.min(), current), max(h.max(), current)
    if hi - lo <= 1e-12:
        return 50.0
    return float(np.clip((current - lo) / (hi - lo) * 100.0, 0, 100))


def percentile_rank(current: float, history: pd.Series | np.ndarray) -> float:
    """Share of history values at or below `current`, 0..100."""
    h = pd.Series(history, dtype=float).dropna()
    if not np.isfinite(current) or h.empty:
        return float("nan")
    return float((h <= current).mean() * 100.0)


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def hv(close: pd.Series, window: int = 20) -> pd.Series:
    """Annualized close-to-close realized vol (decimal), rolling."""
    return log_returns(close).rolling(window).std(ddof=1) * math.sqrt(TRADING_DAYS)


def proxy_ivr(close: pd.Series, window: int = 20, lookback: int = TRADING_DAYS) -> float:
    """Percentile of today's HV20 within the last year of HV20 values."""
    h = hv(close, window).dropna()
    if len(h) < 20:
        return float("nan")
    h = h.iloc[-lookback:]
    return percentile_rank(h.iloc[-1], h)


def spike(close: pd.Series, max_k: int = 3, hv_window: int = 20) -> dict:
    """Largest standardized 1..k-day move ending today.

    sigma_d = HV20 measured on returns ending at t-k (before the window) * price(t-k) / sqrt(252)
    z_k = (close_t - close_{t-k}) / (sigma_d * sqrt(k))
    Returns {"down": max(-z), "up": max(z), "down_k", "up_k"}.
    """
    c = pd.Series(close, dtype=float).dropna()
    hvs = hv(c, hv_window)
    out = {"down": 0.0, "up": 0.0, "down_k": None, "up_k": None}
    n = len(c)
    for k in range(1, max_k + 1):
        if n <= k + hv_window:
            break
        base_i = n - 1 - k
        sig_ann = hvs.iloc[base_i]
        base_px = c.iloc[base_i]
        if not np.isfinite(sig_ann) or sig_ann <= 0:
            continue
        sigma_d = sig_ann * base_px / math.sqrt(TRADING_DAYS)
        z = (c.iloc[-1] - base_px) / (sigma_d * math.sqrt(k))
        if -z > out["down"]:
            out["down"], out["down_k"] = float(-z), k
        if z > out["up"]:
            out["up"], out["up_k"] = float(z), k
    return out


def extension(close: pd.Series, sma_window: int = 200, lookback: int = 756, min_days: int = 60) -> dict:
    """Percentile of close/SMA200 over the last ~3 years (or what exists)."""
    c = pd.Series(close, dtype=float).dropna()
    sma = c.rolling(sma_window).mean()
    ratio = (c / sma).dropna()
    if len(ratio) < min_days:
        return {"pct": float("nan"), "ratio": float("nan"), "days": len(ratio)}
    r = ratio.iloc[-lookback:]
    return {"pct": percentile_rank(r.iloc[-1], r), "ratio": float(r.iloc[-1]), "days": len(r)}


def regime(ext_pct: float, low_below: float = 20, high_above: float = 80) -> str:
    if not np.isfinite(ext_pct):
        return "Mid"
    if ext_pct < low_below:
        return "Low"
    if ext_pct > high_above:
        return "High"
    return "Mid"


def bb_width(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.Series:
    """(upper - lower) / middle of the Bollinger band."""
    mid = close.rolling(window).mean()
    sd = close.rolling(window).std(ddof=0)
    return (2 * n_std * sd) / mid


def consolidation(close: pd.Series, ivr: float, window: int = 20, n_std: float = 2.0,
                  lookback: int = TRADING_DAYS, pct_max: float = 25, ivr_max: float = 25) -> dict:
    w = bb_width(pd.Series(close, dtype=float), window, n_std).dropna()
    if len(w) < 20:
        return {"on": False, "bb_pct": float("nan")}
    w = w.iloc[-lookback:]
    pct = percentile_rank(w.iloc[-1], w)
    on = bool(pct <= pct_max and np.isfinite(ivr) and ivr < ivr_max)
    return {"on": on, "bb_pct": pct}


def range_position(hist: pd.DataFrame, window: int = 50) -> float:
    """0 = at the 50-day low, 1 = at the 50-day high."""
    h = hist.iloc[-window:]
    lo, hi = h["low"].min(), h["high"].max()
    c = hist["close"].iloc[-1]
    if not np.isfinite(lo) or hi - lo <= 1e-12:
        return float("nan")
    return float(np.clip((c - lo) / (hi - lo), 0, 1))


def sma(close: pd.Series, window: int) -> float:
    c = pd.Series(close, dtype=float).dropna()
    if len(c) < window:
        return float("nan")
    return float(c.iloc[-window:].mean())


def bull_gate(bull_mode: bool, spy_close: pd.Series) -> dict:
    s200 = sma(spy_close, 200)
    last = float(spy_close.iloc[-1]) if len(spy_close) else float("nan")
    above = bool(np.isfinite(s200) and last > s200)
    return {"on": bool(bull_mode and above), "bull_mode": bool(bull_mode),
            "spy_close": last, "spy_sma200": s200, "spy_above_sma200": above}


def swing_points(series: pd.Series, order: int = 5, kind: str = "low") -> list[float]:
    """Local extrema: a bar lower (higher) than `order` bars on each side."""
    v = pd.Series(series, dtype=float).values
    out = []
    for i in range(order, len(v) - order):
        win = v[i - order:i + order + 1]
        if not np.isfinite(v[i]):
            continue
        if kind == "low" and v[i] == np.nanmin(win):
            out.append(float(v[i]))
        if kind == "high" and v[i] == np.nanmax(win):
            out.append(float(v[i]))
    return out
