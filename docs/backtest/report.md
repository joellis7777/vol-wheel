# vol-wheel backtest

Generated 2026-10-09T21:06Z by `python -m vol_wheel.backtest` (workflow `backtest`). Account $500,000, cash yield _IRX. Single-stock IV is modelled as 1.15× max(HV20, HV60) unless a row says otherwise.

Deployed = average put collateral + shares as % of the account; In shares = the part held as assigned stock; Premium/yr = option credits (after costs) per year as % of average equity.

## 2007 → today (2007-01-03 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned | Premium/yr | In shares |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 14.5% | 17.8% | 0.76 | -32.8% | -30.3% | +10.6% | +30.8% | -30.9% | 80% | 1.2 | 5 | 0.9% | 79.0% |
| QQQ only · spikes · fixed 20Δ | 13.8% | 16.2% | 0.78 | -30.5% | -27.6% | +13.1% | +29.5% | -28.2% | 73% | 1.5 | 4 | 1.1% | 72.3% |
| QQQ only · spike puts, calls always on shares | 2.0% | 6.1% | 0.10 | -28.0% | -19.1% | -2.3% | +4.1% | +2.7% | 7% | 4.9 | 7 | 1.6% | 3.9% |
| QQQ only · always on | 3.2% | 8.9% | 0.22 | -36.0% | -24.8% | -5.7% | +3.5% | -11.0% | 28% | 46.9 | 24 | 5.7% | 9.6% |
| QQQ only · always on, IVR ≥ 30 | 2.6% | 8.1% | 0.17 | -35.4% | -24.4% | -6.9% | +2.5% | -4.7% | 17% | 23.1 | 19 | 4.0% | 8.4% |
| QQQ + SPY · spikes | 12.7% | 17.3% | 0.69 | -34.5% | -26.4% | +2.5% | +24.3% | -27.0% | 83% | 2.1 | 6 | 0.9% | 81.2% |
| Basket · spikes (current rules) (stock IV 1x HV) | 14.6% | 16.1% | 0.83 | -33.0% | -30.3% | +27.3% | +42.8% | -31.5% | 62% | 32.4 | 36 | 7.7% | 54.7% |
| Basket · spikes (current rules) | 15.6% | 16.5% | 0.87 | -34.6% | -31.7% | +35.6% | +45.8% | -33.0% | 62% | 32.1 | 33 | 9.1% | 55.1% |
| Basket · spikes (current rules) (stock IV 1.3x HV) | 16.9% | 16.7% | 0.93 | -29.5% | -26.5% | +38.8% | +37.4% | -27.4% | 65% | 26.1 | 29 | 9.4% | 58.8% |
| Index core 50% + satellites · spikes (stock IV 1x HV) | 15.5% | 17.0% | 0.84 | -37.6% | -25.6% | +16.3% | +33.2% | -26.5% | 72% | 23.5 | 26 | 5.5% | 66.6% |
| Index core 50% + satellites · spikes | 15.8% | 16.8% | 0.86 | -34.8% | -26.4% | +19.2% | +33.6% | -27.3% | 72% | 25.4 | 24 | 6.3% | 65.5% |
| Index core 50% + satellites · spikes (stock IV 1.3x HV) | 18.3% | 18.6% | 0.92 | -34.7% | -26.5% | +22.9% | +30.8% | -27.4% | 73% | 18.8 | 20 | 5.8% | 68.4% |
| Basket · always on (stock IV 1x HV) | 10.7% | 14.3% | 0.67 | -41.6% | -30.8% | -0.3% | +48.2% | -26.2% | 75% | 210.6 | 138 | 24.3% | 34.9% |
| Basket · always on | 13.0% | 14.0% | 0.84 | -39.9% | -29.2% | +2.6% | +43.8% | -24.7% | 76% | 213.4 | 119 | 28.9% | 33.7% |
| Basket · always on (stock IV 1.3x HV) | 15.3% | 13.9% | 0.98 | -40.0% | -29.9% | +3.2% | +38.2% | -21.2% | 76% | 212.8 | 110 | 35.1% | 34.2% |
| Buy & hold QQQ 100% | 15.4% | 22.2% | 0.69 | -53.6% | -41.9% | -12.0% | +32.4% | -33.7% | 100% | – | – | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 12.9% | 17.6% | 0.69 | -45.0% | -34.4% | -7.7% | +26.2% | -27.3% | 80% | – | – | – | – |
| Buy & hold basket 80% (equal weight) | 20.3% | 20.3% | 0.94 | -51.1% | -38.1% | +12.8% | +53.1% | -35.8% | 80% | – | – | – | – |

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +1,189k, QQQ +3,547k
- **Basket · spikes (current rules)** P&L by name (excl. interest): IBIT -41k, HOOD +2k, GLD +43k, SOFI +50k, CEG +122k, FNV +180k, SPY +290k, AMZN +447k, GOOG +448k, MRVL +728k, TSLA +782k, QQQ +1,252k, MSTR +1,297k, NVDA +2,197k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): IBIT -51k, HOOD +19k, GLD +37k, SOFI +46k, FNV +49k, CEG +99k, MRVL +105k, GOOG +293k, MSTR +309k, TSLA +329k, AMZN +458k, SPY +711k, QQQ +1,986k, NVDA +3,783k
- **Basket · always on** P&L by name (excl. interest): IBIT +55k, GLD +69k, FNV +115k, SOFI +141k, HOOD +145k, SPY +193k, QQQ +210k, GOOG +264k, CEG +295k, AMZN +300k, MRVL +452k, MSTR +758k, TSLA +792k, NVDA +812k

## 2021 → today (whole basket live) (2021-01-04 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned | Premium/yr | In shares |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 7.0% | 3.8% | 0.94 | -4.5% | 0.2% | – | – | +2.7% | 17% | 4.5 | 1 | 1.4% | 14.0% |
| QQQ only · spikes · fixed 20Δ | 3.9% | 0.7% | 0.82 | -1.1% | 0.2% | – | – | +3.2% | 2% | 4.5 | 0 | 1.1% | 0.0% |
| QQQ only · spike puts, calls always on shares | 4.0% | 1.5% | 0.47 | -1.8% | 0.2% | – | – | +2.7% | 4% | 4.5 | 1 | 1.4% | 0.9% |
| QQQ only · always on | 5.6% | 8.1% | 0.31 | -13.3% | -9.8% | – | – | -9.9% | 32% | 46.1 | 10 | 6.1% | 12.6% |
| QQQ only · always on, IVR ≥ 30 | 5.3% | 6.4% | 0.33 | -10.3% | -4.7% | – | – | -4.7% | 21% | 23.8 | 7 | 4.5% | 10.9% |
| QQQ + SPY · spikes | 7.4% | 4.1% | 0.96 | -5.1% | 0.3% | – | – | +4.4% | 18% | 7.7 | 1 | 2.1% | 13.9% |
| Basket · spikes (current rules) (stock IV 1x HV) | 19.7% | 15.4% | 1.03 | -15.3% | -6.5% | – | – | -6.5% | 47% | 52.2 | 17 | 10.7% | 35.4% |
| Basket · spikes (current rules) | 21.0% | 15.3% | 1.11 | -13.8% | -4.9% | – | – | -4.9% | 47% | 52.7 | 16 | 12.8% | 35.1% |
| Basket · spikes (current rules) (stock IV 1.3x HV) | 24.4% | 17.7% | 1.14 | -18.9% | -3.4% | – | – | -3.4% | 52% | 47.5 | 13 | 13.8% | 40.0% |
| Index core 50% + satellites · spikes (stock IV 1x HV) | 21.2% | 16.0% | 1.08 | -15.6% | -6.5% | – | – | -6.5% | 52% | 46.4 | 16 | 10.6% | 39.7% |
| Index core 50% + satellites · spikes | 22.5% | 15.9% | 1.15 | -15.3% | -5.2% | – | – | -5.2% | 52% | 45.6 | 15 | 12.1% | 39.6% |
| Index core 50% + satellites · spikes (stock IV 1.3x HV) | 25.1% | 17.3% | 1.20 | -18.9% | -0.8% | – | – | -0.9% | 54% | 43.3 | 11 | 12.8% | 42.1% |
| Basket · always on (stock IV 1x HV) | 16.4% | 16.9% | 0.79 | -25.7% | -22.8% | – | – | -23.2% | 78% | 217.6 | 45 | 28.7% | 35.4% |
| Basket · always on | 20.5% | 16.6% | 1.01 | -24.6% | -21.4% | – | – | -21.9% | 78% | 226.6 | 39 | 34.9% | 33.0% |
| Basket · always on (stock IV 1.3x HV) | 27.1% | 17.7% | 1.26 | -22.2% | -17.0% | – | – | -17.6% | 78% | 217.2 | 35 | 39.0% | 34.0% |
| Buy & hold QQQ 100% | 16.6% | 22.4% | 0.65 | -35.6% | -33.1% | – | – | -33.7% | 100% | – | – | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 14.1% | 17.8% | 0.65 | -29.0% | -26.7% | – | – | -27.3% | 80% | – | – | – | – |
| Buy & hold basket 80% (equal weight) | 26.1% | 24.6% | 0.93 | -38.6% | -34.7% | – | – | -35.8% | 80% | – | – | – | – |

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +17k, QQQ +143k
- **Basket · spikes (current rules)** P&L by name (excl. interest): IBIT -4k, GLD +2k, MRVL +2k, SPY +6k, HOOD +15k, SOFI +24k, CEG +28k, FNV +34k, GOOG +48k, TSLA +49k, QQQ +52k, AMZN +58k, MSTR +104k, NVDA +486k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): IBIT -6k, MRVL +2k, GLD +2k, HOOD +10k, SPY +11k, SOFI +25k, CEG +26k, FNV +33k, TSLA +44k, GOOG +48k, AMZN +57k, QQQ +137k, MSTR +145k, NVDA +488k
- **Basket · always on** P&L by name (excl. interest): GLD +4k, IBIT +4k, SPY +22k, FNV +23k, SOFI +25k, GOOG +31k, QQQ +32k, HOOD +42k, AMZN +60k, TSLA +63k, MRVL +74k, CEG +91k, NVDA +129k, MSTR +243k

## Data

- AMZN: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- CEG: cboe 2022-02-02 → 2026-10-08 (1176 bars); history before 2022-02-02 dropped (3614-day gap: earlier listing)
- FNV: cboe 2011-09-08 → 2026-10-08 (3795 bars)
- GLD: cboe 2006-01-03 → 2026-10-08 (5226 bars); bars before 2006-01-03 dropped
- GOOG: cboe 2006-01-03 → 2026-10-08 (5224 bars)
- HOOD: cboe 2021-07-29 → 2026-10-08 (1306 bars)
- IBIT: cboe 2024-01-11 → 2026-10-08 (689 bars); bars before 2024-01-11 dropped
- MRVL: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped; 2006-07-25 x2 jump adjusted
- MSTR: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- NVDA: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped; 2006-04-07 x2 jump adjusted
- QQQ: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- SOFI: cboe 2020-11-30 → 2026-10-08 (1472 bars)
- SPY: cboe 2006-01-03 → 2026-10-08 (5226 bars); bars before 2006-01-03 dropped
- TSLA: cboe 2010-06-29 → 2026-10-08 (4096 bars)
- _GVZ: yahoo+cboe 2008-06-03 → 2026-10-08 (4615 bars)
- _VIX: cboe 1990-01-02 → 2026-10-08 (9290 bars)
- _VXN: yahoo+cboe 2001-01-23 → 2026-10-08 (6468 bars)

## Caveats

- Option prices are Black-Scholes, not market quotes. Index names use VXN/VIX/GVZ × 0.9 as ATM IV with a fixed skew; single stocks use an assumed IV/HV multiple, so their premium (and the basket's edge) is a modelling choice: read the sensitivity rows.
- The basket is today's universe applied to the past (hindsight and survivorship bias in its favour).
- Prices exclude dividends (buy-and-hold is understated by ~0.6%/yr for QQQ, ~1.5% for SPY).
- Earnings IV, early assignment, rolling for credit beyond `max_rolls`, and integer contract sizes are not modelled.
- Trades fill at the signal day's close; the live scanner alerts intraday on delayed quotes.
