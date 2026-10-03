# vol-wheel — notes for future sessions

Daily options scanner + phone dashboard for a volatility-wheel + LEAP strategy.
**Phase 1 = signals only.** No trading, no broker calls, and **no account data in this repo** (it is
public). Position-dependent rules (cost basis, which names you hold) are shown as conditions on the
dashboard ("only if holding shares/LEAPs"), never computed from real holdings.

The rulebook this implements is the "Volatility Wheel + LEAP Strategy Rulebook" doc (Claude Docs,
artifact `b35fd311-9607-4176-9b14-4bc53847457f`). Every threshold lives in `config/rules.yaml`;
change behaviour there, not in code. If you add a rule, add its knob to the YAML.

## Layout

```
config/rules.yaml          all thresholds, universe/buckets/caps, sizing tiers, data URLs
vol_wheel/
  config.py                load_rules(), universe() -> [{symbol, bucket, role, cap}]
  data.py                  CBOE fetch + parse (chains, daily OHLC), Yahoo fallback, with_today()
  signals.py               IVR, HV, proxy IVR, spikes, extension/regime, Bollinger consolidation,
                           range position, bull gate, swing points (pure functions)
  ivhistory.py             data/iv_history/{SYM}.csv upsert/load
  strikes.py               expiry choice, skew fit, support/resistance levels, filters, 5-factor
                           scoring, reasons, LEAP candidate, ladder
  scan.py                  orchestration, action decision, JSON output; `python -m vol_wheel.scan`
data/iv_history/{SYM}.csv  date,iv30 (vol points),price — appended once per market date
docs/index.html            static phone-first dashboard (vanilla JS, light/dark) -> data/latest.json
docs/data/latest.json      written by the scan workflow (do not hand-edit)
docs/.nojekyll             serve docs/ as-is on GitHub Pages
tests/                     pytest; conftest.py builds synthetic histories + Black-Scholes chains
.github/workflows/scan.yml weekdays 21:35 UTC + manual: scan, commit data, push (GITHUB_TOKEN)
.github/workflows/tests.yml pytest on push/PR
```

## Running

```
pip install -r requirements-dev.txt
python -m pytest -q
python -m vol_wheel.scan                                   # full run, appends IV history
python -m vol_wheel.scan --symbols SPY,NVDA --no-append --out /tmp/x.json
```

The Claude Code cloud sandbox cannot reach cdn.cboe.com or Yahoo (proxy 403), so real-data checks
happen on the Actions runner: trigger `scan` (workflow_dispatch) and read the job log, which prints
one line per ticker (action, IVR, source, regime) and all data-quality notes.

## Data sources

Shapes below were verified on the first Actions run (2026-10-03): all 13 tickers plus `_VIX`/`_VXN`
parsed from CBOE with no fallback needed; history goes back to ~2004 for most names.

- Chains: `https://cdn.cboe.com/api/global/delayed_quotes/options/{SYM}.json`
  - `timestamp` (ET, fetch time), `data.current_price`, `data.iv30` (vol points, e.g. 15.2),
    `data.open/high/low/close/prev_day_close`, `data.options[]` with `option` (OCC symbol,
    e.g. `SPY261120P00550000`), `bid`, `ask`, `iv` (decimal), `open_interest`, `delta` (signed
    decimal), `volume`, greeks.
- Daily OHLC: `https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/{SYM}.json`
  - `{"data": [{"date": "YYYY-MM-DD", "open", "high", "low", "close", "volume"}]}`; values may be
    strings, parsers coerce.
- Indexes take a leading underscore: `_VIX`, `_VXN`.
- Fallback for daily prices: yfinance (`^VIX` for `_VIX`), else Yahoo's chart endpoint via requests.
  Used when CBOE history fails or has fewer than `data.history_min_days` bars.
- `data.parse_chain` normalizes units defensively (IV > 3 => percent, |delta| > 1.5 => percent).
- If today's bar isn't in the history yet, `with_today()` appends the chain quote as today's bar.
  Weekend fetches map to Friday (`market_date`) so manual weekend runs don't create fake bars.
- One ticker failing never fails the run: it becomes an `ERROR` card and a header note. The job
  exits non-zero only when every ticker failed.

## Signals (see `signals.py`)

- **IVR** = (iv30 − 52w low) / (52w high − 52w low) × 100 over our stored iv30 history.
  - `true`: ≥ 252 stored days. `partial`: 60–251 days. Below 60 days:
  - SPY/QQQ use VIX/VXN closes (true IVR now), labelled `VIX`/`VXN`.
  - Everyone else: `proxy` = percentile of today's HV20 within the last year of HV20.
  - The dashboard shows the source badge next to IVR.
- **σd** = HV20 measured on returns ending at t−k (before the window) × price(t−k) / √252.
  z_k = (close_t − close_{t−k}) / (σd·√k), k = 1..3. Down-spike size = max(−z_k), up = max(z_k).
  A spike counts at ≥ 1.5 (and the action also needs IVR ≥ 50).
- **Extension** = percentile of close/SMA200 over the last 756 days (or what exists, ≥ 60).
  Regime Low < 20, Mid 20–80, High > 80 (defaults to Mid when history is too short).
- **Consolidation** = 20-day Bollinger width (4σ/SMA) in the bottom 25% of the past year AND IVR < 25.
- **Range position** = (close − 50d low) / (50d high − 50d low).
- **Bull gate** = `bull_mode` in config AND SPY close > SMA200.

## Actions (`scan.decide_action`, priority order)

1. `SELL_PUT`: IVR ≥ 50 + down-spike (larger of the two if both).
2. `SELL_CALL`: IVR ≥ 50 + up-spike, "only if holding shares/LEAPs".
3. `LEAP_BUY`: bull gate, regime Low/Mid, consolidation, range pos ≤ 1/3, IVR < 25, core name.
4. `WATCH`: IVR ≥ 50, no spike.  5. `NEUTRAL` ("WAIT"): 30 ≤ IVR < 50.
6. `NO_SHORT`: IVR < 30.  `NO_DATA` / `ERROR` last.
- `both_sides`: SELL_PUT in Mid regime with IVR ≥ 70 adds a 10Δ covered call (`pair_call`).
- Put and call candidates and the LEAP candidate are always computed, whatever the action.

## Strike selection (`strikes.py`)

- Expiry: monthly (third Friday, or Thursday when that Friday is missing) in 35–50 DTE closest to
  45; else any expiry in the window; else closest to 45 (noted).
- Target delta by regime (puts/calls): Low 30/10, Mid 20/20, High 10/30. Band ±7Δ, OTM only.
- Filters: spread ≤ 10% of mid or ≤ $0.10; OI ≥ 100; puts ≥ 20Δ need mid ≥ 1% of strike, else 0.3%.
- Scores (0–1) × weights: support/resistance 30%, richness 25%, return on capital 20%,
  cushion 15%, assignment fit 10%.
  - S/R levels: SMA50/100/200, swing lows/highs (120d, 5 bars each side), round numbers
    (step ≈ 5% of price snapped to 1/2/2.5/5×10ⁿ), biggest put/call-OI strike (expiries ≤ 60 DTE).
    Each level type has a `strength` multiplier. Score 1 at 0.5–3% beyond the level, ramp 0.5→1
    inside 0.5%, fade to 0 at 8%; −0.5×strength penalty if within 2% on the wrong side of a level.
  - Richness: 50% skew residual (IV minus quadratic fit of IV vs ln(K/S) on OTM quotes of that
    expiry between 5Δ and 60Δ, −2..+3 pts → 0..1) + 50% IV/HV20 (0.8..1.5 → 0..1). The delta
    limits matter: fitting the far wings biased every tradeable strike ~3–5 pts "cheap".
  - ROC: annualized mid/strike (calls: mid/price), ranked within the band (best = 1).
  - Cushion: puts (price − BE)/move, calls (K − price)/move, move = price·iv30·√(DTE/365); full at 1.5.
  - Assignment fit: puts BE ≤ SMA200 or a 252d swing low (+1%, fading to 0 at +10%); calls K > price.
- Top 3 per side with a one-line reason, at least `min_strike_gap_pct` (0.5%) of price apart so
  SPY/QQQ's $1 strikes don't yield three near-identical picks.
- LEAP: 365–548 DTE calls, 70–80Δ, liquid if possible; lowest extrinsic % of price.
- Ladder: rung 1 = top put; rungs 2–3 = 1 and 2 forty-five-day expected moves lower, snapped down
  to a listed strike. IBIT/MSTR use max(iv30, HV20) for the move (weekend gaps).

## Dashboard (`docs/index.html`)

- Reads `data/latest.json` (relative path, works on Pages and `python -m http.server` in docs/).
- Account selector ($25k…$1M, default $500k, remembered in localStorage): entry = 5% of account;
  a put/rung is "CSP ok" when strike × 100 ≤ entry, else "spread / PMCC". Computed client-side.
- Cards sorted by action priority, then spike size, then IVR. Tap to expand.
- Theme follows the OS; the toggle overrides via `data-theme` on <html>.

## Conventions

- Python 3.11, deps: requests, pandas, numpy, pyyaml (+ optional yfinance). Keep it that way.
- Signal and scoring functions stay pure and take Series/DataFrames, so tests use synthetic data.
- Never commit account balances, positions, or broker credentials.
- `docs/data/latest.json` and `data/iv_history/*.csv` are written by the workflow; don't hand-edit.
