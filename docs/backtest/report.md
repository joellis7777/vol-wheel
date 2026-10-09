# vol-wheel backtest

Generated 2026-10-09T21:00Z by `python -m vol_wheel.backtest` (workflow `backtest`). Account $500,000, cash yield _IRX. Single-stock IV is modelled as 1.15× max(HV20, HV60) unless a row says otherwise.

## 2006 → today (2006-01-03 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 12.3% | 14.1% | 0.77 | -29.6% | -27.2% | +15.9% | +26.7% | -27.8% | 64% | 3.6 | 4 |
| QQQ only · spikes · fixed 20Δ | 10.8% | 13.1% | 0.72 | -28.9% | -26.1% | +9.1% | +28.9% | -26.7% | 55% | 4.2 | 3 |
| QQQ only · always on | 4.2% | 7.8% | 0.35 | -28.4% | -15.5% | +4.0% | +3.5% | -10.3% | 31% | 48.0 | 29 |
| QQQ only · always on, IVR ≥ 30 | 3.5% | 6.7% | 0.29 | -26.9% | -14.7% | +3.0% | +2.5% | -4.7% | 19% | 25.3 | 20 |
| QQQ + SPY · spikes | 13.0% | 16.7% | 0.71 | -29.9% | -26.6% | +10.3% | +24.6% | -27.2% | 80% | 2.8 | 7 |
| Basket · spikes (current rules) (stock IV 1x HV) | 15.6% | 16.2% | 0.87 | -36.7% | -28.6% | +19.9% | +40.2% | -29.9% | 64% | 35.4 | 45 |
| Basket · spikes (current rules) | 16.7% | 16.6% | 0.91 | -43.1% | -31.4% | +19.5% | +39.8% | -25.4% | 60% | 36.2 | 34 |
| Basket · spikes (current rules) (stock IV 1.3x HV) | 16.8% | 17.0% | 0.90 | -40.1% | -28.0% | +24.0% | +36.0% | -25.9% | 64% | 32.1 | 32 |
| Index core 50% + satellites · spikes (stock IV 1x HV) | 16.7% | 17.1% | 0.89 | -41.5% | -29.9% | +13.9% | +37.6% | -28.2% | 71% | 30.1 | 37 |
| Index core 50% + satellites · spikes | 16.8% | 17.6% | 0.88 | -44.8% | -33.5% | +13.8% | +36.9% | -30.4% | 66% | 26.3 | 27 |
| Index core 50% + satellites · spikes (stock IV 1.3x HV) | 17.6% | 18.3% | 0.89 | -41.5% | -29.3% | +18.8% | +35.0% | -26.7% | 70% | 21.0 | 22 |
| Basket · always on (stock IV 1x HV) | 11.1% | 13.8% | 0.71 | -44.0% | -33.4% | -5.9% | +47.5% | -25.6% | 77% | 207.3 | 137 |
| Basket · always on | 12.8% | 13.7% | 0.83 | -43.3% | -33.0% | -0.0% | +36.2% | -23.1% | 77% | 207.5 | 124 |
| Basket · always on (stock IV 1.3x HV) | 14.9% | 14.0% | 0.94 | -47.0% | -38.5% | -5.7% | +40.6% | -18.7% | 78% | 200.3 | 102 |
| Buy & hold QQQ 100% | 15.0% | nan% | nan | -100.0% | -41.9% | -12.0% | +32.4% | -33.7% | 100% | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 12.6% | 84.8% | 0.30 | -81.2% | -34.4% | -7.7% | +26.2% | -27.3% | 80% | – | – |
| Buy & hold basket 80% (equal weight) | 19.3% | 33.9% | 0.62 | -58.8% | -40.4% | +6.8% | +53.1% | -29.8% | 80% | – | – |

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +1,330k, QQQ +4,388k
- **Basket · spikes (current rules)** P&L by name (excl. interest): IBIT +10k, GLD +55k, HOOD +60k, SOFI +138k, CEG +226k, FNV +265k, SPY +402k, TSLA +592k, GOOG +621k, MRVL +1,013k, AMZN +1,248k, QQQ +1,578k, MSTR +1,674k, NVDA +3,288k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): IBIT -28k, HOOD -1k, GLD +35k, SOFI +74k, FNV +79k, CEG +163k, TSLA +552k, GOOG +671k, MRVL +1,040k, MSTR +1,113k, SPY +1,217k, AMZN +1,289k, QQQ +1,793k, NVDA +3,545k
- **Basket · always on** P&L by name (excl. interest): GLD +69k, SOFI +142k, IBIT +144k, FNV +145k, SPY +184k, HOOD +229k, GOOG +240k, QQQ +265k, AMZN +346k, CEG +456k, MRVL +492k, NVDA +608k, MSTR +809k, TSLA +836k

## 2021 → today (whole basket live) (2021-01-04 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned |
|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 7.0% | 3.8% | 0.94 | -4.5% | 0.2% | – | – | +2.7% | 17% | 4.5 | 1 |
| QQQ only · spikes · fixed 20Δ | 3.9% | 0.7% | 0.82 | -1.1% | 0.2% | – | – | +3.2% | 2% | 4.5 | 0 |
| QQQ only · always on | 5.6% | 8.1% | 0.31 | -13.3% | -9.8% | – | – | -9.9% | 32% | 46.1 | 10 |
| QQQ only · always on, IVR ≥ 30 | 5.3% | 6.4% | 0.33 | -10.3% | -4.7% | – | – | -4.7% | 21% | 23.8 | 7 |
| QQQ + SPY · spikes | 7.4% | 4.1% | 0.96 | -5.1% | 0.3% | – | – | +4.4% | 18% | 7.7 | 1 |
| Basket · spikes (current rules) (stock IV 1x HV) | 19.9% | 15.4% | 1.04 | -15.2% | -6.1% | – | – | -6.1% | 48% | 55.0 | 17 |
| Basket · spikes (current rules) | 21.2% | 15.3% | 1.12 | -13.7% | -4.4% | – | – | -4.4% | 48% | 55.1 | 15 |
| Basket · spikes (current rules) (stock IV 1.3x HV) | 24.8% | 17.6% | 1.17 | -18.8% | -2.8% | – | – | -2.8% | 52% | 50.4 | 13 |
| Index core 50% + satellites · spikes (stock IV 1x HV) | 20.6% | 14.4% | 1.14 | -14.4% | -0.0% | – | – | -0.0% | 49% | 51.1 | 15 |
| Index core 50% + satellites · spikes | 21.8% | 14.2% | 1.24 | -12.7% | 1.3% | – | – | +1.3% | 49% | 51.3 | 13 |
| Index core 50% + satellites · spikes (stock IV 1.3x HV) | 25.8% | 17.9% | 1.19 | -20.0% | -2.3% | – | – | -2.3% | 56% | 43.7 | 12 |
| Basket · always on (stock IV 1x HV) | 16.4% | 16.9% | 0.79 | -25.5% | -22.5% | – | – | -22.9% | 77% | 232.0 | 40 |
| Basket · always on | 19.6% | 16.9% | 0.95 | -27.1% | -23.9% | – | – | -24.4% | 78% | 231.7 | 38 |
| Basket · always on (stock IV 1.3x HV) | 24.1% | 15.5% | 1.26 | -22.8% | -17.7% | – | – | -18.3% | 78% | 249.9 | 35 |
| Buy & hold QQQ 100% | 16.6% | 22.4% | 0.65 | -35.6% | -33.1% | – | – | -33.7% | 100% | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 14.1% | 17.8% | 0.65 | -29.0% | -26.7% | – | – | -27.3% | 80% | – | – |
| Buy & hold basket 80% (equal weight) | 27.4% | 24.4% | 0.98 | -33.8% | -29.8% | – | – | -31.0% | 80% | – | – |

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +17k, QQQ +143k
- **Basket · spikes (current rules)** P&L by name (excl. interest): GLD +2k, MRVL +2k, IBIT +5k, SPY +6k, HOOD +15k, SOFI +24k, CEG +29k, FNV +34k, GOOG +48k, TSLA +49k, QQQ +52k, AMZN +58k, MSTR +104k, NVDA +487k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): MRVL +2k, GLD +2k, IBIT +5k, HOOD +13k, SPY +13k, TSLA +18k, CEG +27k, SOFI +28k, FNV +34k, GOOG +48k, AMZN +57k, MSTR +91k, QQQ +137k, NVDA +488k
- **Basket · always on** P&L by name (excl. interest): SOFI +9k, GLD +10k, IBIT +21k, FNV +24k, SPY +24k, QQQ +28k, GOOG +30k, HOOD +30k, AMZN +51k, MRVL +71k, TSLA +78k, CEG +84k, NVDA +107k, MSTR +219k

## Data

- AMZN: cboe 2004-01-02 → 2026-10-08 (5729 bars)
- CEG: cboe 2006-01-03 → 2026-10-08 (2735 bars)
- FNV: cboe 2011-09-08 → 2026-10-08 (3795 bars)
- GLD: cboe 2004-11-18 → 2026-10-08 (5508 bars)
- GOOG: cboe 2006-01-03 → 2026-10-08 (5224 bars)
- HOOD: cboe 2021-07-29 → 2026-10-08 (1306 bars)
- IBIT: cboe 2022-09-08 → 2026-10-08 (1026 bars)
- MRVL: cboe 2004-01-02 → 2026-10-08 (5729 bars); 2006-07-25 1:2 reverse split adjusted
- MSTR: cboe 2004-01-02 → 2026-10-08 (5729 bars)
- NVDA: cboe 2004-01-02 → 2026-10-08 (5729 bars); 2006-04-07 1:2 reverse split adjusted
- QQQ: cboe 2004-01-02 → 2026-10-08 (5729 bars)
- SOFI: cboe 2020-11-30 → 2026-10-08 (1472 bars)
- SPY: cboe 2004-01-02 → 2026-10-08 (5730 bars)
- TSLA: cboe 2010-06-29 → 2026-10-08 (4096 bars)
- _GVZ: cboe 2009-09-18 → 2026-10-08 (4288 bars)
- _VIX: cboe 1990-01-02 → 2026-10-08 (9290 bars)
- _VXN: cboe 2009-09-14 → 2026-10-08 (4296 bars)

## Caveats

- Option prices are Black-Scholes, not market quotes. Index names use VXN/VIX/GVZ × 0.9 as ATM IV with a fixed skew; single stocks use an assumed IV/HV multiple, so their premium (and the basket's edge) is a modelling choice: read the sensitivity rows.
- The basket is today's universe applied to the past (hindsight and survivorship bias in its favour).
- Prices exclude dividends (buy-and-hold is understated by ~0.6%/yr for QQQ, ~1.5% for SPY).
- Earnings IV, early assignment, rolling for credit beyond `max_rolls`, and integer contract sizes are not modelled.
- Trades fill at the signal day's close; the live scanner alerts intraday on delayed quotes.
