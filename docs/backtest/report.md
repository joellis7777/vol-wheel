# vol-wheel backtest

Generated 2026-10-09T21:03Z by `python -m vol_wheel.backtest` (workflow `backtest`). Account $500,000, cash yield _IRX. Single-stock IV is modelled as 1.15× max(HV20, HV60) unless a row says otherwise.

## 2006 → today (2006-01-03 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 14.2% | 17.6% | 0.75 | -32.9% | -30.4% | +8.4% | +31.0% | -31.0% | 79% | 1.4 | 5 |
| QQQ only · spikes · fixed 20Δ | 13.3% | 15.8% | 0.76 | -30.5% | -27.6% | +13.1% | +29.5% | -28.2% | 70% | 1.7 | 4 |
| QQQ only · always on | 3.8% | 8.5% | 0.28 | -33.4% | -21.6% | -3.8% | +3.5% | -10.3% | 30% | 47.8 | 29 |
| QQQ only · always on, IVR ≥ 30 | 3.2% | 7.7% | 0.23 | -32.8% | -21.3% | -4.0% | +2.5% | -4.7% | 19% | 24.3 | 22 |
| QQQ + SPY · spikes | 12.4% | 16.9% | 0.68 | -35.3% | -26.4% | +0.1% | +24.2% | -27.0% | 80% | 2.5 | 6 |
| Basket · spikes (current rules) (stock IV 1x HV) | 15.7% | 16.1% | 0.88 | -33.0% | -30.3% | +30.8% | +44.1% | -31.6% | 62% | 33.6 | 42 |
| Basket · spikes (current rules) | 17.3% | 17.2% | 0.92 | -42.0% | -27.9% | +34.5% | +39.0% | -27.3% | 62% | 31.9 | 32 |
| Basket · spikes (current rules) (stock IV 1.3x HV) | 16.9% | 17.0% | 0.91 | -37.6% | -26.2% | +28.4% | +37.4% | -27.1% | 62% | 30.2 | 29 |
| Index core 50% + satellites · spikes (stock IV 1x HV) | 17.6% | 17.8% | 0.90 | -40.5% | -30.7% | +18.7% | +38.6% | -31.9% | 71% | 27.1 | 33 |
| Index core 50% + satellites · spikes | 17.1% | 18.0% | 0.88 | -43.4% | -30.9% | +22.0% | +37.9% | -29.6% | 68% | 23.0 | 24 |
| Index core 50% + satellites · spikes (stock IV 1.3x HV) | 18.9% | 19.1% | 0.91 | -41.9% | -30.0% | +16.2% | +35.0% | -28.2% | 70% | 20.3 | 23 |
| Basket · always on (stock IV 1x HV) | 11.0% | 14.5% | 0.68 | -42.1% | -30.2% | -1.6% | +45.0% | -26.9% | 76% | 200.7 | 145 |
| Basket · always on | 13.5% | 14.1% | 0.85 | -42.3% | -31.1% | +3.5% | +37.3% | -21.7% | 76% | 208.1 | 124 |
| Basket · always on (stock IV 1.3x HV) | 15.4% | 14.1% | 0.97 | -44.2% | -35.0% | -2.4% | +38.3% | -19.4% | 76% | 206.4 | 109 |
| Buy & hold QQQ 100% | 15.0% | nan% | nan | -100.0% | -41.9% | -12.0% | +32.4% | -33.7% | 100% | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 12.6% | 84.8% | 0.30 | -81.2% | -34.4% | -7.7% | +26.2% | -27.3% | 80% | – | – |
| Buy & hold basket 80% (equal weight) | 19.8% | 34.1% | 0.63 | -58.8% | -38.1% | +12.8% | +53.1% | -35.8% | 80% | – | – |

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +1,268k, QQQ +3,795k
- **Basket · spikes (current rules)** P&L by name (excl. interest): IBIT +9k, HOOD +54k, GLD +55k, SOFI +152k, CEG +198k, FNV +291k, SPY +392k, TSLA +658k, GOOG +696k, MRVL +1,193k, AMZN +1,309k, MSTR +1,861k, QQQ +1,952k, NVDA +3,684k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): IBIT -34k, HOOD -17k, GLD +19k, SOFI +47k, CEG +137k, FNV +155k, MSTR +426k, TSLA +603k, GOOG +717k, SPY +1,014k, MRVL +1,196k, AMZN +1,346k, QQQ +2,750k, NVDA +3,878k
- **Basket · always on** P&L by name (excl. interest): GLD +79k, IBIT +85k, SOFI +111k, FNV +147k, SPY +186k, HOOD +204k, QQQ +265k, GOOG +294k, AMZN +373k, CEG +408k, NVDA +632k, MRVL +696k, TSLA +814k, MSTR +1,502k

## 2021 → today (whole basket live) (2021-01-04 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 7.0% | 3.8% | 0.94 | -4.5% | 0.2% | – | – | +2.7% | 17% | 4.5 | 1 |
| QQQ only · spikes · fixed 20Δ | 3.9% | 0.7% | 0.82 | -1.1% | 0.2% | – | – | +3.2% | 2% | 4.5 | 0 |
| QQQ only · always on | 5.6% | 8.1% | 0.31 | -13.3% | -9.8% | – | – | -9.9% | 32% | 46.1 | 10 |
| QQQ only · always on, IVR ≥ 30 | 5.3% | 6.4% | 0.33 | -10.3% | -4.7% | – | – | -4.7% | 21% | 23.8 | 7 |
| QQQ + SPY · spikes | 7.4% | 4.1% | 0.96 | -5.1% | 0.3% | – | – | +4.4% | 18% | 7.7 | 1 |
| Basket · spikes (current rules) (stock IV 1x HV) | 19.8% | 15.4% | 1.04 | -15.2% | -6.5% | – | – | -6.5% | 47% | 53.7 | 17 |
| Basket · spikes (current rules) | 21.1% | 15.3% | 1.12 | -13.7% | -4.9% | – | – | -4.9% | 48% | 53.9 | 15 |
| Basket · spikes (current rules) (stock IV 1.3x HV) | 24.7% | 17.6% | 1.16 | -18.8% | -3.4% | – | – | -3.4% | 52% | 49.2 | 13 |
| Index core 50% + satellites · spikes (stock IV 1x HV) | 21.4% | 15.9% | 1.09 | -15.5% | -6.5% | – | – | -6.5% | 52% | 47.8 | 16 |
| Index core 50% + satellites · spikes | 22.6% | 15.8% | 1.16 | -15.2% | -5.2% | – | – | -5.2% | 52% | 46.6 | 15 |
| Index core 50% + satellites · spikes (stock IV 1.3x HV) | 25.9% | 17.3% | 1.23 | -18.7% | -0.8% | – | – | -0.9% | 54% | 44.7 | 12 |
| Basket · always on (stock IV 1x HV) | 17.1% | 16.9% | 0.82 | -25.7% | -22.8% | – | – | -23.2% | 78% | 220.2 | 43 |
| Basket · always on | 20.7% | 16.5% | 1.03 | -24.6% | -21.4% | – | – | -21.9% | 78% | 235.1 | 36 |
| Basket · always on (stock IV 1.3x HV) | 26.2% | 18.0% | 1.20 | -22.2% | -17.0% | – | – | -17.6% | 78% | 217.6 | 38 |
| Buy & hold QQQ 100% | 16.6% | 22.4% | 0.65 | -35.6% | -33.1% | – | – | -33.7% | 100% | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 14.1% | 17.8% | 0.65 | -29.0% | -26.7% | – | – | -27.3% | 80% | – | – |
| Buy & hold basket 80% (equal weight) | 26.2% | 24.7% | 0.94 | -38.6% | -34.7% | – | – | -35.8% | 80% | – | – |

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +17k, QQQ +143k
- **Basket · spikes (current rules)** P&L by name (excl. interest): GLD +2k, MRVL +2k, IBIT +5k, SPY +6k, HOOD +15k, SOFI +24k, CEG +28k, FNV +34k, GOOG +48k, TSLA +49k, QQQ +52k, AMZN +58k, MSTR +104k, NVDA +486k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): MRVL +2k, GLD +2k, IBIT +3k, HOOD +10k, SPY +11k, SOFI +25k, CEG +25k, FNV +33k, TSLA +45k, GOOG +48k, AMZN +57k, QQQ +137k, MSTR +144k, NVDA +488k
- **Basket · always on** P&L by name (excl. interest): GLD +4k, FNV +24k, SPY +24k, IBIT +25k, SOFI +35k, QQQ +35k, GOOG +38k, HOOD +39k, AMZN +46k, TSLA +61k, CEG +69k, MRVL +73k, NVDA +131k, MSTR +248k

## Data

- AMZN: cboe 2004-01-02 → 2026-10-08 (5729 bars)
- CEG: cboe 2022-02-02 → 2026-10-08 (1176 bars); history before 2022-02-02 dropped (3614-day gap: earlier listing)
- FNV: cboe 2011-09-08 → 2026-10-08 (3795 bars)
- GLD: cboe 2004-11-18 → 2026-10-08 (5508 bars)
- GOOG: cboe 2006-01-03 → 2026-10-08 (5224 bars)
- HOOD: cboe 2021-07-29 → 2026-10-08 (1306 bars)
- IBIT: cboe 2022-09-08 → 2026-10-08 (1026 bars)
- MRVL: cboe 2004-01-02 → 2026-10-08 (5729 bars); 2006-07-25 x2 jump adjusted
- MSTR: cboe 2004-01-02 → 2026-10-08 (5729 bars)
- NVDA: cboe 2004-01-02 → 2026-10-08 (5729 bars); 2006-04-07 x2 jump adjusted
- QQQ: cboe 2004-01-02 → 2026-10-08 (5729 bars)
- SOFI: cboe 2020-11-30 → 2026-10-08 (1472 bars)
- SPY: cboe 2004-01-02 → 2026-10-08 (5730 bars)
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
