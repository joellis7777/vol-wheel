# Recommended strategy build (living document)

Claude's current recommendation from everything tested and ingested so far. It changes as research and
backtests come in; each change is dated in the log at the bottom. Percentages are of the whole account
(IRA + taxable together); no balances or positions belong here (public repo). Evidence lives in CLAUDE.md
("Open strategy items") and `docs/backtest/report.md`; source notes in the private research folder.

Last updated: 2026-10-11.

## The one-paragraph version

Own the right assets and let a mechanical trend signal decide how much of each to hold; use options to
enter and trim more cheaply, not as the return engine. Every test says the return comes from what you own
(QQQ, gold, bitcoin) and the drawdown is set by the exit rule; premium selling in a cash-secured IRA earns
T-bills + 1–3%. So: a trend-managed core, a T-bill reserve that doubles as put collateral, and two small,
rule-bound satellites (an MSTR/IBIT long-call sleeve and stock picks) for upside.

## The build

| Sleeve | Weight | What it holds | Rules | Where |
|---|---|---|---|---|
| **Core** | 65% | QQQ 35 / GLD 35 / IBIT 20 / XLE 10 (of the core) | Held, no trend exit (Jordan: buy dips, don't sell them). Scale out as each name's bull run matures: a cap by its gain from the 3-year low (QQQ/GLD/XLE 90% at +50% → 50% at +150%; IBIT 85% at +200% → 30% at +1500%), so the account is light going into the next bear; trades in stock (options lag the targets) | IRA |
| **Reserve** | 20% | SGOV | Pyramid fund: each core name has its own range, from its base weight at the high to fully invested near its historical worst drawdown (QQQ −80%, GLD −45%, IBIT −80%, XLE −75%); add at each step by stock or 16Δ cash-secured puts on IVR ≥ 50 down-spikes; trim back to base as new highs return | IRA |
| **Convexity sleeve** | ≤ 5% at risk | MSTR (or IBIT) long calls | ~15–25Δ, ~15 months out, 1–2% of the account per position, sell half at +100%, rest out at 60Δ or 90 DTE, re-enter as a roll; no entry filter | IRA (or taxable for > 1-year holds) |
| **Stock picks** | ≤ 10% | 5–10 names | See "Stock picker" below | Taxable (long-term holds) or IRA |
| **Long-term taxable** | rest of taxable | Buy-and-hold core names | No short calls against LEAPs/shares held for long-term gains (tax straddles) | Taxable |

Why these numbers:
- Bitcoin weight is the main dial: every 10% of the core in bitcoin added ~5–6%/yr and ~4–6 pts of max
  drawdown over 2016–26, at the same Sharpe (~1.38). Start-every-January medians, monthly exits: BTC 30%
  30.9% / −29.5% worst DD; **BTC 20% 25.5% / −21.8%**; BTC 10% ~16–17% / −16%. For a large account aimed
  at steady gains, 20% balances Jordan's bitcoin conviction (~13% of the whole account) against drawdown.
  These numbers carry bitcoin's 2016–21 hindsight; read them as relative, not as forecasts.
- XLE 10% cut the 2022 loss (2022 −5% vs −9 to −11%) and is uncorrelated with gold.
- Cycle (pyramid in + scale out, Jordan 2026-10-11): best risk-adjusted core tested. 2015→ 21.8% / −20%
  max DD, 2022 −14%, Sharpe 1.45 vs pyramid-only 24.8% / −26% (2022 −19%) and held 30.2% / −31% (−23%).
  It gives up ~3%/yr in a mostly-bull decade for a lighter account into bears. Execute with stock: done
  through puts and assigned calls the same targets earned 16.3% (options lag the targets).
- Exit rule: none on the core (Jordan's call, 2026-10-11). Tested cost vs the trend-exit core (2015→): ~25% /
  −26% max DD and ~−19% in 2022 vs ~22% / −21% and −6%; in a 2000-style bear (not in our data) the gap would
  be larger, which is why the pyramid ranges go deep (QQQ fully invested only at −80%).
- Convexity sleeve: 15Δ with exits beat 40Δ (with or without Soliel's trend filter) on MSTR, QQQ, NVDA,
  TSLA and modelled BTC, in start-every-January windows too, and still with LEAPs priced 20% richer. It is
  a bull-market result (2009–26) and bleeds in flat years, so keep it small: 1–2% of the account per
  position, ≤ 5% at risk, on IBIT or MSTR.

## What to implement

Built 2026-10-11: items 1 (core pyramid panel + ADD/TRIM alerts), 4's alerts pending, 5 (picks watchlist status + ENTRY/EXIT alerts) and the bitcoin warning.


1. Core pyramid on the dashboard: each core name's drawdown from its high, target invested % from its range,
   the price of the next add step, and alerts when a step is crossed (add) or new highs return (trim);
   trend state shown for information, plus a bitcoin daily warning. This replaces "spike = sell put"
   as the main signal.
2. Put entries on core names: the existing SELL_PUT alert, but only when the name is under its target
   weight, at 16Δ, using reserve cash. 16Δ beat 30Δ on drawdown; IVR ≥ 50 helps a little.
3. Up-spike calls only on volatile core names (IBIT, MSTR) and only on shares above target weight:
   on MSTR they added ~3.5%/yr and cut the drawdown 18 pts; on QQQ they don't matter.
4. Convexity sleeve signals: entry / half-off / 60Δ / 90-DTE alerts.
5. Stock-picks watchlist with entry/exit alerts (below).

## What not to do (tested and rejected)

- Continuous covered calls on core shares (QQQ 2% CAGR; Sosnoff's 30Δ-below-basis rule is this).
- Poor man's covered calls (Tom King's rules 1.4%; LEAPs ~7%/yr behind shares at equal notional).
- Rolling for credit as a return source (QQQ 4.7% vs 5.0%; MSTR 23% vs 28%).
- Put credit spreads in the IRA as the income engine (0.4% / −24% for a 6-ETF book).
- A tastytrade-style premium book as the main strategy (3.9% / −16%; fine as a bond substitute only).
- Pyramiding put *size* inside a capped wheel ("start small, add bigger lower" per trade): no gain in any
  book tested; flat-sized puts did better across start dates. Pyramiding *total exposure* with the reserve
  is different and is adopted above (Reserve row).
- Bigger trades after a loss: tastylive's 2021–26 SPY study found doubling size after each losing trade
  wiped out the period's gains; losses cluster with volatility, so size-ups land in the worst stretches.
- Selling MSTR puts whenever premium looks rich: the edge is IV above the realized vol that follows
  (IV = realized → about 0%); only sell when IV ≥ 1.15 x realized vol (the scanner's gate).
  On indexes IV sits above realized most days (SPY ~84% of days 2016–26, tastylive), so the gate rarely
  binds there; on single names it is the main safeguard (MSTR read 0.78x in Oct 2026).
- Standing collars or always-on puts (QQQ always collared 6.0%; collars on the BTC core cost ~19%/yr).
- The 16Δ / IVR ≥ 50 wheel as a standalone strategy (median 2.5–2.8%: it only works if a crash assigns
  it early).
- Leverage, personal loans, concentration (every Soliel blow-up), and calendar-timed exits (the cycle
  thesis sets readiness; the trend signal triggers).
- EARNINGS_PLAY: no support from tastylive's earnings study or our data; keep earnings mode (avoid).

## Stock picker (proposed design, not built)

Goal: a high-return satellite (≤ 10% of the account) that needs no daily watching. Picks come from
people and theses (Jordi Visser, Jordan's research); the system handles entries, sizing and exits.

- Watchlist in rules.yaml (`picks:` symbol, thesis, source, date added). No positions or sizes owned.
- Entry: the name is in a full trend state (above a rising 200-day) and in the top third of the watchlist
  by 6- and 12-month relative strength vs QQQ; enter on a pullback (a down-spike) via a cash-secured put
  or shares. Never enter in the "out" state, however good the story.
- Size: 1–2% of the account per name at cost, max 10 names, sleeve cap 10%; no averaging down below the
  200-day.
- Exits: state goes to "out" (below a falling 200-day) → sell; or a 25–30% trailing stop from the high;
  sell half at +100% and let the rest run with the trailing stop; thesis review each quarter.
- Trims: up-spike calls on at most half the shares of winners (momentum-name rule).
- Draft watchlist (rules.yaml `picks:`, 2026-10-11): 12 names from Jordi Visser's last 12 episodes. On
  2026-10-08 data the ones passing entry (rising 200-day + strong 6/12-month RS vs QQQ) were MU, MRVL, LITE,
  with PLTR, NVDA, GOOGL, LLY above their 200-day but middling on strength; HOOD, COIN, ETHA, SLV, TSLA
  failed (half or out). Visser himself says he isn't a stock picker and recommends baskets: a thematic
  ETF (e.g. a semiconductor fund) is the low-maintenance alternative for part of this sleeve.
- Open design question to test: top-third relative strength (momentum) vs Visser's "comb the rubble"
  (strongest trend, deepest pullback) for entries.
- Testing: pick selection can't be backtested without hindsight; the exit and sizing rules can be tested
  on a list (with that caveat), and the live sleeve gets a private trade journal from day one.

## Next tests that could change this

1. Done 2026-10-11: monthly combo exits beat the daily signal; bitcoin 20% of the core chosen.
2. Done 2026-10-11: the sleeve holds on QQQ, NVDA, TSLA, BTC. Still to do: real MSTR/IBIT LEAP bid/ask from
   the scanner's chains.
3. Reserve put entries: core + 16Δ put entries on dips vs buying at the next rebalance.
4. Stock-picker exit rules on a list of momentum names (with a hindsight caveat).
5. Done 2026-10-11: Jordi Visser ingest → draft watchlist. Next: scanner support for `picks:` (states,
   RS rank, trailing stop, half-off alerts) and a momentum-vs-rubble entry test on a name list.

## Change log

- 2026-10-11 (later): core scales out as bull runs mature (cycle plan); trades in stock, not via assignment.
- 2026-10-11 (later): no trend exit on the core (Jordan); per-ticker pyramid ranges to each asset's worst drawdown.
- 2026-10-11 (later): reserve becomes a pyramid fund for core dips in uptrends (beat an idle reserve).
- 2026-10-11 (later): draft picks watchlist from Jordi Visser; picker entry question (momentum vs rubble) added.
- 2026-10-11 (later): scale-in by trade size tested: no gain; keep flat sizes with caps and the reserve.
- 2026-10-11 (later): convexity sleeve confirmed beyond MSTR (15Δ > 40Δ on every name tested); MSTR
  premium explained (the edge is IV vs later realized vol, not the premium size).
- 2026-10-11 (later): core switched to QQQ 35 / GLD 35 / IBIT 20 / XLE 10 with monthly combo exits
  after the start-every-January runs (daily three-state signal and the hybrid rejected).
- 2026-10-11: first version, after research batches 1–2 (Soliel, tastylive, Tom Sosnoff, 42 Macro) and
  the tastytrade-book, start-date, MSTR sleeve and KISS tests.
