"""data/iv_history/{SYM}.csv: one row per market date with the CBOE iv30 (vol points)."""
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
    """Series of iv30 (decimal) indexed by date."""
    p = path_for(sym, base)
    if not p.exists():
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    df = pd.read_csv(p, parse_dates=["date"])
    s = pd.Series(df["iv30"].astype(float).values / 100.0, index=pd.DatetimeIndex(df["date"]))
    return s[~s.index.duplicated(keep="last")].sort_index().dropna()


def append(sym: str, day: date, iv30: float, price: float | None = None, base: Path | None = None) -> None:
    """Upsert today's row (re-running the same day replaces it)."""
    if not np.isfinite(iv30) or iv30 <= 0:
        return
    p = path_for(sym, base)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([{"date": pd.Timestamp(day).strftime("%Y-%m-%d"), "iv30": round(iv30 * 100, 3),
                         "price": round(price, 4) if price is not None and np.isfinite(price) else ""}])
    if p.exists():
        df = pd.read_csv(p, dtype={"date": str})
        df = df[df["date"] != row["date"].iloc[0]]
        df = pd.concat([df, row], ignore_index=True).sort_values("date")
    else:
        df = row
    df.to_csv(p, index=False)
