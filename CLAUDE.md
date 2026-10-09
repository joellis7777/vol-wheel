# vol-wheel — notes for future sessions

Daily options scanner + phone dashboard for a volatility-wheel + LEAP strategy.
**Phase 1 = signals only.** No trading, no broker calls, and **no account data in this repo** (it is
public). Position-dependent rules (cost basis, which names you hold) are shown as conditions on the
dashboard ("only if holding shares/LEAPs"), never computed from real holdings.

The rulebook this implements is the "Volatility Wheel + LEAP Strategy Rulebook" doc (Claude Docs,
artifact `b35fd311-9607-4176-9b14-4bc53847457f`). Every threshold lives in `config/rules.yaml`;
change behaviour there, not in code. If you add a rule, add its knob to the YAML.

## Strategy decisions (source of truth — read first, keep current)

These are Jordan's standing decisions. Treat them as authoritative over older notes, defaults or
your own assumptions; if a request conflicts with one, say so before building. When a decision
changes, update this list in the same change.

- **Wheel runs in a Schwab IRA.** All short puts/calls (45 DTE wheel, calls against LEAPs, earnings
  plays) are IRA trades, so tax treatment doesn't drive wheel decisions.
- **Taxable account = long-term holds + LEAPs held >1 year with no short calls against them**
  (tax-straddle rules would otherwise suspend the holding period). Hence the dashboard's two LEAP
  variants: IRA 12–18 months, Taxable 16–18 months "hold >1 year, don't sell calls against".
- **No standing crash hedge.** Protection = 20% cash reserve in SGOV, bucket caps, circuit
  breakers (and 10Δ puts in the High regime). The far-OTM SPY/QQQ put card is optional and off
  by default (`hedge_alerts: false`).
- **Watch wash sales between taxable and the IRA**: don't buy or get assigned a stock in the IRA
  within 30 days of selling it at a loss in taxable (the loss is permanently disallowed). Not
  automated (no account data in this public repo); call it out when relevant.
- **Phase 3 broker = Schwab Trader API** (OAuth login must be renewed every 7 days; its quotes can
  replace the delayed CBOE feed). Robinhood's agent accounts don't cover IRAs, so they're out.
- **Earnings mode** replaces the old "no entries above 10Δ spanning earnings" rule: nothing normal
  is sold *through* a report. When earnings fall before the usual 35–50 DTE expiry, the wheel
  trades the latest expiry of 21–34 DTE that settles before the report (normal deltas, size and
  signals; decided 2026-10-06, `earnings.pre_earnings_expiry`). Those trades are managed as
  "take 50% of the credit or hold to expiry" (`take_profit_pct`, decided 2026-10-09): the 21-DTE
  decision rule doesn't apply and they are never rolled past the report. Only if no such expiry
  exists do normal entries pause. The one trade that spans a report is the directional 10–15Δ EARNINGS PLAY
  outside 1.5× the implied move at half size (see below).
- **IV vs realized measures realized vol from before the move** (decided 2026-10-09,
  `thresholds.iv_hv_pre_move`): HV20 for the 1.15× check ends `spike_max_days` before today, so a
  spike doesn't fail the check on its own volatility (CEG +13% on 2026-10-06 read 0.80× instead of
  1.20×). The same pre-move HV feeds the richness score and the earnings-play IV gate.
- **Universe:** FNV (gold royalty) added 2026-10-09 as an opportunistic name in the Hard asset
  bucket beside GLD (shared 10% cap; spikes only; has earnings). RGLD was added and removed the same
  day: over a full day of 15-minute scans no strike in its delta bands had a spread under 40% of
  mid. Liquidity test for a name: if nothing passes even the 40% fallback for days, drop it; FNV
  (puts ~12%, calls ~22%) and CEG (11–30%) are wide but workable with limit orders.
  `data/iv_history/RGLD.csv` is kept in case it's re-added.
- **Thin option markets** (decided 2026-10-09): keep the 10%-of-mid spread rule, but when nothing
  in the band passes it, show the best strikes with spreads up to 40% of mid, flagged "wide market:
  limit order near the mid" (`strikes.wide_spread_fallback`). CEG, FNV and RGLD hit this routinely.
- **No paid IV history for now** (decided 2026-10-09): true IV rank arrives from our own daily
  readings (60 trading days ≈ Dec 29 2026 for names tracked since Oct 2; ≈ Jan 8 2027 for FNV; full
  year ≈ Oct 2027). Until then suggestions carry "check the chain's IV yourself" (`caveat`). ORATS (~$49–199/mo, history to 2007)
  is the option if that changes; its license may not allow publishing its data in this public repo.
- **Strategy history:** the rulebook came out of a separate claude.ai chat; its summary was pasted
  here 2026-10-10 and reconciled. Rules the scanner can't apply because they need positions (per-name
  and bucket caps, 120% beta-weighted delta, 15% LEAP premium cap, circuit breakers, max 3 rungs and
  staggered expiries, ex-dividend early assignment, LEAP 120-DTE exit) stay manual until private
  position tracking exists. Call-strike floors (net cost; LEAP strike + debit) and the High-regime
  LEAP exit ("close half or sell calls") are shown as text in the suggestion.
- **Working style:** Jordan wants to discuss strategy *and* build in the same session. Engage on the
  trading logic (push back, flag rulebook conflicts, suggest tests) — don't just implement.

## Open strategy items (keep current)

- Backtests: first pass built 2026-10-09 (`backtest.py`, results in `docs/backtest/report.md`).
  Findings, 2007→2026, not yet discussed into decisions:
  - Spike-only rules mostly end up *holding assigned stock*: calls need an up-spike with IVR ≥ 50,
    which almost never happens on an index, so QQQ shares are kept (79% of the account in shares,
    premium ~1%/yr). QQQ spikes 14.5% CAGR / −33% max DD vs QQQ hold 15.4% / −54%.
  - Writing calls continuously on assigned QQQ (a turning wheel) collapses it to 2% CAGR: called away
    in rallies, then idle until the next spike. Supports the rulebook's spike-only calls.
  - Tastytrade-style always-on puts did worse than spikes-only in this cash-secured wheel (QQQ 3.2%,
    basket 13.0% vs 15.6%, deeper drawdowns).
  - Basket ≈ index core 50% + satellites (15.6% vs 15.8%); both lean on NVDA/MSTR (hindsight) and on
    the assumed single-stock IV. 2021→: basket spikes 21% / −14% vs QQQ hold 17% / −36%.
  - Regime deltas vs fixed 20Δ: no meaningful difference.
  Still to add: one side vs both; IVR 30/50/70 sweep; 50% vs full call coverage; LEAPs vs shares;
  VIX-scaled deployment (tastytrade 25–50% by VIX). Real option history is paid.
- Schwab developer app (Phase 3 prerequisite; approval can take days). Gives real-time quotes and
  chains with current IV, not a year of IV history.
- Keep MSTR? (IBIT already covers bitcoin.)  XSP/SPX puts (taxable, cash-settled, 60/40) are in the
  rulebook's Index row but not scanned.
- Trade journal: log alerts + Jordan's action for 2–3 months, then tune thresholds. Actions are
  account data → keep them out of this public repo.
- Position tracking (needs private hosting).
- Ladder spacing: the rulebook's "new rung only 5+ trading days later with IVR ≥ 50 (or 1 expected
  move beyond)" is only partly enforced: alerts re-fire at 1 EM within an episode, and any new spike
  after a lapse alerts regardless of the 5-day spacing.

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
  scan.py                  orchestration, action decision, coverage check, JSON output, then alerts;
                           `python -m vol_wheel.scan`
  schedule.py              resolve_mode(): post-close / intraday / skip from the cron string + ET clock
  earnings.py              earnings dates (Nasdaq → yfinance, cached), implied move, ex-earnings IV,
                           earnings-play setup, post-earnings gap
  alerts.py                ntfy messages, dedup against data/alert_state.json, digest, test alert
  backtest.py              Black-Scholes wheel simulation of the rulebook on price + vol-index
                           history: variants from rules.yaml `backtest:`; `python -m vol_wheel.backtest`
data/iv_history/{SYM}.csv  date,iv30 (vol points),price — appended once per market date (post-close only)
data/alert_state.json      alert dedup state (signals only, no account data), written by the workflow
data/earnings.json         earnings cache: next/last report date + timing, implied move (workflow-written)
docs/index.html            static phone-first dashboard (vanilla JS, light/dark) -> data/latest.json
docs/data/latest.json      written by the scan workflow (do not hand-edit)
docs/.nojekyll             serve docs/ as-is on GitHub Pages
tests/                     pytest; conftest.py builds synthetic histories + Black-Scholes chains
.github/workflows/scan.yml post-close 21:35 UTC + intraday 10:30/15:30 ET + manual; commits data
.github/workflows/alert-test.yml  manual "send test alert" to the NTFY_TOPIC phone topic
.github/workflows/tests.yml pytest on push/PR
.github/workflows/backtest.yml  manual: run the backtest, commit docs/backtest/{results.json,report.md}
```

## Running

```
pip install -r requirements-dev.txt
python -m pytest -q
python -m vol_wheel.scan                                   # mode from the ET clock
python -m vol_wheel.scan --mode close                      # post-close: appends IV history
python -m vol_wheel.scan --mode intraday                   # latest.json + alerts only
python -m vol_wheel.scan --symbols SPY,NVDA --no-append --no-alerts --out /tmp/x.json
NTFY_TOPIC=... python -m vol_wheel.alerts --test           # test notification
```

## Schedule and modes (`schedule.py`)

- GitHub cron is UTC-only. Post-close is `35 21 * * 1-5` (16:35 EST / 17:35 EDT; must equal
  `schedule.close_cron` in rules.yaml). Each intraday slot (10:30, 15:30 ET) has two crons, one for
  EDT (14:30/19:30 UTC) and one for EST (15:30/20:30 UTC). `resolve_mode("auto", cron, now)` keeps
  the twin whose ET time is within −20/+55 min of a slot and returns `skip` for the other, so
  exactly one intraday scan runs per slot year-round, even when GitHub starts a cron late.
- Manual runs (`workflow_dispatch`, input `mode`): `auto` = intraday during 09:30–16:00 ET on a
  weekday, post-close otherwise; `close` / `intraday` force it.
- Only `close` appends IV history. Intraday runs rewrite `latest.json` (`scan_mode`, `scan_slot`,
  `scan_et`, shown as a header pill) and send alerts. The commit message names the mode.
- **GitHub's cron is unreliable here** (2026-10-06 → 10-09: the 10:30 ET slot never ran on time,
  post-close started ~21:00 ET). The primary schedule is an outside timer (cron-job.org) calling
  the workflow_dispatch API (`mode: intraday`) every 15 min 10:00–15:45 ET (Jordan's setting,
  live since 2026-10-09; runs take ~45 s) and at 16:40 ET (`mode: close`); setup in
  `docs/SCHEDULE.md`. The GitHub crons stay as a backup.
- `latest.json` is written compact (~16 KB/version compressed) because intraday runs commit it.

## Alerts (`alerts.py`, config `alerts:`)

- After every scan: POST `https://ntfy.sh/$NTFY_TOPIC`. The topic comes only from the
  `NTFY_TOPIC` repo secret (env var); never put it in the repo or logs. Missing secret = skip
  silently and record nothing, so triggers still alert once it's added. Alerting errors never fail
  the scan.
- Title/priority/tags/click are sent as query params (ntfy treats them like headers and they carry
  UTF-8 like "·" and "Δ" safely). Click opens the dashboard.
- Triggers: SELL_PUT, SELL_CALL, LEAP_BUY, PAIR_CALL (Mid regime + IVR ≥ 70 10Δ call add-on),
  EARNINGS_PLAY (tags date + put/call arrow; no rung re-alerts), HEDGE (result-level, state key
  `_HEDGE`). LEAP alerts list both variants.
  Priority high; default when the previous scan saw WATCH ("Upgraded from WATCH"). Tags:
  chart_with_downwards_trend (puts), chart_with_upwards_trend (calls), seedling (LEAPs).
- Dedup in `data/alert_state.json` per ticker + trigger: alert when there is no record or the
  record is inactive from an earlier day; while active, re-alert only at the next ladder rung
  (price one 45-day expected move past the last alerted strike; LEAPs: past the last alerted
  price), up to `max_rungs`. A trigger that lapses and returns the same day is reactivated
  silently. ERROR/NO_DATA cards don't touch state. A failed send isn't recorded (retried next scan).
- Body: price/change, regime, IVR (+source), top-scored strike with expiry, delta, mid, annualized,
  the value reason, and CSP eligibility at `alerts.sizing_tier` ($500k).
- `alerts.daily_digest`: one low-priority post-close message listing WATCH names, once per day.

## Coverage check

`scan.coverage()` compares the output with the universe: `latest.json.coverage` has
`expected/present/missing/failed{sym: reason}/no_chain`, failures also appear as header notes
("Failed: SYM (reason)"), and the job log prints a `coverage:` line.

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
- **Market date = `data.session_date()`**, from the ET clock: before 09:30 ET or on a weekend it's
  the previous weekday, otherwise today. Never derive it from the UTC date or CBOE's timestamp:
  GitHub started the 2026-10-05 post-close cron at 21:51 ET, the UTC date was already 10-06, and
  that run wrote IV history as 10-06 (corrected by hand). `fetch_chain` passes it as the chain's
  `asof`, which drives DTE, IV-history dates and alert dedup dates.
- If today's bar isn't in the history yet, `with_today()` appends the chain quote as today's bar.
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

1. `SELL_PUT`: IVR ≥ 50 + down-spike (larger of the two if both) + iv30 ≥ 1.15 × HV20 measured
   before the move (`hv20_ref`; `hv20` is today's, both on the card).
2. `SELL_CALL`: same with an up-spike, "only if holding shares/LEAPs".
   A spike that fails the IV/HV filter (`thresholds.min_iv_hv_ratio`) or falls in earnings mode
   becomes `WATCH` with the reason spelled out. Cards show IV/HV (green ≥ 1.15, red below).
3. `EARNINGS_PLAY`: see Earnings mode.
4. `LEAP_BUY`: bull gate, regime Low/Mid, consolidation, range pos ≤ 1/3, IVR < 25, core name.
5. `WATCH`: IVR ≥ 50, no spike (or a blocked spike).  6. `NEUTRAL` ("WAIT"): 30 ≤ IVR < 50.
7. `NO_SHORT`: IVR < 30.  `NO_DATA` / `ERROR` last.
- `both_sides`: SELL_PUT in Mid regime with IVR ≥ 70 adds a 10Δ covered call (`pair_call`).
- Put and call candidates and the LEAP candidate are always computed, whatever the action.
- **`t.suggestion`** (`scan.build_suggestion`) is the one trade a card recommends, in words:
  `text` ("Sell TSLA Nov 20 $445 call @ ~$3.80 · half size"), `requires` (covered calls: shares or
  a LEAP), `collateral`/`cost` + `entry_frac` (the dashboard sizes contracts for the selected
  account), `manage` (from `management:` or the pre-earnings rule) and `valid_while`. None for
  WATCH/WAIT/NO NEW SHORTS. The card shows it as a box above the fold and everything else as
  "reference"; alerts open with "→ <text>", "⚠ <requires>", "Manage: …".

## Earnings mode (`earnings.py`, config `earnings:`)

- Single stocks only (`earnings.etfs` = SPY, QQQ, IBIT, GLD have none). Next date + timing
  (BMO/AMC) from `https://api.nasdaq.com/api/analyst/{sym}/earnings-date` (`data.announcement` /
  `data.reportText` text, parsed by regex), yfinance `Ticker.calendar` as fallback, cached in
  `data/earnings.json` (refetched once per session date; on failure the cached date is kept and a
  header note says so). A report that has happened moves `next` → `last`, carrying the implied move
  recorded on the last scan before it.
- Reaction date = report day if BMO, else the next weekday. "In window" = reaction ≤ the chosen
  35–50 DTE expiry; the card shows "Earnings in N days · date timing · implied ±x%".
- **Implied move** = term structure: first expiry after the reaction (E1) vs the next one ≥ 5 days
  later (E2): base² = (σ2²T2 − σ1²T1)/(T2 − T1), jump² = (σ1² − base²)T1, move = jump (1-sd, fraction
  of price). If the term structure reads but shows no bump (jump < 0.5%), there is no earnings
  move and iv30 is used as-is. Only if it can't be read at all does ATM straddle / price stand in,
  and only for an E1 within 7 days of the reaction and 14 days of today (otherwise the straddle is
  mostly base vol: CEG/MSTR showed "±13%" from a 5-week straddle on 2026-10-06).
- **Ex-earnings IV**: when the report is within 30 days, iv30_ex = √(iv30² − jump²·365/30). IVR and
  IV/HV use iv30_ex (badge "ex-earn"); IV history stores raw `iv30` plus `iv30_ex`, and IVR reads
  `iv30_ex` where present. If any step is non-positive → badge "earn-inflated" and normal signals off.
- **Pre-earnings expiry** (`earnings.pre_earnings_expiry`, on by default): when the report falls
  before the usual expiry, strikes, ladder and normal signals use the latest expiry of 21–34 DTE
  that settles before it (on/before the report day for AMC, strictly before for BMO/unknown).
  `t.expiry` is then that expiry, `t.earnings.pre_expiry` names it (+ `take_profit_pct`),
  `spans_trade` is false, and alerts/cards add "take 50% or hold to expiry; don't roll past the
  report". IVR/IV-HV logic is unchanged.
- **Only when no such expiry exists are normal SELL_PUT/SELL_CALL paused** ("earnings mode", with
  "No expiry of 21+ DTE ends before the report"). The only trade through a report is:
- **EARNINGS_PLAY** (always on the usual spanning expiry): report 1–21 days out and before expiry, implied move known, raw iv30 ≥ 1.15×HV20,
  and a 5-day return of ≥ 1σ (HV20·√(5/252)): run-up → sell a call, sell-off → sell a put. Strikes
  10–15Δ and beyond price × (1 ± 1.5 × move) (`strike_limit` in `select_strikes`), same filters
  and scoring, half size (CSP eligibility vs half the entry). Alert "EARNINGS PLAY · SYM".
- Nasdaq usually omits BMO/AMC timing for estimated dates. Unknown timing is treated as "after the
  close" for the term structure (E1 = first expiry after the next weekday) and as "before the open"
  for the gap (pre-report close = the close before the report day), so neither misses the event.
- **Post-earnings gap**: within 3 sessions of the reaction, a move since the pre-report close ≥ 1.5×
  the recorded implied move is forced to count as a spike in that direction (reason says so; the
  card shows "gap"). It still needs IVR ≥ 50 and IV/HV ≥ 1.15 like any spike.

## Strike selection (`strikes.py`)

- Expiry: monthly (third Friday, or Thursday when that Friday is missing) in 35–50 DTE closest to
  45; else any expiry in the window; else closest to 45 (noted).
- Target delta by regime (puts/calls): Low 30/10, Mid 20/20, High 10/30. Band ±7Δ, OTM only.
- Filters: spread ≤ 10% of mid or ≤ $0.10; OI ≥ 100; puts ≥ 20Δ need mid ≥ 1% of strike, else 0.3%.
  If nothing passes only because of the spread, the band is re-filtered at ≤ 40% of mid and the
  picks carry `wide_spread: true` + `spread_pct` (reason "· wide market (N% spread)", suggestion
  "· wide market: limit order near the mid", a "wide · limit near mid" tag on the card).
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
- LEAP: 70–80Δ calls, liquid if possible, lowest extrinsic % of price, in two variants
  (`leap.variants`): IRA 365–548 DTE and Taxable 487–548 DTE ("hold >1 year, don't sell calls
  against"; 487 DTE = held >1 year and still out by the 120-DTE exit). LEAP expiries are sparse
  (Jan plus a few other months), so when nothing is listed in a window the nearest expiry up to
  `fallback_max_dte` is shown with a "no listed expiry … nearest is N months" note.
  `t.leaps = {ira, taxable}`; `t.leap` = the IRA one.
- Hedge (only if `hedge_alerts: true`): when VIX < 14 and SPY is in the High regime, SPY/QQQ puts
  at the expiry nearest 105 DTE within 90–120, strikes nearest 10% and 15% OTM → a card above the
  ticker list and one "HEDGE · SPY/QQQ puts" alert per episode.
- Ladder: rung 1 = top put; rungs 2–3 = 1 and 2 forty-five-day expected moves lower, snapped down
  to a listed strike. IBIT/MSTR use max(iv30, HV20) for the move (weekend gaps).

## Dashboard (`docs/index.html`)

- Reads `data/latest.json` (relative path, works on Pages and `python -m http.server` in docs/).
- Account selector ($25k…$1M, default $500k, remembered in localStorage): entry = 5% of account;
  a put/rung is "CSP ok" when strike × 100 ≤ entry, else "spread / PMCC". Computed client-side.
- Cards sorted by action priority, then spike size, then IVR. Tap to expand.
- Theme follows the OS; the toggle overrides via `data-theme` on <html>.

## Backtest (`backtest.py`, config `backtest:`)

- Runs on Actions only (workflow `backtest`, manual; the sandbox can't reach CBOE/Yahoo). ~1 min of
  data download, then every variant x window; the job log prints one line per run plus the report.
- Signals are the scanner's, vectorized per day (`signal_frame`; a test checks they equal
  `signals.spike`/`proxy_ivr` on the last bar). QQQ/SPY/GLD price options off VXN/VIX/GVZ x
  `vol_index_atm_ratio` and get true IVR + the IV/HV gate. Other names: IV = `stock_iv_mult` x
  max(HV20, HV60), proxy IVR, no gate; run at each of `stock_iv_mults` because that multiple *is*
  the single-stock edge and it's assumed.
- Lifecycle: 45 DTE, close at `management.take_profit_pct`, at `decide_dte` close if OTM else hold
  to expiry and take assignment (`decide_itm: roll` rolls once), covered calls on assigned shares
  (spike mode: on up-spikes; always mode: continuously; momentum names 50%; strike ≥ net cost in
  Low/Mid), caps per name/bucket/total, circuit breakers. Fractional contracts, T-bill yield on cash.
- Modes: `spike` (rulebook), `always` (a put every `entry_every_days` while IVR ≥ `min_ivr`,
  tastytrade-style), `hold` (buy-and-hold at `weight`%, monthly rebalance).
- Known biases: today's universe applied to the past, no dividends, no earnings IV, BS prices.

## Conventions

- Python 3.11, deps: requests, pandas, numpy, pyyaml (+ optional yfinance). Keep it that way.
- Signal and scoring functions stay pure and take Series/DataFrames, so tests use synthetic data.
- Never commit account balances, positions, or broker credentials.
- `docs/data/latest.json` and `data/iv_history/*.csv` are written by the workflow; don't hand-edit.
