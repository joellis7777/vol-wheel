# vol-wheel backtest

Generated 2026-10-11T02:49Z by `python -m vol_wheel.backtest` (workflow `backtest`). Account $500,000, cash yield _IRX. Single-stock IV is modelled as 1.15× max(HV20, HV60) unless a row says otherwise.

Deployed = average put collateral + shares as % of the account; In shares = the part held as assigned stock; Premium/yr = option credits (after costs) per year as % of average equity.

## 2007 → today (2007-01-03 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned | Premium/yr | In shares |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 14.5% | 17.8% | 0.76 | -32.8% | -30.3% | +10.6% | +30.8% | -30.9% | 80% | 1.2 | 5 | 0.9% | 79.0% |
| QQQ only · spike puts, calls always on shares | 2.0% | 6.1% | 0.10 | -28.0% | -19.1% | -2.3% | +4.1% | +2.7% | 7% | 4.9 | 7 | 1.6% | 3.9% |
| QQQ scale in/out · cap 80% | 5.3% | 11.0% | 0.39 | -38.9% | -28.1% | -8.7% | +8.5% | -17.1% | 54% | 101.8 | 38 | 10.8% | 13.9% |
| QQQ scale in/out · VIX-scaled cap | 5.0% | 10.4% | 0.38 | -37.9% | -27.1% | -7.6% | +9.7% | -13.5% | 47% | 88.0 | 38 | 9.5% | 13.3% |
| QQQ scale in/out · VIX cap to 100% | 5.4% | 12.3% | 0.36 | -42.9% | -30.6% | -8.0% | +10.1% | -16.6% | 53% | 95.1 | 43 | 10.5% | 15.5% |
| QQQ scale in/out · VIX cap · 40Δ puts at lows | 5.2% | 10.6% | 0.39 | -36.1% | -26.1% | -6.0% | +10.1% | -15.1% | 48% | 85.7 | 49 | 9.7% | 13.6% |
| QQQ scale in/out · VIX cap · puts only at IVR ≥ 30 | 3.5% | 9.6% | 0.25 | -37.9% | -27.1% | -8.7% | +6.0% | -9.4% | 26% | 40.4 | 24 | 6.0% | 10.9% |
| QQQ puts always on · calls only on up-spikes | 14.8% | 18.9% | 0.75 | -38.7% | -30.8% | +5.7% | +31.5% | -31.4% | 87% | 6.4 | 9 | 1.1% | 84.0% |
| QQQ scale in/out · calls on half the shares | 6.5% | 10.9% | 0.50 | -38.3% | -26.8% | -1.9% | +15.6% | -14.5% | 51% | 76.9 | 38 | 8.6% | 21.7% |
| QQQ scale in/out · calls only in High regime | 8.1% | 12.0% | 0.58 | -38.7% | -26.5% | -6.8% | +14.7% | -14.2% | 55% | 60.8 | 34 | 6.5% | 31.3% |
| QQQ PMCC · Tom King rules | 1.4% | 9.7% | 0.04 | -27.4% | -15.2% | -5.8% | +8.6% | -11.9% | 94% | – | – | 47.7% | – |
| QQQ PMCC · Tom King rules · weekly IV 0.9x | -2.4% | 9.6% | -0.36 | -53.0% | -23.1% | -13.6% | +7.8% | -23.8% | 95% | – | – | 45.7% | – |
| QQQ PMCC · trend calls, no filter/exits | 0.1% | 10.8% | -0.08 | -35.7% | -31.6% | -9.2% | +9.3% | -32.2% | 105% | – | – | 58.4% | – |
| QQQ LEAP · Tom's filter + exits, no calls | 7.7% | 14.9% | 0.47 | -33.2% | -23.7% | -7.4% | +22.4% | -24.5% | 88% | – | – | 0.0% | – |
| QQQ LEAP held (rolled at 120 DTE), no calls | 8.4% | 18.7% | 0.44 | -55.4% | -42.6% | -23.0% | +25.0% | -38.3% | 102% | – | – | 0.0% | – |
| QQQ LEAP held · calls only on up-spikes | 8.3% | 18.3% | 0.44 | -53.8% | -41.5% | -21.8% | +26.8% | -37.1% | 102% | – | – | 1.5% | – |
| QQQ shares · Tom's trend calls | 10.2% | 23.2% | 0.47 | -55.0% | -45.1% | +1.2% | +36.3% | -46.0% | 162% | – | – | 105.7% | – |
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
| Basket scale in/out · VIX-scaled cap (stock IV 1x HV) | 8.1% | 13.2% | 0.54 | -43.4% | -32.5% | -7.3% | +31.5% | -26.5% | 58% | 148.6 | 112 | 18.8% | 29.5% |
| Basket scale in/out · VIX-scaled cap | 9.8% | 12.9% | 0.67 | -41.0% | -31.5% | -2.7% | +34.4% | -23.0% | 58% | 150.0 | 93 | 22.4% | 28.9% |
| Basket scale in/out · VIX-scaled cap (stock IV 1.3x HV) | 11.0% | 12.9% | 0.75 | -41.8% | -32.0% | +0.8% | +30.3% | -21.0% | 58% | 133.5 | 91 | 25.1% | 31.9% |
| Buy & hold QQQ 100% | 15.4% | 22.2% | 0.69 | -53.6% | -41.9% | -12.0% | +32.4% | -33.7% | 100% | – | – | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 12.9% | 17.6% | 0.69 | -45.0% | -34.4% | -7.7% | +26.2% | -27.3% | 80% | – | – | – | – |
| Buy & hold basket 80% (equal weight) | 20.3% | 20.3% | 0.94 | -51.1% | -38.1% | +12.8% | +53.1% | -35.8% | 80% | – | – | – | – |

Share of the account held as stock, by the first name's regime (scaling in at lows, out at highs):

- QQQ only · spikes: Low 64% · Mid 82% · High 87%
- QQQ only · spike puts, calls always on shares: Low 10% · Mid 2% · High 5%
- QQQ scale in/out · cap 80%: Low 36% · Mid 8% · High 6%
- QQQ scale in/out · VIX-scaled cap: Low 33% · Mid 7% · High 8%
- QQQ scale in/out · VIX cap to 100%: Low 39% · Mid 8% · High 9%
- QQQ scale in/out · VIX cap · 40Δ puts at lows: Low 34% · Mid 8% · High 8%
- QQQ scale in/out · VIX cap · puts only at IVR ≥ 30: Low 28% · Mid 6% · High 6%
- QQQ puts always on · calls only on up-spikes: Low 74% · Mid 86% · High 90%
- QQQ scale in/out · calls on half the shares: Low 38% · Mid 16% · High 22%
- QQQ scale in/out · calls only in High regime: Low 41% · Mid 29% · High 26%
- QQQ + SPY · spikes: Low 67% · Mid 84% · High 89%
- Basket · spikes (current rules): Low 45% · Mid 56% · High 63%
- Index core 50% + satellites · spikes: Low 55% · Mid 67% · High 73%
- Basket · always on: Low 45% · Mid 31% · High 30%
- Basket scale in/out · VIX-scaled cap: Low 39% · Mid 26% · High 25%

LEAP / poor man's covered call variants (Deployed = notional exposure; call P&L = premium kept after buybacks, per year as % of equity):

- QQQ PMCC · Tom King rules: in the market 90% of days, call premium 47.7%/yr, call P&L -6.7%/yr, 30 entries; exits: target 0, early 1, stop 7, LEAP at 120 DTE 21
- QQQ PMCC · Tom King rules · weekly IV 0.9x: in the market 90% of days, call premium 45.7%/yr, call P&L -10.2%/yr, 31 entries; exits: target 0, early 0, stop 9, LEAP at 120 DTE 21
- QQQ PMCC · trend calls, no filter/exits: in the market 100% of days, call premium 58.4%/yr, call P&L -8.5%/yr, 30 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 29
- QQQ LEAP · Tom's filter + exits, no calls: in the market 87% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 34 entries; exits: target 0, early 6, stop 10, LEAP at 120 DTE 17
- QQQ LEAP held (rolled at 120 DTE), no calls: in the market 100% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 30 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 29
- QQQ LEAP held · calls only on up-spikes: in the market 100% of days, call premium 1.5%/yr, call P&L +0.1%/yr, 30 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 29
- QQQ shares · Tom's trend calls: in the market 100% of days, call premium 105.7%/yr, call P&L -19.3%/yr, 1 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 0

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +1,189k, QQQ +3,547k
- **Basket · spikes (current rules)** P&L by name (excl. interest): IBIT -41k, HOOD +2k, GLD +43k, SOFI +50k, CEG +122k, FNV +180k, SPY +290k, AMZN +447k, GOOG +448k, MRVL +728k, TSLA +782k, QQQ +1,252k, MSTR +1,297k, NVDA +2,197k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): IBIT -51k, HOOD +19k, GLD +37k, SOFI +46k, FNV +49k, CEG +99k, MRVL +105k, GOOG +293k, MSTR +309k, TSLA +329k, AMZN +458k, SPY +711k, QQQ +1,986k, NVDA +3,783k
- **Basket · always on** P&L by name (excl. interest): IBIT +55k, GLD +69k, FNV +115k, SOFI +141k, HOOD +145k, SPY +193k, QQQ +210k, GOOG +264k, CEG +295k, AMZN +300k, MRVL +452k, MSTR +758k, TSLA +792k, NVDA +812k
- **Basket scale in/out · VIX-scaled cap** P&L by name (excl. interest): SOFI +38k, IBIT +41k, GLD +54k, FNV +64k, SPY +77k, HOOD +87k, CEG +111k, GOOG +127k, AMZN +136k, QQQ +143k, NVDA +258k, MRVL +304k, TSLA +392k, MSTR +462k

## 2021 → today (whole basket live) (2021-01-04 → 2026-10-08)

| Variant | CAGR | Vol | Sharpe | Max DD | Worst yr | 2008 | 2020 | 2022 | Deployed | Puts/yr | Assigned | Premium/yr | In shares |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ only · spikes | 7.0% | 3.8% | 0.94 | -4.5% | 0.2% | – | – | +2.7% | 17% | 4.5 | 1 | 1.4% | 14.0% |
| QQQ only · spike puts, calls always on shares | 4.0% | 1.5% | 0.47 | -1.8% | 0.2% | – | – | +2.7% | 4% | 4.5 | 1 | 1.4% | 0.9% |
| QQQ scale in/out · cap 80% | 7.2% | 11.4% | 0.38 | -19.0% | -17.1% | – | – | -17.1% | 56% | 93.9 | 14 | 10.7% | 17.3% |
| QQQ scale in/out · VIX-scaled cap | 7.3% | 10.0% | 0.43 | -16.1% | -13.5% | – | – | -13.5% | 50% | 86.3 | 13 | 9.9% | 16.0% |
| QQQ scale in/out · VIX cap to 100% | 7.5% | 11.5% | 0.40 | -19.1% | -16.5% | – | – | -16.6% | 55% | 91.7 | 14 | 10.7% | 18.5% |
| QQQ scale in/out · VIX cap · 40Δ puts at lows | 7.3% | 10.4% | 0.41 | -17.8% | -15.0% | – | – | -15.1% | 50% | 82.6 | 14 | 9.8% | 17.3% |
| QQQ scale in/out · VIX cap · puts only at IVR ≥ 30 | 5.7% | 8.6% | 0.31 | -13.7% | -9.4% | – | – | -9.4% | 29% | 37.6 | 8 | 6.1% | 13.8% |
| QQQ puts always on · calls only on up-spikes | 13.1% | 14.3% | 0.70 | -17.2% | -14.0% | – | – | -14.1% | 67% | 28.9 | 8 | 3.5% | 55.5% |
| QQQ scale in/out · calls on half the shares | 8.7% | 10.5% | 0.54 | -16.6% | -13.8% | – | – | -13.9% | 54% | 73.2 | 13 | 8.8% | 25.3% |
| QQQ scale in/out · calls only in High regime | 13.5% | 13.7% | 0.76 | -17.2% | -14.2% | – | – | -14.2% | 67% | 28.7 | 8 | 5.2% | 55.1% |
| QQQ PMCC · Tom King rules | 1.3% | 9.7% | -0.15 | -24.5% | -19.2% | – | – | -20.0% | 87% | – | – | 44.3% | – |
| QQQ PMCC · Tom King rules · weekly IV 0.9x | -1.8% | 9.5% | -0.49 | -29.4% | -19.3% | – | – | -20.0% | 88% | – | – | 43.6% | – |
| QQQ PMCC · trend calls, no filter/exits | -0.9% | 11.3% | -0.32 | -35.6% | -31.1% | – | – | -31.8% | 106% | – | – | 64.2% | – |
| QQQ LEAP · Tom's filter + exits, no calls | 8.6% | 15.2% | 0.40 | -27.0% | -23.8% | – | – | -24.5% | 84% | – | – | 0.0% | – |
| QQQ LEAP held (rolled at 120 DTE), no calls | 9.4% | 20.1% | 0.38 | -40.8% | -37.9% | – | – | -38.5% | 102% | – | – | 0.0% | – |
| QQQ LEAP held · calls only on up-spikes | 10.2% | 19.5% | 0.43 | -39.6% | -36.7% | – | – | -37.3% | 102% | – | – | 1.6% | – |
| QQQ shares · Tom's trend calls | 7.2% | 16.8% | 0.30 | -31.1% | -27.1% | – | – | -27.8% | 128% | – | – | 74.2% | – |
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
| Basket scale in/out · VIX-scaled cap (stock IV 1x HV) | 11.8% | 16.0% | 0.58 | -27.5% | -25.5% | – | – | -25.8% | 60% | 147.5 | 31 | 22.0% | 30.4% |
| Basket scale in/out · VIX-scaled cap | 17.8% | 17.0% | 0.86 | -24.9% | -21.4% | – | – | -21.8% | 60% | 150.6 | 27 | 27.4% | 29.3% |
| Basket scale in/out · VIX-scaled cap (stock IV 1.3x HV) | 17.8% | 14.8% | 0.96 | -23.1% | -17.9% | – | – | -18.4% | 60% | 170.6 | 30 | 33.1% | 24.8% |
| Buy & hold QQQ 100% | 16.6% | 22.4% | 0.65 | -35.6% | -33.1% | – | – | -33.7% | 100% | – | – | – | – |
| Buy & hold QQQ 80% / T-bills 20% | 14.1% | 17.8% | 0.65 | -29.0% | -26.7% | – | – | -27.3% | 80% | – | – | – | – |
| Buy & hold basket 80% (equal weight) | 26.1% | 24.6% | 0.93 | -38.6% | -34.7% | – | – | -35.8% | 80% | – | – | – | – |

Share of the account held as stock, by the first name's regime (scaling in at lows, out at highs):

- QQQ only · spikes: Low 7% · Mid 16% · High 18%
- QQQ only · spike puts, calls always on shares: Low 2% · Mid 1% · High 0%
- QQQ scale in/out · cap 80%: Low 45% · Mid 11% · High 6%
- QQQ scale in/out · VIX-scaled cap: Low 39% · Mid 10% · High 12%
- QQQ scale in/out · VIX cap to 100%: Low 46% · Mid 11% · High 14%
- QQQ scale in/out · VIX cap · 40Δ puts at lows: Low 43% · Mid 10% · High 13%
- QQQ scale in/out · VIX cap · puts only at IVR ≥ 30: Low 33% · Mid 10% · High 5%
- QQQ puts always on · calls only on up-spikes: Low 53% · Mid 55% · High 62%
- QQQ scale in/out · calls on half the shares: Low 44% · Mid 20% · High 25%
- QQQ scale in/out · calls only in High regime: Low 53% · Mid 54% · High 62%
- QQQ + SPY · spikes: Low 7% · Mid 15% · High 18%
- Basket · spikes (current rules): Low 25% · Mid 36% · High 45%
- Index core 50% + satellites · spikes: Low 27% · Mid 41% · High 50%
- Basket · always on: Low 47% · Mid 28% · High 34%
- Basket scale in/out · VIX-scaled cap: Low 38% · Mid 26% · High 33%

LEAP / poor man's covered call variants (Deployed = notional exposure; call P&L = premium kept after buybacks, per year as % of equity):

- QQQ PMCC · Tom King rules: in the market 84% of days, call premium 44.3%/yr, call P&L -6.8%/yr, 10 entries; exits: target 0, early 1, stop 4, LEAP at 120 DTE 4
- QQQ PMCC · Tom King rules · weekly IV 0.9x: in the market 84% of days, call premium 43.6%/yr, call P&L -9.9%/yr, 10 entries; exits: target 0, early 0, stop 4, LEAP at 120 DTE 5
- QQQ PMCC · trend calls, no filter/exits: in the market 100% of days, call premium 64.2%/yr, call P&L -10.3%/yr, 9 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 8
- QQQ LEAP · Tom's filter + exits, no calls: in the market 83% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 11 entries; exits: target 0, early 3, stop 4, LEAP at 120 DTE 3
- QQQ LEAP held (rolled at 120 DTE), no calls: in the market 100% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 9 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 8
- QQQ LEAP held · calls only on up-spikes: in the market 100% of days, call premium 1.6%/yr, call P&L +0.8%/yr, 9 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 8
- QQQ shares · Tom's trend calls: in the market 100% of days, call premium 74.2%/yr, call P&L -13.6%/yr, 1 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 0

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +17k, QQQ +143k
- **Basket · spikes (current rules)** P&L by name (excl. interest): IBIT -4k, GLD +2k, MRVL +2k, SPY +6k, HOOD +15k, SOFI +24k, CEG +28k, FNV +34k, GOOG +48k, TSLA +49k, QQQ +52k, AMZN +58k, MSTR +104k, NVDA +486k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): IBIT -6k, MRVL +2k, GLD +2k, HOOD +10k, SPY +11k, SOFI +25k, CEG +26k, FNV +33k, TSLA +44k, GOOG +48k, AMZN +57k, QQQ +137k, MSTR +145k, NVDA +488k
- **Basket · always on** P&L by name (excl. interest): GLD +4k, IBIT +4k, SPY +22k, FNV +23k, SOFI +25k, GOOG +31k, QQQ +32k, HOOD +42k, AMZN +60k, TSLA +63k, MRVL +74k, CEG +91k, NVDA +129k, MSTR +243k
- **Basket scale in/out · VIX-scaled cap** P&L by name (excl. interest): IBIT +1k, GLD +8k, SOFI +11k, FNV +12k, GOOG +14k, SPY +21k, QQQ +28k, HOOD +29k, NVDA +29k, AMZN +35k, CEG +56k, TSLA +58k, MRVL +97k, MSTR +275k

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
- _GVZ: yahoo+cboe 2008-06-03 → 2026-10-09 (4616 bars)
- _VIX: cboe 1990-01-02 → 2026-10-09 (9291 bars)
- _VXN: yahoo+cboe 2001-01-23 → 2026-10-09 (6469 bars)

## Caveats

- Option prices are Black-Scholes, not market quotes. Index names use VXN/VIX/GVZ × 0.9 as ATM IV with a fixed skew; single stocks use an assumed IV/HV multiple, so their premium (and the basket's edge) is a modelling choice: read the sensitivity rows.
- The basket is today's universe applied to the past (hindsight and survivorship bias in its favour).
- Prices exclude dividends (buy-and-hold is understated by ~0.6%/yr for QQQ, ~1.5% for SPY).
- Earnings IV, early assignment, rolling for credit beyond `max_rolls`, and integer contract sizes are not modelled.
- Trades fill at the signal day's close; the live scanner alerts intraday on delayed quotes.
