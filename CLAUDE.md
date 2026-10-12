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
- **The rulebook is a starting hypothesis, not a constraint** (Jordan, 2026-10-11): the goal is to
  find the best strategy by testing every idea (ours, tastytrade's, Soliel's, others), and the
  result may differ from the original rulebook. Flag conflicts with the decisions above, but don't
  treat drift away from the wheel as a problem in itself. Sources: tastytrade (Jordan rates it
  highly; plus Tom Sosnoff's own post-tastylive YouTube channel "More Tom Sosnoff", added 2026-10-11) and Soliel, who applies the same ideas to high-vol names with conviction in MSTR, ASST and
  other bitcoin plays, plus some non-bitcoin names like TSLA. Research notes live in the private
  `~/vol-wheel-research/` (notes/, brain.md), never in this repo.

## Current recommendation (keep current)

`docs/STRATEGY.md` is Claude's living recommendation for the whole build (sleeves, weights, what to
implement, what not to). Jordan asked for it on 2026-10-11 and wants it updated whenever research or a
backtest changes the picture: edit it in the same change and add a line to its change log.

## Jordan's thesis and goals (views, not decisions — keep current)

- **Cycle thesis (2026-10-12):** a market dump in Q4 2026 → easing and more money printing (like
  the Covid response) → a 2027–2029 bull like 2020–21 (BTC best, then gold, then QQQ; likely rising
  together) → inflation forces a tightening cycle and a 2022-style bear in 2030 (late 2029 top).
  Gold tends to recover first. Matches bitcoin's halving cycle (2028 halving → top ~late 2029).
  Pushback given: single-analog forecast; the plan must still work if the timing is wrong, so
  mechanical trend exits trigger the defence and the calendar only sets readiness.
- **Goals:** consistent income/gains from a large account over catching every bit of upside;
  believes in BTC and wants real exposure; likes tastytrade's mechanical, everyday approach;
  wants roughly equal QQQ / GLD / bitcoin (IBIT or MSTR), less XLE for now.
- **Leanings under discussion (not decided):** defend a 2022-type bear with energy/commodities,
  the dollar and T-bills rather than TLT; deep-OTM LEAP calls (Soliel-style, e.g. MSTR 2028) as a
  small convexity sleeve; LEAP puts vs short puts vs defensive weights as bear preparation.
- **Wants a research "brain":** Soliel (Nithu Sezni) and Tom Sosnoff/tastylive videos plus this
  project's debate, ingested and testable. Handoff steps and prompt: `docs/HANDOFF.md`.

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
  - Jordan's scale-in/scale-out plan (2026-10-11: always deployed, puts on cash, calls on shares,
    regime deltas) works mechanically (QQQ: 36% in shares at Low, 6% at High) but returns 5% CAGR
    with −39% max DD. The calls cost it: same puts with calls on half the shares 6.5%, calls only in
    High regime 8.1%, calls only on up-spikes 14.8% (≈ QQQ hold 15.4%, max DD −39% vs −54%; 2021→
    13.1% / −17% vs 16.6% / −36%; 2022 −14% vs −34%). Always-on puts fix QQQ-spikes' idle capital
    (2021→ 7% → 13%). VIX-scaled cap: small risk cut (2022 −13.5% vs −17%), ~0.3%/yr less. 40Δ puts
    at lows: no gain. Open question for Jordan: QQQ puts always on + calls only on up-spikes / High?
  - Tom King's dynamic PMCC (2026-10-11, `qqq_pmcc_tom`; 100% notional, LEAP debit ~18% of the
    account): 1.4% CAGR / −27% max DD vs LEAP alone with his filter + exits 7.7% / −33%, LEAP held
    8.4% / −55%, QQQ 15.4% / −54%. His weekly calls collect ~48%/yr of equity in premium but lose
    ~7%/yr net (10%/yr with weekly IV at 0.9× VXN); worst in whipsaw years (2011, 2015-16, 2018).
    2023 (a year he'd call favorable): PMCC +14% of the account ≈ +60% on the debit, LEAP alone
    ≈ +220% on the debit. LEAPs vs shares at equal notional: ~7%/yr behind (time value, 85Δ).
    His entry filter + −30% stop is the useful part (max DD −55% → −33%).
  - Assignment is rare (2026-10-12): always-on puts 2–7% assigned (90%+ close at 50% or at 21 DTE),
    spike puts ~22% (QQQ), calls 0% called away when spike-only, 4–7% when always on.
  - TA/rolling ideas (QQQ): 21-DTE 40Δ puts at lows + calls only on up-spikes 15.2% / −39% (best
    tested; puts-always-hold 14.8%). Roll ITM both sides for credit ("roll until you're right") 4.7%
    / −33% (vs 5.0% unrolled; 2022 −9.5% vs −13.5%). Far-OTM calls rolled up, assigned only in the
    High regime: 5.0% (QQQ "tops" mostly aren't; cash then sits idle).
  - MSTR 2020-09→: hold 80% 46.7% / −82% (2022 −63%); puts always + spike calls 28.7% / −63%;
    as Jordan described (40Δ puts at lows, calls rolled until tops) 28.2% / −65%; + puts rolled
    23.0% / −61%; Nithu Sezni's posted call rule 22.9% / −68%; spikes only 12.3% / −40%. Single
    path, modelled IV (18.8–34% across IV mults for the described version).
  - Target allocation by drawdown (2026-10-12, `mode: target`; Jordan's scale-in/out plan as a rule):
    QQQ 40%→100% shares: options 9.6% / −37% (vol 13%, 2008 +12%, worst 12m −32%) vs stock 10.1% /
    −41% (2008 +2%, worst 12m −38%); 60%→100%: options 11.9% / −40% vs stock 12.0% / −46%. Same
    return either way, options smoother. MSTR 15%→100% (from the 1000-day high): options 28.0% / −67%
    vs stock 23.4% / −79% (options better on a high-IV name; 23–34% across IV mults), hold 46.7% /
    −82%. Being light near highs costs return on a trending index (best QQQ wheel 15.2% / −39%);
    drawdown-based buying on MSTR hits 100% at −70% and then rides the rest of a −90% fall.
  - MSTR target 2022 diagnosis (monthly trace): ~0% shares Sep 2020–Nov 2021 (puts never assigned in
    the 10× run), then assigned all the way down: 2% Dec 2021 → 40% Feb → 67% Mar → ~90% Jun–Dec 2022
    (plus ITM puts acting like shares) → 2022 −62%, 2023 +326%. Fixes: deeper schedule (100% only at
    −88%) 25.3% / −42% (2022 −35%, 2023 +181%); + trend cap 40% below a falling 200-day 20.0% / −35%
    (2022 −27%, 2023 +105%); + 10Δ core calls in the Low regime 18.4% / −34% (premium helped 2022 by
    ~1 pt, capped the 2023 rebound). QQQ trend cap 60%: 11.2% / −32% vs 11.9% / −40%.
  - Diversify vs rotate (2026-10-12, hold mode `weights` / `rotate`): 2007→ QQQ/GLD 70/30 14.4% /
    −41% (Sharpe 0.80), 50/50 13.3% / −34% (0.82, 2008 +18%) vs QQQ 15.4% / −54% (0.69); dual-momentum
    rotation QQQ↔GLD 11.2% / −33% (0.57: lags, whipsaws). From 2015-10 (Yahoo BTC-USD, hindsight
    start): QQQ/GLD/BTC 60/25/15 28.7% / −37% (vol 19%, Sharpe 1.29, best risk-adjusted tested);
    QQQ/BTC 80/20 33.4% / −45%; rotation QQQ/GLD/BTC 56% / −82% (momentum too slow for BTC crashes);
    BTC hold 70% / −83%; QQQ hold 19.8% / −36%. Deep vs original MSTR schedule over 2022+2023
    combined: 1.82× vs 1.60× (deep lost less in 2022; held fewer shares in the 2023-24 rebound).
  - Diversifier candidates (2026-10-12, monthly-return correlations since 2015-10, report table):
    QQQ–GLD 0.07, QQQ–BTC 0.30, GLD–BTC 0.09, QQQ–XLE 0.30, GLD–XLE 0.00, QQQ–TLT 0.23 (TLT −33% in
    2022), XLE +58% in 2022; SPY–QQQ 0.91, FNV–GLD 0.73, SLV–GLD 0.77 (redundant). From 2015-10:
    QQQ/GLD/BTC 60/25/15 28.7% / −37% (2022 −31%); + XLE (50/20/15/15) 27.6% / −31% (2022 −23%,
    worst 12m −28%); + TLT 25.1% / −38%; + XLP 26.7% / −34%. 2007→: QQQ/GLD 60/40 13.9% / −37%;
    QQQ/GLD/XLE 13.3% / −43% (XLE fell with stocks in 2008); QQQ/GLD/TLT 12.3% / −35%.
    Jordan is leaning to a core of QQQ / gold / bitcoin + XLE (energy: "seems like a good idea",
    2026-10-12) traded with options; Honeycomb = a defensive sleeve for the late-2029 bear he expects.
  - Core rebalanced with options vs stock (2026-10-12, `mode: multi`, 2% band, from 2015-10):
    QQQ/GLD/BTC 60/25/15 stock 29.2% / −36% vs options 28.3% / −35% (27.9–30.0% across IV mults;
    premium ~3%/yr, stock turnover 1% vs 28%/yr); +XLE 50/20/15/15 stock 27.9% / −31% vs options
    28.1% / −31% vs hybrid (stock for gaps > 8%) 26.8% / −30% (2022 −20%, worst 12m −25%, steadiest);
    80% invested (SGOV 20%) options 22.0% / −26% ≈ monthly-rebalanced 80% mix 22.4% / −25%. 2007→
    QQQ/GLD/XLE stock 13.1% / −44% vs options 13.6% / −42%. Execution is second-order (±1%/yr); the
    mix drives results. Options lag the targets (fully invested = no cash for puts until calls are
    exercised), so they run below target weights and the premium roughly makes up for it.
  - Equal-weight core + 200-day exit (2026-10-12, hold `trend_sma: 200`: a name below its 200-day at
    the monthly check sits in T-bills; Jordan wants ~equal QQQ / GLD / BTC, less XLE, and a way to
    protect gains before the late-2029 bear he expects). From 2015-10: equal QQQ/GLD/BTC 39.5% / −45%
    (2022 −35%, 2018 −30%) vs with the exit 33.5% / −29% (2022 −9%, 2018 −19%; ~25% of name-months in
    T-bills); 30/30/30 + XLE 10 with the exit 31.1% / −27% (2022 −3%). From 2020-09: equal with BTC
    26.9% / −45% vs exit 26.8% / −23% (no cost); with MSTR 37.1% / −52% vs exit 40.1% / −38% (2022
    −2%). 2007→: QQQ hold 15.4% / −54% vs exit 12.7% / −29% (2008 −16% vs −42%; whipsaw cost in 2010,
    2015-16, 2019, 2025); QQQ/GLD equal 13.3% / −34% vs exit 10.3% / −18%. A monthly check misses
    fast crashes (2020 drawdown unchanged). Equal weight with BTC's hindsight 2017 (+224% for the mix)
    is why 2015→ CAGRs are so high.
  - Defensive-exit refinements (2026-10-12; hold `trend_arm`, `trend_falling`, `trend_to`, `collar`):
    (a) Arming the exit only after a High regime (stretched market) misses tops that weren't stretched:
    QQQ 2007→ 11.8% / −54% (2008 −42%, not caught) vs plain exit 12.7% / −29%. Exiting only below a
    *falling* 200-day is the best QQQ rule: 14.7% / −29% vs hold 15.4% / −54% (2008 −21%, 2022 −18% vs
    −34%; ~11% of months out). On the BTC core it is slower: equal QQQ/GLD/BTC falling 34.9% / −31%
    (2022 −18%) vs plain 33.5% / −29% (2022 −9%); QQQ/GLD 2007→ 11.5% / −21% vs plain 10.3% / −18%.
    Untested: plain exit for BTC + falling exit for QQQ/GLD. (b) Exited weight to the best-trending
    of TLT / UUP instead of T-bills: ~+1%/yr on mixes (QQQ/GLD 11.4% vs 10.3%, worst 12m −7.5% vs
    −12.6%; core 34.4% vs 33.5%), nothing on QQQ alone (TLT/UUP fell in the 2009 rebound); + XLE as a
    destination 36.8% / −36% (2022 +11%, but 2018 −26%). (c) Collars (10% put, zero-cost call, 6m,
    re-struck quarterly, skew scaled by √(45/DTE)): always-on QQQ 6.0% / −25% (≈ −10%/yr option
    P&L); only in the High regime 12.2% / −54% (didn't cover 2008/2022); 10% puts only in High 14.7%
    / −54% (−0.8%/yr, 2020 +44% vs +32%, nothing in slow bears); on the BTC core collars cost
    ~19%/yr (2017 +24% vs +224%). Fast crashes are what the monthly trend exit misses and puts catch.
  - Combined exit plan (2026-10-11, `eq_qgb_combo*`: plain 200-day exit for BTC, exit below a falling
    200-day for QQQ and GLD, optional 10% QQQ puts in High). Equal QQQ/GLD/BTC from 2015-10: combo 34.7%
    / −32% (2022 −11%, Sharpe 1.36) vs plain exit on all 33.5% / −29% (2022 −9%, 1.34) vs falling on all
    34.9% / −31% (2022 −18%). From 2020-09: 27.9% / −25% vs 26.8% / −23% vs 27.4% / −31%. With MSTR for
    BTC: 41.4% / −40% vs 40.1% / −38%. 30/30/30 + XLE 10 (XLE falling too): 32.4% / −30% (2022 −6%) vs
    31.1% / −27% (2022 −3%). So the combo buys ~1%/yr for ~2 pts of extra drawdown: a trade-off, not an
    improvement. QQQ-only 10% puts in High cost only 0.2–0.3%/yr here (on 39–47% of days), lift 2020
    (+80% vs +76%) and Sharpe (1.39), max DD unchanged (−32%). Spike-only calls not modelled in hold
    mode (earlier: ~+0.1%/yr on a LEAP).
  - tastylive management/entry studies on the best QQQ wheel (2026-10-11, `qqq_puts_hold_*`; base =
    always-on puts + up-spike calls 14.8% / −39%, 2021→ 13.1% / −17%). Close ITM puts at 21 DTE instead of
    taking assignment (tastytrade's way): 4.1% / −17% (2008 +0.1%, 2022 −1.2%; 2021→ 6.6% / −6.5%), i.e.
    a T-bill-plus income stream: almost all of the wheel's return comes from the assigned shares (84% of
    the account), not the premium. Profit target 25% ≈ 50% (14.8%); 75% 13.7%, none 13.5%: supports
    closing at 50%. Fixed 16Δ puts: 14.6% / −33% (2008 +14%; 2021→ 10.3% / −10%, Sharpe 0.91) vs 30Δ
    14.8% / −38%: 16Δ is the better risk trade. IVR ≥ 50 to sell: 15.0% / −38% (2021→ 14.0%, 2022 −5%
    vs −14%); IVR ≥ 30 ≈ none. tastylive's 25→50% buying power by VIX: 12.6% / −31%. Knobs added:
    per-variant `take_profit_pct`, `decide_itm: close`.
    Combined: 16Δ + IVR ≥ 50 = 15.4% / −33% from 2007 (2008 +19%; ≈ QQQ hold's CAGR at −33% vs −54% DD)
    but 4.6% from 2021 (9% deployed, never assigned, 91% cash). **The hold-to-assignment wheel is
    path-dependent**: its return is set by whether an early drawdown puts it into shares, which it then
    keeps (calls only on up-spikes). Judge wheel variants on several start dates, not one window.
    16Δ + 25% target: 14.8% / −35% (2021→ 10.0% / −10%).
  - One side vs both (2026-10-11, `calls: none` = puts only, assigned shares never written against):
    QQQ puts only 14.7% / −39% vs + up-spike calls 14.8% / −39% (16Δ IVR ≥ 50: 15.3% / −35% vs 15.4% / −33%):
    on an index the spike calls barely matter (few up-spikes). MSTR puts only 25.2% / −81% vs + up-spike
    calls 28.7% / −63%: on a high-vol name the spike calls add ~3.5%/yr and cut the drawdown 18 pts.
    Keep spike-only calls for volatile names; on QQQ they're optional.
  - MSTR long-call convexity sleeve (2026-10-11, `mode: sleeve`, `mstr_sleeve*`): each position costs 5% of
    equity (rest T-bills), ~456 DTE, half off at +100%, rest out at 60Δ or 90 DTE, re-enter = roll.
    Account CAGR / max DD from 2020-09 | from 2021: 5% in shares 7.5% / −9% | 6.7%; Soliel's 2026 rule
    (40Δ, above 200-day + higher high/low, not after a 30% pump) 5.0% / −8% | 3.7%: worse than shares;
    40Δ no filter 13.1% / −10% | 9.1%; 25Δ no filter 17.0% / −13% | 10.6%; **15Δ no filter 30.9% / −14%
    | 16.6%** (10 positions, 8 winners, payoff 3.1×, best 13.9×); 15Δ above the 200-day 29.8% / −14% |
    15.6%; 70Δ 7.1% / −29%; call debit spreads 40/28 and 40/15 1–3% (the short leg caps the runs that pay).
    Jordan's unmanaged version (15Δ, no exits but 90 DTE) 48.5% / −73% | 24.5% / −66%: one or two trades
    (84×, 58×) grow until they are the account; that's a concentrated bet, not a sleeve. Robust across
    IV mults (15Δ 28.5–31.0%) and skew (flat 17.7%, upside 14.1% with the stricter filter). So: deep OTM
    beats 40Δ here, and the entry filter (esp. the "not after a pump" rule) is what costs; the exits
    (half at +100%, 60Δ, 90 DTE) are what keep it a sleeve. Caveats: ~8–10 positions on one path whose
    gains come from the 2020–21 and 2024 bitcoin runs; modelled IV (HV-based) and BS prices, while real
    MSTR spreads on far-OTM LEAPs can be ~10–50% of the debit (`slippage_pct`, default 5% per leg).
  - Fair tastytrade book in an IRA (2026-10-11, `tasty_*`; SPY/QQQ/IWM/GLD/TLT/XLE, 16Δ puts ~45 DTE, a new
    put per name every 5 sessions, close at 50% or 21 DTE, never assigned, no calls). 2007→: cash-secured
    3.9% / −16% (2021→ 6.6% / −2.4%); 16/5Δ put spreads at 1.5% max loss each, 25–50% total risk by VIX
    0.4% / −24% (the wing costs more than it saves under skew; tastylive's own narrow-spread study agrees);
    IVR ≥ 30 filter lowers both. Same 6 ETFs as our wheel (16Δ held to assignment, up-spike calls) 10.4% /
    −25% vs SPY hold 8.9% / −57%. Blends (`mode: blend`, monthly rebalance): Tom's 30% book / 30% SPY / 40%
    T-bills 4.7% / −20% (CSP) or 3.6% / −24% (spreads); 60% QQQ/GLD falling-exit core + 30% CSP book + 10%
    T-bills 8.3% / −16%; 60% core + 40% 6-ETF wheel 11.2% / −21%; BTC core 60% + 30% CSP + 10% T-bills
    22.2% / −21% (core alone 34.7% / −32%). In cash-secured form the premium book is a T-bill-plus-1–3%
    sleeve: it lowers drawdowns, it doesn't compound.
  - Start-date robustness (2026-10-11, `backtest.rolling`, every January 2007→, vs QQQ hold). Median CAGR
    3y | 5y windows (worst): QQQ falling-200 exit 14.1% | 14.7% (4.7 | 8.4), max DD −29%, the most robust;
    QQQ/GLD falling exit 9.8 | 10.8; QQQ wheel puts-always + spike calls 6.6 | 7.8 (3.8 | 5.5); **16Δ IVR ≥ 50
    wheel 2.5 | 2.8**: its 15.4% from 2007 was the 2008 assignment, not the rule; tasty CSP book 3.0 | 2.8
    (0.6 | 1.7, DD −16%); spreads 0.1 | −0.2; 6-ETF wheel 5.8 | 5.7; blends core + CSP 7.8 | 7.4, core + wheel
    8.3 | 9.5 (DD −19%); Tom's split 4.5 | 4.7; SPY hold 9.4 | 12.5 (worst −8.2 | −2.4, DD −57%). QQQ hold won
    most windows (2009–26 bull): beat rates 0–33% for everything but the BTC core (88–100% of 6–8 windows
    from 2016, hindsight start). Caveat: option prices are modelled (index IV = vol index × 0.9, BS, skew);
    real fills could make the premium book somewhat better or worse, not a different order of magnitude.
  - 42 Macro KISS (2026-10-11, `kiss*`, `run_states`; spec and sources in the private research folder): 60%
    stocks / 30% gold / 10% bitcoin, each scaled daily by its own trend state (1 / 0.5 / 0; our 200-day proxy
    for their unpublished signal), next-close trades, rest in T-bills. From 2018: KISS 11.9% / −18% (2020 +11%,
    2022 −13%) vs the same mix without the signal 16.6% / −26% vs 60/40 7.2% / −22%. 42 Macro claims ~14–16%
    CAGR (their "20–26%" is an arithmetic mean) with −11 to −12% max DD; the proxy lands near, not on, that.
    The half state is the useful part: same daily signal but all-or-nothing 11.4% / −26%. Regime-vote proxy
    (SPY/IWM/EFA/EEM/HYG) 11.5% / −16% (2022 −9%). QQQ instead of SPY 17.2% / −21%. Our assets (equal QQQ /
    GLD / BTC) with the KISS signal: 33.0% / −27% from 2015-10 vs our monthly combo exit 34.7% / −32%; from
    2018 19.7% / −26% vs 22.8% / −30% (daily checks catch fast crashes but cost the V-rebounds: 2020 +59% vs
    +76%). 2007→ without bitcoin: SPY 60 / GLD 30 / T-bills 10 with the signal 6.7% / −16% vs held 8.9% / −35%.
    Same lesson as before: the weights (bitcoin share, QQQ vs SPY) set the return; the signal sets the
    drawdown, and a 3-state daily signal buys ~5 pts of drawdown for ~1–3%/yr.
  - Core design, start-every-January (2026-10-11, `core_*`, `qqq_states`, `eq_qg_states`, `qg_x_*`). 2007→ (no
    bitcoin; 17 3y / 15 5y windows), monthly falling-200 exit vs daily 3-state, median CAGR: QQQ 14.1 | 14.7
    vs 11.5 | 12.2; QQQ/GLD 9.8 | 10.8 vs 6.8 | 7.8; QQQ/GLD/XLE 45/45/10 9.6 | 9.9 vs 6.7 | 8.4, worst DD
    about equal (−29 vs −25, −21 vs −22, −20 vs −21): the daily signal costs 2–3%/yr for nothing on the long
    history. With bitcoin (2016→, 8 | 6 windows, QQQ/GLD/BTC/XLE 30/30/30/10): held 34.0 | 34.7 / −38%;
    monthly combo 30.9 | 31.9 / −29.5%; daily 3-state 27.5 | 26.0 / −24.7%; BTC daily + rest monthly (blend)
    28.8 | 27.7 / −27.4%. Bitcoin weight with monthly combo exits: 30% 30.9 / −29.5%, 20% (35/35/20/10)
    25.5 | 26.3 / −21.8% (full window 26.1% / −21.8%, Sharpe 1.38, 2022 −5%), 10% (daily) 16.4 | 17.1 / −16.2%.
    Chosen for docs/STRATEGY.md: 35/35/20/10 with monthly combo exits.
  - Why MSTR premium (Jordan sees ~5% of capital per 45-DTE put) doesn't become a big return (2026-10-11,
    `mstr_csp*`; 30Δ puts, close at 50% or 21 DTE, never assigned, from 2020-09). Gross credits are large
    (52%/yr of equity at ~25% deployed; 129%/yr kept ~60% deployed) but net CAGR is 10.2% / −22% and 16.4% /
    −45% (2022 −35%): buybacks of the ~1 in 3 puts tested by 21 DTE give most of it back. Net depends almost
    entirely on IV vs the realized vol that follows: at IV = 1.0x HV the fully deployed book makes −1.2%, at
    1.15x 16.4%, at 1.3x 31.5%. Real MSTR iv30 on 2026-10-02..09 was ~63 vs HV20/HV60 ~80 (0.78x), i.e.
    below realized: premium that looks rich can still be a losing sale. This is what the IV/HV ≥ 1.15 gate
    is for. Selling puts also caps the upside: MSTR held +250% (2023) and +294% (2024).
  - Convexity sleeve beyond MSTR (2026-10-11, `*_sleeve15/40`, no entry filter, 5% per position, half at +100%,
    out at 60Δ / 90 DTE; start-every-January medians 3y | 5y, account CAGR): 15Δ beat 40Δ on every name: QQQ
    13.4 | 13.7 vs 8.5 | 6.9 (beat 5% in shares in 100% of windows); NVDA 14.3 | 11.2 vs 8.6 | 7.7; TSLA
    11.3 | 12.7 vs 6.2 | 6.4; BTC (modelled, no listed options before 2024) 26.6 | 26.8 vs 12.6 | 11.1. Worst
    windows −4% (NVDA 2012, a flat stretch), worst max DD −17 to −26%. Pricing the LEAPs at 1.2x the 30-day IV
    (`iv_scale`, term structure): QQQ 15Δ 9.7% vs 12.2%, MSTR 27.9% vs 30.9%, NVDA 11.7% (DD −29%): the ranking
    holds. Caveat: 2009–26 was a long bull market for all four; long calls bleed in flat years.
  - Start small, scale in by trade size (2026-10-11, `size_by_dd` [[drawdown % from the 1-year high, size
    multiplier]], `*_scalein`; same caps as the flat versions). QQQ puts + spike calls, 2007→: flat 10% puts
    14.8% / −38.7%; flat 3% 15.0% / −34.6%; 3% → 15% at −20% 14.8% / −37.8%; 2% → 20% at −30% 14.9% / −36.3%.
    Start-every-January medians 3y | 5y: flat 10% 6.6 | 7.8 beats every small-start version (3.7–5.2 | 5.1–6.3):
    small first puts deploy too slowly in rising markets. 6-ETF wheel 5.8 | 5.7 vs scale-in 5.1 | 5.1; tasty
    book 3.0 | 2.8 vs 2.7 | 2.6; MSTR 28.7% / −62.6% vs 28.2% / −60.9%. Trade size barely matters here because
    the caps (VIX-scaled total, per name) bind first and assignment, not size, decides what the wheel ends up
    owning. tastytrade's "start small" protects margin buying power, which expands in sell-offs; cash-secured
    collateral doesn't expand, so in an IRA the same job is done by the reserve and the caps. What does change
    results is total exposure by drawdown (`mode: target`: MSTR deeper schedule −67% → −42% max DD).
    tastylive's double-down study (SPY 16Δ strangles 2021–26) agrees: doubling after each loss ended the
    period about flat, and a loss after doubling was at least twice the first loss ~90% of the time.
  - Bitcoin's 2025 top, our monthly rule vs a KISS-style daily signal (2026-10-11): peak $125k on 2025-10-06;
    monthly 200-day rule exited 2025-12-01 at $86k, re-entered 2026-09-01 at $77k (low ~$60k in July 2026);
    daily 3-state went half on 2025-11-03 ($107k), out 2025-11-26 ($91k), half 2026-08-19 ($69k), full
    2026-09-03 ($81k), but flipped 4 times in Oct 2025. Daily sold ~14% higher this time; across start
    dates the monthly rule still wins (whipsaws). 42 Macro sold their bitcoin the same way (two steps on
    their trend signal, no calendar input). Keep monthly; show bitcoin's daily state on the dashboard as a
    readiness warning only.
  - Pyramiding by total exposure (Jordan 2026-10-11: scale into high-conviction assets as they fall, expecting new
    highs; `*_pyr*`, mode: target exec: stock, e.g. QQQ 80% at the high → 100% at −30%, BTC 70% → 100% at −70%,
    trimmed back as highs return; `trend_cap_pct: 0` = out below a falling 200-day). Equal 20% reserve on both
    sides, 2007→ (3y | 5y start-every-January medians): QQQ held 80% 12.9% / −45% (12.5 | 13.1) vs pyramid 14.0% /
    −51% (13.1 | 14.0); QQQ falling-200 exit + idle reserve 12.2% / −24% (11.3 | 11.8) vs pyramid in uptrends +
    exit 12.6% / −31% (12.7 | 12.9). Core 35/35/20/10 from 2015-10: idle reserve, no exits 24.5% / −25% (22.0 |
    23.4) vs pyramid 25.5% / −27% (21.7 | 25.8); combo exits + idle reserve 21.2% / −18% (20.6 | 21.4, 2022 −4%)
    vs pyramid in uptrends + exits 21.8% / −21% (20.2 | 22.1, 2022 −6%); fully invested held 30.2% / −31%.
    BTC: pyramid 58.5% / −78% vs 80% held 59.9% / −74% (medians 49.3 | 60.2 vs 46.9 | 56.6). So deploying a
    reserve into dips beats leaving it idle by ~0.5–1%/yr at ~3–6 pts more drawdown; it doesn't beat being
    fully invested or the trend exit's drawdown control. Same Sharpe band (1.30–1.38): a risk dial, not a free
    lunch. Different from pyramiding put size inside a capped wheel (no gain, see above).
  - Jordan's "Honeycomb v2" research (Perplexity, June 2026, after Porter Stansberry; 17 names,
    reported 17.0% CAGR / −18% max DD 2010–2026): names were picked partly on 2022 returns and
    2021–26 correlations (hindsight), TPL alone is +682 of +1,084 points, monthly data understates
    drawdowns, many names have thin options (TPL, VNOM, BWXT, RGLD). Fits the taxable buy-and-hold
    role better than the options wheel. Not yet backtested here on daily data.
  - Nithu Sezni (@nithusezni, "The Orange Pill Investor", the "Soliel" Jordan follows): posted
    rules = calls only after a rally with IVR > 50 and ~20% upside buffer, Friday rolls, LEAPs after
    dips at low IVR with > 90 DTE (OTM LEAPs closed ~90 days out, deep-ITM ones become PMCCs),
    funded partly with a personal loan; no public record before 2024, no verified returns; his
    full rules are in his pinned X "Options Comprehensive Mega Thread".
  Still to add: IVR 70. Real option history is paid.
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
  pmcc.py                  LEAP / poor man's covered call simulation (backtest `mode: pmcc`)
  target.py                target-allocation scaling by drawdown, via options or stock (`mode: target`)
  multi.py                 multi-asset core at fixed weights, rebalanced with options or stock (`mode: multi`)
  sleeve.py                long-call convexity sleeve: premium-sized calls/debit spreads with delta exits (`mode: sleeve`)
data/iv_history/{SYM}.csv  date,iv30 (vol points),price — appended once per market date (post-close only)
data/alert_state.json      alert dedup state (signals only, no account data), written by the workflow
data/earnings.json         earnings cache: next/last report date + timing, implied move (workflow-written)
docs/index.html            static phone-first dashboard (vanilla JS, light/dark) -> data/latest.json
docs/data/latest.json      written by the scan workflow (do not hand-edit)
docs/.nojekyll             serve docs/ as-is on GitHub Pages
docs/STRATEGY.md           living recommended build (sleeves, weights, do / don't); keep current
docs/HANDOFF.md            moving the work to the laptop (Cowork / Claude Code) + the research-brain prompt
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
- Lifecycle: 45 DTE, close at `management.take_profit_pct` (or the variant's `take_profit_pct`), at
  `decide_dte` close if OTM else hold to expiry and take assignment (`decide_itm`, global or per
  variant: `roll` rolls once, `close` buys it back), covered calls on assigned shares
  (spike mode: on up-spikes; always mode: continuously; momentum names 50%; strike ≥ net cost in
  Low/Mid), caps per name/bucket/total, circuit breakers. Fractional contracts, T-bill yield on cash.
- Modes: `spike` (rulebook), `always` (a put every `entry_every_days` while IVR ≥ `min_ivr`,
  tastytrade-style), `hold` (buy-and-hold at `weight`%, monthly rebalance).
- `qqq_scale*` / `basket_scale_vix` = Jordan's scale-in/scale-out plan (2026-10-11): always-on puts
  on the cash and calls on the shares, regime deltas doing the leaning. `vix_caps: true` takes the
  total cap from `deployment.vix_caps` (VIX bands; a list in the variant overrides it). Per-variant
  `dte` (number or {regime: dte}) and `decide_dte`. The report's scaling check shows the % of the
  account in shares by the first name's regime (should be high at Low, low at High).
- `mode: pmcc` (`vol_wheel/pmcc.py`, defaults in `backtest.pmcc`): one underlying, long leg = LEAP
  (85Δ, 12 months, closed at 120 DTE) or shares at `exposure_pct` notional, short calls `trend`
  (Tom King's dynamic PMCC: 10-DTE calls at 25/50/65Δ by EMA8 vs EMA21, rolled at 85% of the
  extrinsic captured), `spike` (rulebook) or `none`; optional entry filter (close > SMA200,
  RSI14 > 35, EMA8 > EMA21) and exits (+100%, +50% in half the time, −30% of the LEAP debit).
  Weekly calls are priced off the 30-day IV × `weekly_iv_ratio`.
- `roll_itm` ("roll until you're right"): at the 21-DTE decision an ITM option is rolled `dte` days out
  to the best strike that still nets a credit (puts down, calls up), up to `max_rolls`, calls only in
  `call_regimes`; no credit = held to expiry. Options opened at or inside `decide_dte` (short-DTE
  variants) skip the decision and run to expiry. A variant's `start` clips the window (MSTR from
  2020-09-01, its bitcoin-treasury era).
- `mode: target` (`vol_wheel/target.py`, defaults in `backtest.target`): Jordan's scaling plan
  (2026-10-12) as a rule: target share % = interpolation of `alloc` [[drawdown % from the high,
  share %]], reached by trading the stock (`exec: stock`) or with laddered slices (`exec: options`:
  puts on the shortfall, calls only on the excess, one slice per `every_days` plus one on a spike
  day, each struck off that day's price). Report adds shares held by drawdown bucket, positive
  months and worst 12 months.
- `mode: multi` (`vol_wheel/multi.py`): a few assets at fixed `weights` of `invested_pct` of the
  account, bought with stock on day one, then kept within `band_pct` either by trading stock
  (`exec: stock`) or with options (`exec: options`: puts on underweights, secured by spare cash only,
  calls on the overweight excess only; `stock_gap_pct` = hybrid, stock for big gaps). At 100%
  invested there is no cash to secure puts, so options rebalancing only buys after calls are
  exercised; `invested_pct: 80` (the SGOV reserve) is the realistic setting.
- `put_wing_delta` (wheel `always`/`spike` variants): sell a put credit spread instead of a cash-secured put
  (the IRA's defined-risk substitute for margin): long put at that delta, collateral = width, `entry_pct` =
  max loss per trade, in-the-money at expiry = cash-settled at the width it lost (no assignment, no rolls).
- `mode: blend` (`run_blend`): fixed `weights` of other variants' daily equity curves plus `tbills`,
  rebalanced monthly (`rebalance: M|Q|Y`) at no cost (separate sleeves of one account). Components run
  automatically, also under `--only`.
- `backtest.rolling` {years, first_year, benchmark, variants}: start-date robustness. Each listed variant is
  re-run from every January for each window length; the report's "Start-date robustness" table gives median
  / worst / best CAGR, worst max DD, % of windows beating the benchmark and the worst start. Slow (minutes);
  `--no-rolling` skips it.
- `mode: sleeve` (`vol_wheel/sleeve.py`, defaults in `backtest.sleeve`): premium-sized long calls (or a call
  debit spread via `short_delta`) on one name; entry filter `sma200` / `hhhl` (rising confirmed swings, no
  look-ahead) / `max_runup_pct`; exits `half_off_pct`, `exit_delta`, `short_exit_delta`, `exit_dte`,
  `stop_pct`; `call_skew` overrides the skew slope (scaled by √(skew_term_days/DTE) like the collars);
  strikes by bisection (stable under upside skew). Report lists payoff multiple and the best positions.
- Hold mode with `states` (`run_states`, KISS-style): fixed `weights` x each name's daily trend state
  (`trend_states`: 1 above a rising `sma`-day average, `neutral` (0.5) when only one holds, 0 below a falling
  one), traded at the next close (`lag_days`), re-traded on any state change and rebalanced monthly,
  `stock_cost_bps` per trade; `regime_vote` {symbols, halve, mult} scales the `halve` names when most vote
  symbols are at state 0. Report gives state-day shares and trades per year.
- Hold mode (`run_hold`) defensive knobs, checked at the monthly rebalance: `trend_sma` (below the
  N-day average → T-bills until back above), `trend_falling` (only while that average is falling;
  true = all names, a list = only those, the rest use the plain exit),
  `trend_arm` {symbols, high_within_days} (exit needs a High regime in the window), `trend_to`
  {symbols, lookback} (exited weight to the best-trending defensive name if it beats T-bills),
  `collar` {put_otm_pct, dte, roll_days, call, call_otm_pct, regimes, symbols} (puts financed by zero-cost
  calls, legs resized to the holding at each rebalance; longer-dated skew = slope × √(45/DTE),
  `skew_term_days`).
- Local runs: `--only name1,name2 --out <scratch dir>` runs a subset without touching docs/backtest.
- Known biases: today's universe applied to the past, no dividends, no earnings IV, BS prices.

## Conventions

- Python 3.11, deps: requests, pandas, numpy, pyyaml (+ optional yfinance). Keep it that way.
- Signal and scoring functions stay pure and take Series/DataFrames, so tests use synthetic data.
- Never commit account balances, positions, or broker credentials.
- `docs/data/latest.json` and `data/iv_history/*.csv` are written by the workflow; don't hand-edit.
