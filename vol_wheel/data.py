"""Market data: CBOE free delayed quotes, with a yfinance fallback for daily prices.

The CBOE JSON shapes handled here (verified on the Actions runner, see CLAUDE.md):

options/{SYM}.json
    {"timestamp": "2026-10-02 16:15:03", "data": {"symbol": "SPY", "current_price": 571.2,
     "iv30": 15.2, "open": ..., "high": ..., "low": ..., "close": ..., "prev_day_close": ...,
     "options": [{"option": "SPY261120P00550000", "bid": 4.1, "ask": 4.2, "iv": 0.17,
                  "open_interest": 1234, "delta": -0.21, "volume": 10, ...}, ...]}}

charts/historical/{SYM}.json
    {"symbol": "SPY", "data": [{"date": "2026-10-02", "open": "570.1", "high": ..., "low": ...,
                                "close": ..., "volume": ...}, ...]}

Indexes use a leading underscore (_VIX, _VXN). Parsers accept numbers or numeric strings and
normalize IV/delta units, so a small shape change degrades gracefully instead of crashing.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime

import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.cboe.com/",
    "Origin": "https://www.cboe.com",
}

OCC_RE = re.compile(r"^(?P<root>[A-Z0-9_.^]+?)\s*(?P<ymd>\d{6})(?P<cp>[CP])(?P<strike>\d{8})$")

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
    return _session


def get_json(url: str, timeout: float = 30, retries: int = 3) -> dict:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session().get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001 - any network/JSON failure is retried
            last = e
            log.warning("GET %s failed (%s/%s): %s", url, attempt + 1, retries, e)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v if np.isfinite(v) else float("nan")


def parse_occ(sym: str):
    """'SPY261120P00550000' -> (root, date(2026,11,20), 'P', 550.0) or None."""
    m = OCC_RE.match(str(sym).strip().upper())
    if not m:
        return None
    ymd = m.group("ymd")
    try:
        exp = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:6]))
    except ValueError:
        return None
    return m.group("root"), exp, m.group("cp"), int(m.group("strike")) / 1000.0


def normalize_iv30(v) -> float:
    """CBOE iv30 is in vol points (15.2). Return decimal (0.152)."""
    v = _num(v)
    if not np.isfinite(v) or v <= 0:
        return float("nan")
    return v / 100.0 if v > 3 else v


def parse_chain(payload: dict, asof: date | None = None) -> dict:
    """Return {'price', 'iv30', 'asof', 'quote': {...}, 'options': DataFrame}."""
    d = payload.get("data", payload) if isinstance(payload, dict) else {}
    price = _num(d.get("current_price"))
    if not np.isfinite(price):
        price = _num(d.get("close") or d.get("last_trade_price"))
    ts = payload.get("timestamp") if isinstance(payload, dict) else None
    asof_date = asof
    if asof_date is None:
        asof_date = _parse_date(ts) or _parse_date(d.get("last_trade_time")) or date.today()

    rows = []
    for o in d.get("options") or []:
        parsed = parse_occ(o.get("option", ""))
        if not parsed:
            continue
        _, exp, cp, strike = parsed
        bid, ask = _num(o.get("bid")), _num(o.get("ask"))
        rows.append({
            "expiry": exp, "type": cp, "strike": strike, "bid": bid, "ask": ask,
            "iv": _num(o.get("iv")), "oi": _num(o.get("open_interest")),
            "delta": _num(o.get("delta")), "volume": _num(o.get("volume")),
        })
    df = pd.DataFrame(rows, columns=["expiry", "type", "strike", "bid", "ask", "iv", "oi", "delta", "volume"])
    if not df.empty:
        # Normalize units defensively: IV should be decimal, delta in [-1, 1].
        ivs = df["iv"][df["iv"] > 0]
        if len(ivs) and ivs.median() > 3:
            df["iv"] = df["iv"] / 100.0
        ds = df["delta"].abs()
        if len(ds.dropna()) and ds.max() > 1.5:
            df["delta"] = df["delta"] / 100.0
        df["oi"] = df["oi"].fillna(0)
        df["mid"] = (df["bid"] + df["ask"]) / 2.0
        df["dte"] = [(e - asof_date).days for e in df["expiry"]]
    else:
        df["mid"] = []
        df["dte"] = []
    quote = {k: _num(d.get(k)) for k in ("open", "high", "low", "close", "prev_day_close")}
    return {"price": price, "iv30": normalize_iv30(d.get("iv30")), "asof": asof_date,
            "quote": quote, "options": df}


def _parse_date(s) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s)[:19], fmt).date()
        except ValueError:
            continue
    return None


def market_date(d: date) -> date:
    """Roll a weekend date back to Friday (CBOE timestamps carry the fetch time)."""
    wd = d.weekday()
    return d - pd.Timedelta(days=wd - 4).to_pytimedelta() if wd > 4 else d


def parse_history(payload) -> pd.DataFrame:
    """CBOE daily OHLC -> DataFrame(index=DatetimeIndex, cols open/high/low/close/volume)."""
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    recs = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        dt = _parse_date(r.get("date"))
        c = _num(r.get("close"))
        if dt is None or not np.isfinite(c) or c <= 0:
            continue
        recs.append({"date": pd.Timestamp(dt), "open": _num(r.get("open")), "high": _num(r.get("high")),
                     "low": _num(r.get("low")), "close": c, "volume": _num(r.get("volume"))})
    return _finish_history(pd.DataFrame(recs, columns=["date", "open", "high", "low", "close", "volume"]))


def _finish_history(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"],
                            index=pd.DatetimeIndex([], name="date"))
    df = df.drop_duplicates("date", keep="last").set_index("date").sort_index()
    for col in ("open", "high", "low"):
        df[col] = df[col].where(df[col] > 0, df["close"])
    return df


def yahoo_symbol(sym: str) -> str:
    return "^" + sym[1:] if sym.startswith("_") else sym


def fetch_history_yf(sym: str) -> pd.DataFrame:
    """Daily OHLC from Yahoo: yfinance if installed, else the public chart endpoint."""
    ysym = yahoo_symbol(sym)
    try:
        import yfinance as yf  # optional dependency

        h = yf.Ticker(ysym).history(period="5y", auto_adjust=False)
        if h is not None and not h.empty:
            h = h.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
            h.index = pd.DatetimeIndex([pd.Timestamp(d.date()) for d in h.index], name="date")
            return _finish_history(h.reset_index())
    except Exception as e:  # noqa: BLE001
        log.warning("yfinance %s failed: %s", ysym, e)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}?range=5y&interval=1d"
    j = get_json(url, retries=2)
    res = j["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "date": [pd.Timestamp(datetime.utcfromtimestamp(t).date()) for t in res["timestamp"]],
        "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"], "volume": q["volume"],
    }).dropna(subset=["close"])
    return _finish_history(df)


def fetch_chain(sym: str, cfg: dict) -> dict:
    url = cfg["cboe_chain_url"].format(sym=sym)
    return parse_chain(get_json(url, cfg.get("timeout_s", 30), cfg.get("retries", 3)))


def fetch_history(sym: str, cfg: dict) -> tuple[pd.DataFrame, str, list[str]]:
    """Daily history, CBOE first then Yahoo. Returns (df, source, notes)."""
    notes: list[str] = []
    df = None
    try:
        url = cfg["cboe_history_url"].format(sym=sym)
        df = parse_history(get_json(url, cfg.get("timeout_s", 30), cfg.get("retries", 3)))
        if len(df) >= cfg.get("history_min_days", 220):
            return df, "cboe", notes
        notes.append(f"CBOE history short ({len(df)} bars)")
    except Exception as e:  # noqa: BLE001
        notes.append(f"CBOE history failed: {e}")
    try:
        yf_df = fetch_history_yf(sym)
        if df is None or len(yf_df) > len(df):
            return yf_df, "yahoo", notes
    except Exception as e:  # noqa: BLE001
        notes.append(f"Yahoo history failed: {e}")
    if df is not None and len(df):
        return df, "cboe", notes
    raise RuntimeError("; ".join(notes) or "no price history")


def with_today(hist: pd.DataFrame, chain: dict | None) -> pd.DataFrame:
    """Append the chain's quote as today's bar if history doesn't include it yet."""
    if chain is None or not np.isfinite(chain.get("price", np.nan)):
        return hist
    day = pd.Timestamp(market_date(chain["asof"]))
    if len(hist) and hist.index[-1] >= day:
        return hist
    q = chain.get("quote", {})
    px = chain["price"]
    hi, lo, op = q.get("high"), q.get("low"), q.get("open")
    bar = {
        "open": op if np.isfinite(op or np.nan) and op > 0 else px,
        "high": max(hi, px) if np.isfinite(hi or np.nan) and hi > 0 else px,
        "low": min(lo, px) if np.isfinite(lo or np.nan) and lo > 0 else px,
        "close": px, "volume": np.nan,
    }
    out = pd.concat([hist, pd.DataFrame([bar], index=pd.DatetimeIndex([day], name="date"))])
    return out
