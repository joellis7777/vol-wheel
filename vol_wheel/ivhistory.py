"""data/iv_history/{SYM}.csv: one row per market date with the CBOE iv30 (vol points).

Columns: date, iv30, price, iv30_ex. iv30_ex is iv30 with the implied earnings move stripped out,
written only when earnings sat inside the 30-day IV window; IV rank reads iv30_ex where present so
earnings bumps don't set the 52-week high.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ROOT

DIR = ROOT / "data" / "iv_history"


def path_for(sym: str, base: Path | None = None) -> Path:
    return (base or DIR) / f"{sym}.csv"


def load(sym: str, base: Path | None = None) -> pd.Series:
    """Series of iv30 (decimal, ex-earnings where recorded) indexed by date."""
    p = path_for(sym, base)
    if not p.exists():
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    df = pd.read_csv(p, parse_dates=["date"])
    iv = pd.to_numeric(df["iv30"], errors="coerce")
    if "iv30_ex" in df:
        iv = pd.to_numeric(df["iv30_ex"], errors="coerce").fillna(iv)
    s = pd.Series(iv.astype(float).values / 100.0, index=pd.DatetimeIndex(df["date"]))
    return s[~s.index.duplicated(keep="last")].sort_index().dropna()


def append(sym: str, day: date, iv30: float, price: float | None = None, base: Path | None = None,
           iv30_ex: float | None = None) -> None:
    """Upsert today's row (re-running the same day replaces it)."""
    if not np.isfinite(iv30) or iv30 <= 0:
        return
    p = path_for(sym, base)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([{"date": pd.Timestamp(day).strftime("%Y-%m-%d"), "iv30": round(iv30 * 100, 3),
                         "price": round(price, 4) if price is not None and np.isfinite(price) else "",
                         "iv30_ex": round(iv30_ex * 100, 3) if iv30_ex is not None and np.isfinite(iv30_ex) else ""}])
    if p.exists():
        df = pd.read_csv(p, dtype={"date": str})
        df = df[df["date"] != row["date"].iloc[0]]
        df = pd.concat([df, row], ignore_index=True).sort_values("date")
    else:
        df = row
    df.to_csv(p, index=False)
