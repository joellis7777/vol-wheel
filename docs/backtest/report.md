# vol-wheel backtest

Generated 2026-10-11T18:41Z by `python -m vol_wheel.backtest` (workflow `backtest`). Account $500,000, cash yield _IRX. Single-stock IV is modelled as 1.15× max(HV20, HV60) unless a row says otherwise.

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
| QQQ puts+calls always · roll ITM both sides for credit | 4.7% | 9.3% | 0.37 | -33.1% | -23.3% | -3.7% | +3.5% | -9.5% | 48% | 86.5 | 16 | 20.1% | 12.2% |
| QQQ puts always · 5–10Δ calls rolled up, assigned only in High regime | 5.0% | 10.7% | 0.37 | -38.5% | -27.8% | -8.5% | +8.2% | -13.8% | 50% | 74.2 | 37 | 14.2% | 21.7% |
| QQQ puts always · 21-DTE 40Δ puts at lows · calls on up-spikes | 15.2% | 19.4% | 0.75 | -38.9% | -31.3% | +5.6% | +32.0% | -31.9% | 89% | 6.6 | 11 | 1.0% | 86.9% |
| MSTR · buy & hold 80% | 46.7% | 74.5% | 0.84 | -81.6% | -62.6% | – | +123.1% | -63.3% | 80% | – | – | – | – |
| MSTR · spikes (current rules) (stock IV 1x HV) | 11.2% | 20.9% | 0.47 | -40.3% | -9.9% | – | +0.7% | -1.2% | 22% | 6.9 | 7 | 8.8% | 15.5% |
| MSTR · spikes (current rules) | 12.3% | 19.8% | 0.53 | -40.4% | -10.7% | – | +0.8% | -0.5% | 22% | 6.9 | 6 | 10.7% | 16.1% |
| MSTR · spikes (current rules) (stock IV 1.3x HV) | 13.6% | 19.5% | 0.59 | -38.7% | -9.0% | – | +1.0% | +1.0% | 22% | 6.9 | 6 | 12.6% | 15.9% |
| MSTR · puts always · calls on up-spikes (stock IV 1x HV) | 24.1% | 51.9% | 0.62 | -63.5% | -58.6% | – | +4.0% | -59.3% | 69% | 54.2 | 23 | 34.2% | 46.8% |
| MSTR · puts always · calls on up-spikes | 28.7% | 53.5% | 0.68 | -62.6% | -57.9% | – | +5.1% | -58.6% | 71% | 48.5 | 22 | 37.3% | 50.2% |
| MSTR · puts always · calls on up-spikes (stock IV 1.3x HV) | 32.4% | 52.7% | 0.74 | -61.3% | -55.3% | – | +6.2% | -56.1% | 71% | 50.4 | 23 | 43.9% | 49.1% |
| MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up) (stock IV 1x HV) | 22.6% | 54.0% | 0.59 | -63.4% | -58.4% | – | +4.0% | -59.0% | 72% | 44.7 | 21 | 38.8% | 53.4% |
| MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up) | 22.9% | 55.7% | 0.59 | -67.5% | -56.0% | – | +5.1% | -56.7% | 72% | 33.8 | 16 | 40.5% | 58.6% |
| MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up) (stock IV 1.3x HV) | 25.5% | 73.7% | 0.63 | -85.0% | -54.4% | – | +6.2% | -55.2% | 87% | 28.9 | 14 | 29.9% | 75.0% |
| MSTR · as described (40Δ puts at lows, calls rolled up until tops) (stock IV 1x HV) | 18.8% | 50.5% | 0.53 | -66.7% | -60.6% | – | +6.1% | -61.3% | 69% | 44.7 | 19 | 40.2% | 50.1% |
| MSTR · as described (40Δ puts at lows, calls rolled up until tops) | 28.2% | 51.4% | 0.68 | -64.9% | -58.6% | – | +7.1% | -59.4% | 72% | 47.8 | 23 | 48.0% | 49.9% |
| MSTR · as described (40Δ puts at lows, calls rolled up until tops) (stock IV 1.3x HV) | 34.0% | 51.4% | 0.77 | -63.6% | -58.6% | – | +8.6% | -59.4% | 72% | 47.8 | 24 | 56.4% | 49.1% |
| MSTR · as described + puts rolled down & out (stock IV 1x HV) | 20.4% | 49.1% | 0.56 | -64.3% | -58.0% | – | +6.1% | -58.7% | 69% | 44.5 | 19 | 48.4% | 46.8% |
| MSTR · as described + puts rolled down & out | 23.0% | 44.1% | 0.62 | -60.7% | -54.2% | – | +7.1% | -54.9% | 70% | 57.7 | 23 | 68.4% | 37.8% |
| MSTR · as described + puts rolled down & out (stock IV 1.3x HV) | 29.0% | 41.9% | 0.75 | -57.5% | -50.3% | – | +8.6% | -51.1% | 70% | 64.1 | 24 | 83.2% | 34.4% |
| QQQ target 40%→100% shares by drawdown · via options | 9.6% | 13.0% | 0.65 | -36.8% | -22.9% | +11.9% | +15.9% | -18.5% | 50% | – | 16 | 2.1% | 50.1% |
| QQQ target 40%→100% shares by drawdown · via stock | 10.1% | 14.5% | 0.63 | -41.2% | -29.8% | +2.3% | +22.1% | -19.5% | 52% | – | 0 | 0.0% | 51.9% |
| QQQ target 60%→100% shares by drawdown · via options | 11.9% | 15.8% | 0.69 | -39.9% | -26.4% | +9.2% | +22.4% | -23.7% | 65% | – | 14 | 1.6% | 64.9% |
| QQQ target 60%→100% shares by drawdown · via stock | 12.0% | 17.0% | 0.66 | -45.8% | -34.6% | -2.5% | +26.2% | -24.9% | 69% | – | 0 | 0.0% | 68.6% |
| MSTR target 15%→100% shares by drawdown · via options (stock IV 1x HV) | 23.0% | 60.6% | 0.60 | -69.5% | -65.4% | – | +1.6% | -65.8% | 54% | – | 25 | 17.8% | 53.8% |
| MSTR target 15%→100% shares by drawdown · via options | 28.0% | 59.5% | 0.66 | -66.7% | -62.4% | – | +2.1% | -62.8% | 52% | – | 25 | 22.8% | 52.1% |
| MSTR target 15%→100% shares by drawdown · via options (stock IV 1.3x HV) | 33.6% | 59.4% | 0.73 | -61.9% | -57.0% | – | +2.5% | -57.4% | 54% | – | 25 | 24.1% | 53.8% |
| MSTR target 15%→100% shares by drawdown · via stock | 23.4% | 68.7% | 0.60 | -78.7% | -71.1% | – | +31.7% | -71.6% | 70% | – | 0 | 0.0% | 70.5% |
| MSTR target · deeper schedule (100% only at -88%) (stock IV 1x HV) | 22.6% | 36.5% | 0.66 | -42.2% | -36.7% | – | +1.1% | -37.1% | 33% | – | 21 | 15.8% | 33.0% |
| MSTR target · deeper schedule (100% only at -88%) | 25.3% | 36.8% | 0.72 | -42.1% | -35.0% | – | +1.4% | -35.5% | 34% | – | 21 | 17.9% | 33.9% |
| MSTR target · deeper schedule (100% only at -88%) (stock IV 1.3x HV) | 30.1% | 36.7% | 0.82 | -39.8% | -30.4% | – | +1.7% | -30.8% | 34% | – | 20 | 22.1% | 34.2% |
| MSTR target · deeper + trend cap 40% below a falling 200-day (stock IV 1x HV) | 17.9% | 26.7% | 0.63 | -34.2% | -28.7% | – | +1.1% | -29.2% | 26% | – | 14 | 11.1% | 26.0% |
| MSTR target · deeper + trend cap 40% below a falling 200-day | 20.0% | 27.0% | 0.70 | -34.8% | -26.8% | – | +1.4% | -27.3% | 27% | – | 13 | 13.1% | 26.7% |
| MSTR target · deeper + trend cap 40% below a falling 200-day (stock IV 1.3x HV) | 23.5% | 27.6% | 0.79 | -34.3% | -25.4% | – | +1.7% | -25.9% | 28% | – | 13 | 16.0% | 27.6% |
| MSTR target · deeper + trend cap + core calls at lows (stock IV 1x HV) | 16.2% | 25.1% | 0.60 | -33.6% | -28.2% | – | +1.1% | -28.7% | 24% | – | 14 | 12.3% | 24.1% |
| MSTR target · deeper + trend cap + core calls at lows | 18.4% | 25.4% | 0.67 | -34.4% | -26.1% | – | +1.4% | -26.6% | 25% | – | 13 | 14.6% | 24.8% |
| MSTR target · deeper + trend cap + core calls at lows (stock IV 1.3x HV) | 23.4% | 27.0% | 0.80 | -33.4% | -24.2% | – | +1.7% | -24.7% | 27% | – | 12 | 18.9% | 27.1% |
| QQQ target 60%→100% · trend cap 60% below a falling 200-day | 11.2% | 14.2% | 0.71 | -32.3% | -23.4% | +4.7% | +22.5% | -23.9% | 62% | – | 9 | 1.4% | 61.8% |
| Mix · QQQ 70 / GLD 30 (monthly rebalance) | 14.4% | 16.6% | 0.80 | -41.3% | -28.7% | +6.3% | +28.9% | -24.1% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 50 | 13.3% | 14.7% | 0.82 | -33.8% | -19.3% | +18.3% | +26.1% | -17.4% | 100% | – | – | – | – |
| Rotate · QQQ or GLD by 12-month momentum (else T-bills) | 11.2% | 19.3% | 0.57 | -32.8% | -19.2% | +25.1% | +12.9% | -19.7% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 25 / BTC 15 | 28.7% | 19.3% | 1.29 | -36.5% | -30.8% | – | +50.5% | -31.0% | 100% | – | – | – | – |
| Mix · QQQ 80 / BTC 20 | 33.4% | 24.6% | 1.21 | -44.8% | -39.5% | – | +61.0% | -40.0% | 100% | – | – | – | – |
| Rotate · QQQ / GLD / BTC by 12-month momentum | 56.1% | 57.6% | 1.03 | -82.2% | -61.0% | – | +160.6% | -26.4% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 20 / BTC 15 / XLE 15 | 27.6% | 19.2% | 1.25 | -30.7% | -22.1% | – | +38.9% | -22.7% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 20 / BTC 15 / TLT 15 | 25.1% | 17.3% | 1.25 | -37.8% | -32.1% | – | +48.0% | -32.0% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 20 / BTC 15 / XLP 15 | 26.7% | 18.3% | 1.27 | -33.5% | -28.3% | – | +46.1% | -28.4% | 100% | – | – | – | – |
| Mix · QQQ 45 / GLD 20 / BTC 15 / XLE 10 / TLT 10 | 25.5% | 17.5% | 1.26 | -31.9% | -25.5% | – | +41.1% | -25.7% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 25 / XLE 15 (2007→) | 13.3% | 17.1% | 0.72 | -42.7% | -30.7% | +1.1% | +19.4% | -15.0% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 25 / TLT 15 (2007→) | 12.3% | 13.9% | 0.80 | -34.8% | -25.4% | +6.7% | +26.4% | -25.2% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 40 (2007→) | 13.9% | 15.4% | 0.82 | -37.1% | -24.1% | +12.4% | +27.5% | -20.8% | 100% | – | – | – | – |
| Buy & hold BTC 100% | 69.9% | 65.4% | 1.11 | -83.0% | -74.5% | – | +201.1% | -64.3% | 100% | – | – | – | – |
| Buy & hold QQQ 100% (from 2015-10) | 19.8% | 22.1% | 0.83 | -35.6% | -33.1% | – | +32.4% | -33.7% | 100% | – | – | – | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with stock (2% band) | 29.2% | 19.3% | 1.31 | -35.6% | -30.0% | – | +54.4% | -30.2% | 99% | – | 0 | 0.0% | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with options (stock IV 1x HV) | 27.9% | 19.0% | 1.28 | -36.0% | -29.0% | – | +49.3% | -29.3% | 88% | – | 9 | 2.6% | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with options | 28.3% | 19.2% | 1.28 | -35.4% | -28.4% | – | +49.8% | -28.7% | 87% | – | 8 | 3.2% | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with options (stock IV 1.3x HV) | 30.0% | 19.6% | 1.33 | -35.8% | -29.1% | – | +53.2% | -29.3% | 88% | – | 13 | 2.7% | – |
| Core +XLE 50/20/15/15 · rebalanced with stock | 27.9% | 18.9% | 1.28 | -30.5% | -20.8% | – | +38.7% | -21.4% | 98% | – | 0 | 0.0% | – |
| Core +XLE 50/20/15/15 · rebalanced with options (stock IV 1x HV) | 27.0% | 19.2% | 1.23 | -31.0% | -22.6% | – | +41.7% | -23.0% | 91% | – | 11 | 2.1% | – |
| Core +XLE 50/20/15/15 · rebalanced with options | 28.1% | 19.3% | 1.27 | -31.2% | -21.4% | – | +41.8% | -21.9% | 91% | – | 12 | 2.5% | – |
| Core +XLE 50/20/15/15 · rebalanced with options (stock IV 1.3x HV) | 28.3% | 19.2% | 1.28 | -31.1% | -20.9% | – | +42.1% | -21.4% | 90% | – | 11 | 2.7% | – |
| Core +XLE · options, stock for gaps > 8% (stock IV 1x HV) | 26.6% | 18.3% | 1.27 | -29.8% | -19.6% | – | +41.1% | -20.1% | 91% | – | 9 | 2.5% | – |
| Core +XLE · options, stock for gaps > 8% | 26.8% | 18.4% | 1.26 | -30.3% | -19.4% | – | +40.4% | -19.9% | 92% | – | 8 | 2.6% | – |
| Core +XLE · options, stock for gaps > 8% (stock IV 1.3x HV) | 27.1% | 18.4% | 1.28 | -30.2% | -19.0% | – | +40.7% | -19.5% | 91% | – | 8 | 2.7% | – |
| Core +XLE · options · 80% invested (20% SGOV) (stock IV 1x HV) | 22.7% | 15.5% | 1.26 | -24.8% | -16.7% | – | +33.2% | -17.2% | 74% | – | 6 | 2.0% | – |
| Core +XLE · options · 80% invested (20% SGOV) | 22.0% | 15.5% | 1.22 | -25.7% | -17.9% | – | +34.4% | -18.3% | 76% | – | 4 | 1.3% | – |
| Core +XLE · options · 80% invested (20% SGOV) (stock IV 1.3x HV) | 22.2% | 15.4% | 1.24 | -25.1% | -17.1% | – | +35.4% | -17.6% | 75% | – | 4 | 1.6% | – |
| Mix · core +XLE · monthly rebalance · 80% invested | 22.4% | 15.3% | 1.26 | -24.9% | -17.5% | – | +31.4% | -17.9% | 80% | – | – | – | – |
| Core QQQ 60/GLD 25/XLE 15 · stock (2007→) | 13.1% | 17.1% | 0.72 | -43.6% | -31.7% | -0.9% | +20.1% | -15.0% | 98% | – | 0 | 0.0% | – |
| Core QQQ 60/GLD 25/XLE 15 · options (2007→) (stock IV 1x HV) | 13.4% | 16.5% | 0.75 | -41.5% | -29.4% | -0.0% | +22.9% | -14.3% | 96% | – | 10 | 0.8% | – |
| Core QQQ 60/GLD 25/XLE 15 · options (2007→) | 13.6% | 16.4% | 0.76 | -41.5% | -29.3% | +0.0% | +23.1% | -13.5% | 97% | – | 10 | 0.6% | – |
| Core QQQ 60/GLD 25/XLE 15 · options (2007→) (stock IV 1.3x HV) | 13.5% | 16.5% | 0.75 | -41.5% | -29.3% | +0.1% | +21.1% | -13.7% | 97% | – | 9 | 0.7% | – |
| QQQ PMCC · Tom King rules | 1.4% | 9.7% | 0.04 | -27.4% | -15.2% | -5.8% | +8.6% | -11.9% | 94% | – | – | 47.7% | – |
| QQQ PMCC · Tom King rules · weekly IV 0.9x | -2.4% | 9.6% | -0.36 | -53.0% | -23.1% | -13.6% | +7.8% | -23.8% | 95% | – | – | 45.7% | – |
| QQQ PMCC · trend calls, no filter/exits | 0.1% | 10.8% | -0.08 | -35.7% | -31.6% | -9.2% | +9.3% | -32.2% | 105% | – | – | 58.4% | – |
| QQQ LEAP · Tom's filter + exits, no calls | 7.7% | 14.9% | 0.47 | -33.2% | -23.7% | -7.4% | +22.4% | -24.5% | 88% | – | – | 0.0% | – |
| QQQ LEAP held (rolled at 120 DTE), no calls | 8.4% | 18.7% | 0.44 | -55.4% | -42.6% | -23.0% | +25.0% | -38.3% | 102% | – | – | 0.0% | – |
| QQQ LEAP held · calls only on up-spikes | 8.3% | 18.3% | 0.44 | -53.8% | -41.5% | -21.8% | +26.8% | -37.1% | 102% | – | – | 1.5% | – |
| QQQ shares · Tom's trend calls | 7.0% | 13.2% | 0.47 | -32.3% | -25.2% | +3.8% | +17.1% | -25.9% | 100% | – | – | 56.3% | – |
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
- QQQ puts+calls always · roll ITM both sides for credit: Low 18% · Mid 8% · High 18%
- QQQ puts always · 5–10Δ calls rolled up, assigned only in High regime: Low 38% · Mid 18% · High 15%
- QQQ puts always · 21-DTE 40Δ puts at lows · calls on up-spikes: Low 77% · Mid 88% · High 93%
- MSTR · spikes (current rules): Low 17% · Mid 17% · High 14%
- MSTR · puts always · calls on up-spikes: Low 59% · Mid 49% · High 43%
- MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up): Low 63% · Mid 59% · High 53%
- MSTR · as described (40Δ puts at lows, calls rolled up until tops): Low 60% · Mid 47% · High 43%
- MSTR · as described + puts rolled down & out: Low 44% · Mid 38% · High 31%
- QQQ + SPY · spikes: Low 67% · Mid 84% · High 89%
- Basket · spikes (current rules): Low 45% · Mid 56% · High 63%
- Index core 50% + satellites · spikes: Low 55% · Mid 67% · High 73%
- Basket · always on: Low 45% · Mid 31% · High 30%
- Basket scale in/out · VIX-scaled cap: Low 39% · Mid 26% · High 25%

Rotation variants (share of months holding each):

- Rotate · QQQ or GLD by 12-month momentum (else T-bills): QQQ 57%, GLD 35%, T-bills 8%
- Rotate · QQQ / GLD / BTC by 12-month momentum: QQQ 14%, GLD 11%, BTC-USD 66%, T-bills 8%

Multi-asset core variants (average weights; option premium and stock turnover per year, % of equity):

- Core QQQ 60/GLD 25/BTC 15 · rebalanced with stock (2% band): QQQ 60% · GLD 24% · BTC-USD 15%; premium 0.0%/yr, stock turnover 28%/yr, 0 puts / 0 calls, assigned 0, called away 0; positive months 67%, worst 12 months -35.3%
- Core QQQ 60/GLD 25/BTC 15 · rebalanced with options: QQQ 52% · GLD 17% · BTC-USD 18%; premium 3.2%/yr, stock turnover 1%/yr, 406 puts / 95 calls, assigned 8, called away 10; positive months 65%, worst 12 months -35.0%
- Core +XLE 50/20/15/15 · rebalanced with stock: QQQ 50% · GLD 19% · BTC-USD 15% · XLE 14%; premium 0.0%/yr, stock turnover 30%/yr, 0 puts / 0 calls, assigned 0, called away 0; positive months 65%, worst 12 months -27.5%
- Core +XLE 50/20/15/15 · rebalanced with options: QQQ 44% · GLD 16% · BTC-USD 18% · XLE 12%; premium 2.5%/yr, stock turnover 2%/yr, 286 puts / 97 calls, assigned 12, called away 12; positive months 66%, worst 12 months -28.6%
- Core +XLE · options, stock for gaps > 8%: QQQ 48% · GLD 18% · BTC-USD 14% · XLE 12%; premium 2.6%/yr, stock turnover 6%/yr, 276 puts / 47 calls, assigned 8, called away 6; positive months 67%, worst 12 months -25.2%
- Core +XLE · options · 80% invested (20% SGOV): QQQ 38% · GLD 14% · BTC-USD 14% · XLE 10%; premium 1.3%/yr, stock turnover 2%/yr, 130 puts / 73 calls, assigned 4, called away 9; positive months 65%, worst 12 months -24.5%
- Core QQQ 60/GLD 25/XLE 15 · stock (2007→): QQQ 61% · GLD 24% · XLE 13%; premium 0.0%/yr, stock turnover 13%/yr, 0 puts / 0 calls, assigned 0, called away 0; positive months 65%, worst 12 months -39.0%
- Core QQQ 60/GLD 25/XLE 15 · options (2007→): QQQ 60% · GLD 24% · XLE 12%; premium 0.6%/yr, stock turnover 1%/yr, 181 puts / 122 calls, assigned 10, called away 10; positive months 65%, worst 12 months -37.1%

Target-allocation variants (shares held by distance below the high; consistency = % of positive months and the worst 12-month return):

- QQQ target 40%→100% shares by drawdown · via options: in shares near high (<10%) 46% · 10-30% down 57% · >30% down 72%; positive months 67%, worst 12 months -32.2%; premium 2.1%/yr, 274 puts / 240 calls, assigned 16, called away 19
- QQQ target 40%→100% shares by drawdown · via stock: in shares near high (<10%) 45% · 10-30% down 66% · >30% down 89%; positive months 67%, worst 12 months -38.2%; stock turnover 131%/yr
- QQQ target 60%→100% shares by drawdown · via options: in shares near high (<10%) 63% · 10-30% down 68% · >30% down 79%; positive months 65%, worst 12 months -35.3%; premium 1.6%/yr, 230 puts / 183 calls, assigned 14, called away 14
- QQQ target 60%→100% shares by drawdown · via stock: in shares near high (<10%) 64% · 10-30% down 78% · >30% down 95%; positive months 66%, worst 12 months -42.0%; stock turnover 67%/yr
- MSTR target 15%→100% shares by drawdown · via options: in shares near high (<10%) 36% · 10-30% down 31% · >30% down 59%; positive months 62%, worst 12 months -63.8%; premium 22.8%/yr, 180 puts / 53 calls, assigned 25, called away 12
- MSTR target 15%→100% shares by drawdown · via stock: in shares near high (<10%) 19% · 10-30% down 35% · >30% down 84%; positive months 55%, worst 12 months -73.6%; stock turnover 498%/yr
- MSTR target · deeper schedule (100% only at -88%): in shares near high (<10%) 26% · 10-30% down 27% · >30% down 36%; positive months 59%, worst 12 months -38.9%; premium 17.9%/yr, 159 puts / 79 calls, assigned 21, called away 10
- MSTR target · deeper + trend cap 40% below a falling 200-day: in shares near high (<10%) 26% · 10-30% down 27% · >30% down 27%; positive months 59%, worst 12 months -31.5%; premium 13.1%/yr, 146 puts / 52 calls, assigned 13, called away 7
- MSTR target · deeper + trend cap + core calls at lows: in shares near high (<10%) 24% · 10-30% down 26% · >30% down 24%; positive months 59%, worst 12 months -31.0%; premium 14.6%/yr, 157 puts / 122 calls, assigned 13, called away 7
- QQQ target 60%→100% · trend cap 60% below a falling 200-day: in shares near high (<10%) 62% · 10-30% down 61% · >30% down 61%; positive months 65%, worst 12 months -27.5%; premium 1.4%/yr, 232 puts / 169 calls, assigned 9, called away 10

LEAP / poor man's covered call variants (Deployed = notional exposure; call P&L = premium kept after buybacks, per year as % of equity):

- QQQ PMCC · Tom King rules: in the market 90% of days, call premium 47.7%/yr, call P&L -6.7%/yr, 30 entries; exits: target 0, early 1, stop 7, LEAP at 120 DTE 21
- QQQ PMCC · Tom King rules · weekly IV 0.9x: in the market 90% of days, call premium 45.7%/yr, call P&L -10.2%/yr, 31 entries; exits: target 0, early 0, stop 9, LEAP at 120 DTE 21
- QQQ PMCC · trend calls, no filter/exits: in the market 100% of days, call premium 58.4%/yr, call P&L -8.5%/yr, 30 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 29
- QQQ LEAP · Tom's filter + exits, no calls: in the market 87% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 34 entries; exits: target 0, early 6, stop 10, LEAP at 120 DTE 17
- QQQ LEAP held (rolled at 120 DTE), no calls: in the market 100% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 30 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 29
- QQQ LEAP held · calls only on up-spikes: in the market 100% of days, call premium 1.5%/yr, call P&L +0.1%/yr, 30 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 29
- QQQ shares · Tom's trend calls: in the market 100% of days, call premium 56.3%/yr, call P&L -9.6%/yr, 1 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 0

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
| QQQ puts+calls always · roll ITM both sides for credit | 7.4% | 8.7% | 0.49 | -12.6% | -9.5% | – | – | -9.5% | 54% | 69.9 | 8 | 28.4% | 23.7% |
| QQQ puts always · 5–10Δ calls rolled up, assigned only in High regime | 6.7% | 10.0% | 0.37 | -16.3% | -13.7% | – | – | -13.8% | 52% | 74.1 | 13 | 18.7% | 22.4% |
| QQQ puts always · 21-DTE 40Δ puts at lows · calls on up-spikes | 13.7% | 16.0% | 0.68 | -21.3% | -17.3% | – | – | -17.3% | 73% | 25.2 | 9 | 3.0% | 63.7% |
| MSTR · buy & hold 80% | 28.9% | 74.9% | 0.67 | -81.6% | -62.6% | – | – | -63.3% | 80% | – | – | – | – |
| MSTR · spikes (current rules) (stock IV 1x HV) | 11.8% | 21.5% | 0.47 | -40.3% | -9.9% | – | – | -1.2% | 22% | 6.6 | 7 | 8.9% | 16.4% |
| MSTR · spikes (current rules) | 12.9% | 20.4% | 0.54 | -40.4% | -10.7% | – | – | -0.5% | 23% | 6.6 | 6 | 10.9% | 17.1% |
| MSTR · spikes (current rules) (stock IV 1.3x HV) | 14.3% | 20.1% | 0.60 | -38.7% | -9.0% | – | – | +1.0% | 23% | 6.6 | 6 | 12.8% | 16.8% |
| MSTR · puts always · calls on up-spikes (stock IV 1x HV) | 24.8% | 53.4% | 0.62 | -63.5% | -58.6% | – | – | -59.3% | 71% | 50.1 | 23 | 34.5% | 49.5% |
| MSTR · puts always · calls on up-spikes | 29.5% | 55.0% | 0.69 | -62.6% | -57.9% | – | – | -58.6% | 73% | 44.0 | 22 | 37.4% | 53.2% |
| MSTR · puts always · calls on up-spikes (stock IV 1.3x HV) | 33.1% | 54.2% | 0.74 | -61.3% | -55.3% | – | – | -56.1% | 73% | 46.1 | 23 | 44.0% | 52.0% |
| MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up) (stock IV 1x HV) | 23.2% | 55.6% | 0.60 | -63.4% | -58.4% | – | – | -59.0% | 74% | 40.0 | 21 | 39.2% | 56.5% |
| MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up) | 23.3% | 57.3% | 0.60 | -67.5% | -56.0% | – | – | -56.7% | 74% | 28.5 | 16 | 40.7% | 62.0% |
| MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up) (stock IV 1.3x HV) | 25.8% | 75.8% | 0.64 | -85.0% | -54.4% | – | – | -55.2% | 90% | 23.3 | 14 | 29.8% | 79.4% |
| MSTR · as described (40Δ puts at lows, calls rolled up until tops) (stock IV 1x HV) | 18.8% | 51.9% | 0.53 | -66.7% | -60.6% | – | – | -61.3% | 71% | 40.0 | 19 | 40.3% | 53.0% |
| MSTR · as described (40Δ puts at lows, calls rolled up until tops) | 29.2% | 52.8% | 0.69 | -64.3% | -59.0% | – | – | -59.7% | 73% | 44.2 | 23 | 48.2% | 51.9% |
| MSTR · as described (40Δ puts at lows, calls rolled up until tops) (stock IV 1.3x HV) | 33.9% | 52.8% | 0.76 | -63.6% | -58.6% | – | – | -59.4% | 74% | 43.3 | 24 | 56.5% | 52.0% |
| MSTR · as described + puts rolled down & out (stock IV 1x HV) | 20.4% | 50.5% | 0.56 | -64.3% | -58.0% | – | – | -58.7% | 71% | 39.8 | 19 | 48.7% | 49.6% |
| MSTR · as described + puts rolled down & out | 23.2% | 45.3% | 0.62 | -60.7% | -54.2% | – | – | -54.9% | 71% | 53.7 | 23 | 69.1% | 40.0% |
| MSTR · as described + puts rolled down & out (stock IV 1.3x HV) | 28.7% | 43.1% | 0.73 | -57.5% | -50.3% | – | – | -51.1% | 72% | 60.5 | 24 | 83.8% | 36.4% |
| QQQ target 40%→100% shares by drawdown · via options | 10.6% | 11.8% | 0.64 | -15.7% | -12.7% | – | – | -12.7% | 43% | – | 9 | 3.1% | 42.8% |
| QQQ target 40%→100% shares by drawdown · via stock | 11.4% | 13.8% | 0.62 | -21.6% | -19.2% | – | – | -19.5% | 53% | – | 0 | 0.0% | 52.7% |
| QQQ target 60%→100% shares by drawdown · via options | 12.9% | 14.2% | 0.70 | -17.0% | -13.6% | – | – | -13.6% | 54% | – | 9 | 3.0% | 53.8% |
| QQQ target 60%→100% shares by drawdown · via stock | 13.2% | 16.7% | 0.63 | -26.7% | -24.4% | – | – | -24.9% | 69% | – | 0 | 0.0% | 69.1% |
| MSTR target 15%→100% shares by drawdown · via options (stock IV 1x HV) | 24.0% | 62.4% | 0.61 | -69.5% | -65.4% | – | – | -65.8% | 57% | – | 25 | 18.0% | 56.9% |
| MSTR target 15%→100% shares by drawdown · via options | 29.4% | 61.2% | 0.68 | -66.7% | -62.4% | – | – | -62.8% | 55% | – | 25 | 23.1% | 55.1% |
| MSTR target 15%→100% shares by drawdown · via options (stock IV 1.3x HV) | 35.3% | 61.1% | 0.75 | -61.9% | -57.0% | – | – | -57.4% | 57% | – | 25 | 24.3% | 56.9% |
| MSTR target 15%→100% shares by drawdown · via stock | 18.8% | 70.5% | 0.55 | -78.7% | -71.1% | – | – | -71.6% | 73% | – | 0 | 0.0% | 72.8% |
| MSTR target · deeper schedule (100% only at -88%) (stock IV 1x HV) | 23.9% | 37.6% | 0.67 | -42.2% | -36.7% | – | – | -37.1% | 35% | – | 21 | 16.0% | 34.9% |
| MSTR target · deeper schedule (100% only at -88%) | 26.7% | 37.9% | 0.73 | -42.1% | -35.0% | – | – | -35.5% | 36% | – | 21 | 18.2% | 35.8% |
| MSTR target · deeper schedule (100% only at -88%) (stock IV 1.3x HV) | 31.8% | 37.7% | 0.84 | -39.8% | -30.4% | – | – | -30.8% | 36% | – | 20 | 22.4% | 36.2% |
| MSTR target · deeper + trend cap 40% below a falling 200-day (stock IV 1x HV) | 18.9% | 27.5% | 0.65 | -34.2% | -28.7% | – | – | -29.2% | 28% | – | 14 | 11.2% | 27.5% |
| MSTR target · deeper + trend cap 40% below a falling 200-day | 21.0% | 27.8% | 0.71 | -34.8% | -26.8% | – | – | -27.3% | 28% | – | 13 | 13.3% | 28.3% |
| MSTR target · deeper + trend cap 40% below a falling 200-day (stock IV 1.3x HV) | 24.7% | 28.4% | 0.80 | -34.3% | -25.4% | – | – | -25.9% | 29% | – | 13 | 16.1% | 29.2% |
| MSTR target · deeper + trend cap + core calls at lows (stock IV 1x HV) | 17.1% | 25.8% | 0.62 | -33.6% | -28.2% | – | – | -28.7% | 26% | – | 14 | 12.5% | 25.5% |
| MSTR target · deeper + trend cap + core calls at lows | 19.3% | 26.1% | 0.68 | -34.4% | -26.1% | – | – | -26.6% | 26% | – | 13 | 14.8% | 26.2% |
| MSTR target · deeper + trend cap + core calls at lows (stock IV 1.3x HV) | 24.6% | 27.8% | 0.82 | -33.4% | -24.2% | – | – | -24.7% | 29% | – | 12 | 19.2% | 28.7% |
| QQQ target 60%→100% · trend cap 60% below a falling 200-day | 11.9% | 13.2% | 0.68 | -15.8% | -13.0% | – | – | -13.0% | 51% | – | 7 | 2.6% | 51.0% |
| Mix · QQQ 70 / GLD 30 (monthly rebalance) | 16.4% | 17.4% | 0.77 | -28.6% | -24.0% | – | – | -24.1% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 50 | 15.9% | 15.5% | 0.82 | -24.0% | -17.6% | – | – | -17.4% | 100% | – | – | – | – |
| Rotate · QQQ or GLD by 12-month momentum (else T-bills) | 14.2% | 19.2% | 0.62 | -26.1% | -18.9% | – | – | -19.7% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 25 / BTC 15 | 18.7% | 19.7% | 0.81 | -36.5% | -30.8% | – | – | -31.0% | 100% | – | – | – | – |
| Mix · QQQ 80 / BTC 20 | 19.4% | 24.6% | 0.71 | -44.8% | -39.5% | – | – | -40.0% | 100% | – | – | – | – |
| Rotate · QQQ / GLD / BTC by 12-month momentum | 20.1% | 46.3% | 0.56 | -59.2% | -26.2% | – | – | -26.4% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 20 / BTC 15 / XLE 15 | 20.5% | 18.7% | 0.92 | -28.9% | -22.1% | – | – | -22.7% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 20 / BTC 15 / TLT 15 | 14.2% | 17.8% | 0.65 | -37.8% | -32.1% | – | – | -32.0% | 100% | – | – | – | – |
| Mix · QQQ 50 / GLD 20 / BTC 15 / XLP 15 | 17.0% | 18.0% | 0.78 | -33.5% | -28.3% | – | – | -28.4% | 100% | – | – | – | – |
| Mix · QQQ 45 / GLD 20 / BTC 15 / XLE 10 / TLT 10 | 16.8% | 17.4% | 0.79 | -31.9% | -25.5% | – | – | -25.7% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 25 / XLE 15 (2007→) | 18.1% | 16.2% | 0.91 | -21.0% | -14.4% | – | – | -15.0% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 25 / TLT 15 (2007→) | 11.9% | 15.3% | 0.60 | -29.7% | -25.4% | – | – | -25.2% | 100% | – | – | – | – |
| Mix · QQQ 60 / GLD 40 (2007→) | 16.2% | 16.3% | 0.80 | -26.3% | -20.8% | – | – | -20.8% | 100% | – | – | – | – |
| Buy & hold BTC 100% | 17.7% | 57.1% | 0.51 | -76.6% | -64.1% | – | – | -64.3% | 100% | – | – | – | – |
| Buy & hold QQQ 100% (from 2015-10) | 16.6% | 22.4% | 0.65 | -35.6% | -33.1% | – | – | -33.7% | 100% | – | – | – | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with stock (2% band) | 18.3% | 19.5% | 0.79 | -36.7% | -30.6% | – | – | -30.8% | 99% | – | 0 | 0.0% | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with options (stock IV 1x HV) | 16.8% | 19.9% | 0.72 | -38.6% | -32.1% | – | – | -32.3% | 97% | – | 1 | 1.1% | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with options | 16.8% | 19.9% | 0.72 | -38.8% | -32.1% | – | – | -32.3% | 97% | – | 1 | 1.1% | – |
| Core QQQ 60/GLD 25/BTC 15 · rebalanced with options (stock IV 1.3x HV) | 16.8% | 19.9% | 0.71 | -38.6% | -32.0% | – | – | -32.2% | 98% | – | 1 | 1.1% | – |
| Core +XLE 50/20/15/15 · rebalanced with stock | 20.2% | 18.5% | 0.92 | -29.2% | -20.9% | – | – | -21.5% | 99% | – | 0 | 0.0% | – |
| Core +XLE 50/20/15/15 · rebalanced with options (stock IV 1x HV) | 18.5% | 18.7% | 0.83 | -29.7% | -20.6% | – | – | -21.3% | 96% | – | 4 | 1.2% | – |
| Core +XLE 50/20/15/15 · rebalanced with options | 18.8% | 18.7% | 0.84 | -29.4% | -20.1% | – | – | -20.7% | 95% | – | 3 | 1.6% | – |
| Core +XLE 50/20/15/15 · rebalanced with options (stock IV 1.3x HV) | 19.3% | 18.6% | 0.86 | -29.1% | -19.3% | – | – | -20.0% | 95% | – | 2 | 1.9% | – |
| Core +XLE · options, stock for gaps > 8% (stock IV 1x HV) | 19.9% | 18.5% | 0.90 | -28.6% | -19.4% | – | – | -20.1% | 94% | – | 4 | 1.9% | – |
| Core +XLE · options, stock for gaps > 8% | 19.9% | 18.4% | 0.90 | -28.4% | -19.1% | – | – | -19.7% | 94% | – | 4 | 2.0% | – |
| Core +XLE · options, stock for gaps > 8% (stock IV 1.3x HV) | 19.9% | 18.5% | 0.90 | -27.9% | -18.4% | – | – | -19.1% | 94% | – | 3 | 2.5% | – |
| Core +XLE · options · 80% invested (20% SGOV) (stock IV 1x HV) | 16.0% | 14.9% | 0.85 | -23.4% | -14.7% | – | – | -15.3% | 77% | – | 1 | 1.3% | – |
| Core +XLE · options · 80% invested (20% SGOV) | 15.4% | 15.1% | 0.81 | -22.8% | -14.1% | – | – | -14.7% | 77% | – | 0 | 1.5% | – |
| Core +XLE · options · 80% invested (20% SGOV) (stock IV 1.3x HV) | 15.4% | 15.1% | 0.81 | -22.8% | -14.0% | – | – | -14.6% | 77% | – | 0 | 1.7% | – |
| Mix · core +XLE · monthly rebalance · 80% invested | 17.1% | 15.0% | 0.91 | -23.4% | -17.5% | – | – | -17.9% | 80% | – | – | – | – |
| Core QQQ 60/GLD 25/XLE 15 · stock (2007→) | 17.9% | 16.2% | 0.90 | -21.7% | -14.8% | – | – | -15.4% | 100% | – | 0 | 0.0% | – |
| Core QQQ 60/GLD 25/XLE 15 · options (2007→) (stock IV 1x HV) | 17.4% | 16.1% | 0.87 | -20.3% | -13.2% | – | – | -13.9% | 96% | – | 2 | 0.6% | – |
| Core QQQ 60/GLD 25/XLE 15 · options (2007→) | 17.4% | 16.1% | 0.88 | -20.2% | -13.0% | – | – | -13.7% | 96% | – | 2 | 0.7% | – |
| Core QQQ 60/GLD 25/XLE 15 · options (2007→) (stock IV 1.3x HV) | 17.6% | 16.3% | 0.87 | -20.0% | -12.5% | – | – | -13.3% | 99% | – | 1 | 0.5% | – |
| QQQ PMCC · Tom King rules | 1.3% | 9.7% | -0.15 | -24.5% | -19.2% | – | – | -20.0% | 87% | – | – | 44.3% | – |
| QQQ PMCC · Tom King rules · weekly IV 0.9x | -1.8% | 9.5% | -0.49 | -29.4% | -19.3% | – | – | -20.0% | 88% | – | – | 43.6% | – |
| QQQ PMCC · trend calls, no filter/exits | -0.9% | 11.3% | -0.32 | -35.6% | -31.1% | – | – | -31.8% | 106% | – | – | 64.2% | – |
| QQQ LEAP · Tom's filter + exits, no calls | 8.6% | 15.2% | 0.40 | -27.0% | -23.8% | – | – | -24.5% | 84% | – | – | 0.0% | – |
| QQQ LEAP held (rolled at 120 DTE), no calls | 9.4% | 20.1% | 0.38 | -40.8% | -37.9% | – | – | -38.5% | 102% | – | – | 0.0% | – |
| QQQ LEAP held · calls only on up-spikes | 10.2% | 19.5% | 0.43 | -39.6% | -36.7% | – | – | -37.3% | 102% | – | – | 1.6% | – |
| QQQ shares · Tom's trend calls | 5.9% | 13.0% | 0.25 | -29.1% | -25.2% | – | – | -25.9% | 100% | – | – | 59.4% | – |
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
- QQQ puts+calls always · roll ITM both sides for credit: Low 26% · Mid 20% · High 36%
- QQQ puts always · 5–10Δ calls rolled up, assigned only in High regime: Low 39% · Mid 18% · High 20%
- QQQ puts always · 21-DTE 40Δ puts at lows · calls on up-spikes: Low 67% · Mid 62% · High 69%
- MSTR · spikes (current rules): Low 17% · Mid 17% · High 18%
- MSTR · puts always · calls on up-spikes: Low 59% · Mid 49% · High 52%
- MSTR · Nithu's posted rule (calls after rallies, ~20Δ, rolled up): Low 63% · Mid 59% · High 65%
- MSTR · as described (40Δ puts at lows, calls rolled up until tops): Low 60% · Mid 45% · High 51%
- MSTR · as described + puts rolled down & out: Low 44% · Mid 38% · High 37%
- QQQ + SPY · spikes: Low 7% · Mid 15% · High 18%
- Basket · spikes (current rules): Low 25% · Mid 36% · High 45%
- Index core 50% + satellites · spikes: Low 27% · Mid 41% · High 50%
- Basket · always on: Low 47% · Mid 28% · High 34%
- Basket scale in/out · VIX-scaled cap: Low 38% · Mid 26% · High 33%

Rotation variants (share of months holding each):

- Rotate · QQQ or GLD by 12-month momentum (else T-bills): QQQ 47%, GLD 40%, T-bills 13%
- Rotate · QQQ / GLD / BTC by 12-month momentum: QQQ 9%, GLD 21%, BTC-USD 57%, T-bills 13%

Multi-asset core variants (average weights; option premium and stock turnover per year, % of equity):

- Core QQQ 60/GLD 25/BTC 15 · rebalanced with stock (2% band): QQQ 60% · GLD 24% · BTC-USD 15%; premium 0.0%/yr, stock turnover 26%/yr, 0 puts / 0 calls, assigned 0, called away 0; positive months 65%, worst 12 months -36.4%
- Core QQQ 60/GLD 25/BTC 15 · rebalanced with options: QQQ 59% · GLD 22% · BTC-USD 16%; premium 1.1%/yr, stock turnover 12%/yr, 69 puts / 29 calls, assigned 1, called away 1; positive months 64%, worst 12 months -38.5%
- Core +XLE 50/20/15/15 · rebalanced with stock: QQQ 49% · GLD 20% · BTC-USD 15% · XLE 15%; premium 0.0%/yr, stock turnover 26%/yr, 0 puts / 0 calls, assigned 0, called away 0; positive months 64%, worst 12 months -28.0%
- Core +XLE 50/20/15/15 · rebalanced with options: QQQ 48% · GLD 16% · BTC-USD 17% · XLE 15%; premium 1.6%/yr, stock turnover 11%/yr, 78 puts / 47 calls, assigned 3, called away 3; positive months 64%, worst 12 months -27.7%
- Core +XLE · options, stock for gaps > 8%: QQQ 48% · GLD 16% · BTC-USD 15% · XLE 14%; premium 2.0%/yr, stock turnover 12%/yr, 117 puts / 33 calls, assigned 4, called away 3; positive months 64%, worst 12 months -26.7%
- Core +XLE · options · 80% invested (20% SGOV): QQQ 38% · GLD 14% · BTC-USD 14% · XLE 12%; premium 1.5%/yr, stock turnover 9%/yr, 31 puts / 46 calls, assigned 0, called away 1; positive months 64%, worst 12 months -21.3%
- Core QQQ 60/GLD 25/XLE 15 · stock (2007→): QQQ 61% · GLD 24% · XLE 14%; premium 0.0%/yr, stock turnover 21%/yr, 0 puts / 0 calls, assigned 0, called away 0; positive months 70%, worst 12 months -17.2%
- Core QQQ 60/GLD 25/XLE 15 · options (2007→): QQQ 60% · GLD 22% · XLE 14%; premium 0.7%/yr, stock turnover 11%/yr, 65 puts / 13 calls, assigned 2, called away 2; positive months 70%, worst 12 months -15.4%

Target-allocation variants (shares held by distance below the high; consistency = % of positive months and the worst 12-month return):

- QQQ target 40%→100% shares by drawdown · via options: in shares near high (<10%) 38% · 10-30% down 53% · >30% down 69%; positive months 67%, worst 12 months -14.2%; premium 3.1%/yr, 134 puts / 59 calls, assigned 9, called away 7
- QQQ target 40%→100% shares by drawdown · via stock: in shares near high (<10%) 45% · 10-30% down 68% · >30% down 82%; positive months 65%, worst 12 months -21.1%; stock turnover 135%/yr
- QQQ target 60%→100% shares by drawdown · via options: in shares near high (<10%) 50% · 10-30% down 59% · >30% down 76%; positive months 65%, worst 12 months -15.2%; premium 3.0%/yr, 138 puts / 44 calls, assigned 9, called away 5
- QQQ target 60%→100% shares by drawdown · via stock: in shares near high (<10%) 64% · 10-30% down 80% · >30% down 90%; positive months 65%, worst 12 months -26.4%; stock turnover 75%/yr
- MSTR target 15%→100% shares by drawdown · via options: in shares near high (<10%) 50% · 10-30% down 38% · >30% down 59%; positive months 59%, worst 12 months -63.8%; premium 23.1%/yr, 161 puts / 53 calls, assigned 25, called away 12
- MSTR target 15%→100% shares by drawdown · via stock: in shares near high (<10%) 18% · 10-30% down 35% · >30% down 85%; positive months 52%, worst 12 months -73.6%; stock turnover 498%/yr
- MSTR target · deeper schedule (100% only at -88%): in shares near high (<10%) 36% · 10-30% down 32% · >30% down 37%; positive months 56%, worst 12 months -38.9%; premium 18.2%/yr, 145 puts / 79 calls, assigned 21, called away 10
- MSTR target · deeper + trend cap 40% below a falling 200-day: in shares near high (<10%) 36% · 10-30% down 32% · >30% down 27%; positive months 56%, worst 12 months -31.5%; premium 13.3%/yr, 132 puts / 52 calls, assigned 13, called away 7
- MSTR target · deeper + trend cap + core calls at lows: in shares near high (<10%) 34% · 10-30% down 32% · >30% down 25%; positive months 56%, worst 12 months -31.0%; premium 14.8%/yr, 143 puts / 122 calls, assigned 13, called away 7
- QQQ target 60%→100% · trend cap 60% below a falling 200-day: in shares near high (<10%) 49% · 10-30% down 54% · >30% down 63%; positive months 65%, worst 12 months -14.2%; premium 2.6%/yr, 124 puts / 34 calls, assigned 7, called away 3

LEAP / poor man's covered call variants (Deployed = notional exposure; call P&L = premium kept after buybacks, per year as % of equity):

- QQQ PMCC · Tom King rules: in the market 84% of days, call premium 44.3%/yr, call P&L -6.8%/yr, 10 entries; exits: target 0, early 1, stop 4, LEAP at 120 DTE 4
- QQQ PMCC · Tom King rules · weekly IV 0.9x: in the market 84% of days, call premium 43.6%/yr, call P&L -9.9%/yr, 10 entries; exits: target 0, early 0, stop 4, LEAP at 120 DTE 5
- QQQ PMCC · trend calls, no filter/exits: in the market 100% of days, call premium 64.2%/yr, call P&L -10.3%/yr, 9 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 8
- QQQ LEAP · Tom's filter + exits, no calls: in the market 83% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 11 entries; exits: target 0, early 3, stop 4, LEAP at 120 DTE 3
- QQQ LEAP held (rolled at 120 DTE), no calls: in the market 100% of days, call premium 0.0%/yr, call P&L +0.0%/yr, 9 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 8
- QQQ LEAP held · calls only on up-spikes: in the market 100% of days, call premium 1.6%/yr, call P&L +0.8%/yr, 9 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 8
- QQQ shares · Tom's trend calls: in the market 100% of days, call premium 59.4%/yr, call P&L -10.8%/yr, 1 entries; exits: target 0, early 0, stop 0, LEAP at 120 DTE 0

- **QQQ + SPY · spikes** P&L by name (excl. interest): SPY +17k, QQQ +143k
- **Basket · spikes (current rules)** P&L by name (excl. interest): IBIT -4k, GLD +2k, MRVL +2k, SPY +6k, HOOD +15k, SOFI +24k, CEG +28k, FNV +34k, GOOG +48k, TSLA +49k, QQQ +52k, AMZN +58k, MSTR +104k, NVDA +486k
- **Index core 50% + satellites · spikes** P&L by name (excl. interest): IBIT -6k, MRVL +2k, GLD +2k, HOOD +10k, SPY +11k, SOFI +25k, CEG +26k, FNV +33k, TSLA +44k, GOOG +48k, AMZN +57k, QQQ +137k, MSTR +145k, NVDA +488k
- **Basket · always on** P&L by name (excl. interest): GLD +4k, IBIT +4k, SPY +22k, FNV +23k, SOFI +25k, GOOG +31k, QQQ +32k, HOOD +42k, AMZN +60k, TSLA +63k, MRVL +74k, CEG +91k, NVDA +129k, MSTR +243k
- **Basket scale in/out · VIX-scaled cap** P&L by name (excl. interest): IBIT +1k, GLD +8k, SOFI +11k, FNV +12k, GOOG +14k, SPY +21k, QQQ +28k, HOOD +29k, NVDA +29k, AMZN +35k, CEG +56k, TSLA +58k, MRVL +97k, MSTR +275k

## Correlations (monthly returns since 2015-10-01) and 2022 returns

| | QQQ | SPY | GLD | BTC-USD | XLE | TLT | XLP | XLU | XLV | FNV | SLV | IEF | 2022 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QQQ | 1.00 | 0.91 | 0.07 | 0.30 | 0.30 | 0.23 | 0.43 | 0.32 | 0.54 | 0.14 | 0.22 | 0.22 | -33.1% |
| SPY | 0.91 | 1.00 | 0.11 | 0.32 | 0.54 | 0.16 | 0.63 | 0.47 | 0.70 | 0.23 | 0.28 | 0.16 | -19.5% |
| GLD | 0.07 | 0.11 | 1.00 | 0.09 | -0.00 | 0.39 | 0.31 | 0.35 | 0.19 | 0.73 | 0.77 | 0.43 | -0.8% |
| BTC-USD | 0.30 | 0.32 | 0.09 | 1.00 | 0.15 | 0.10 | 0.15 | 0.22 | 0.12 | 0.20 | 0.10 | 0.06 | -64.3% |
| XLE | 0.30 | 0.54 | -0.00 | 0.15 | 1.00 | -0.21 | 0.40 | 0.22 | 0.41 | 0.20 | 0.17 | -0.19 | 57.6% |
| TLT | 0.23 | 0.16 | 0.39 | 0.10 | -0.21 | 1.00 | 0.23 | 0.33 | 0.19 | 0.34 | 0.23 | 0.94 | -32.8% |
| XLP | 0.43 | 0.63 | 0.31 | 0.15 | 0.40 | 0.23 | 1.00 | 0.66 | 0.64 | 0.40 | 0.31 | 0.26 | -3.3% |
| XLU | 0.32 | 0.47 | 0.35 | 0.22 | 0.22 | 0.33 | 0.66 | 1.00 | 0.41 | 0.41 | 0.31 | 0.34 | -1.5% |
| XLV | 0.54 | 0.70 | 0.19 | 0.12 | 0.41 | 0.19 | 0.64 | 0.41 | 1.00 | 0.37 | 0.29 | 0.20 | -3.6% |
| FNV | 0.14 | 0.23 | 0.73 | 0.20 | 0.20 | 0.34 | 0.40 | 0.41 | 0.37 | 1.00 | 0.57 | 0.35 | -1.3% |
| SLV | 0.22 | 0.28 | 0.77 | 0.10 | 0.17 | 0.23 | 0.31 | 0.31 | 0.29 | 0.57 | 1.00 | 0.26 | 2.4% |
| IEF | 0.22 | 0.16 | 0.43 | 0.06 | -0.19 | 0.94 | 0.26 | 0.34 | 0.20 | 0.35 | 0.26 | 1.00 | -16.7% |

## Data

- AMZN: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- BTC-USD: yahoo 2014-09-17 → 2026-10-11 (4408 bars)
- CEG: cboe 2022-02-02 → 2026-10-08 (1176 bars); history before 2022-02-02 dropped (3614-day gap: earlier listing)
- FNV: cboe 2011-09-08 → 2026-10-08 (3795 bars)
- GLD: cboe 2006-01-03 → 2026-10-08 (5226 bars); bars before 2006-01-03 dropped
- GOOG: cboe 2006-01-03 → 2026-10-08 (5224 bars)
- HOOD: cboe 2021-07-29 → 2026-10-08 (1306 bars)
- IBIT: cboe 2024-01-11 → 2026-10-08 (689 bars); bars before 2024-01-11 dropped
- IEF: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- MRVL: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped; 2006-07-25 x2 jump adjusted
- MSTR: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- NVDA: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped; 2006-04-07 x2 jump adjusted
- QQQ: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- SLV: cboe 2006-11-01 → 2026-10-08 (5016 bars); 2008-07-24 x10 jump adjusted
- SOFI: cboe 2020-11-30 → 2026-10-08 (1472 bars)
- SPY: cboe 2006-01-03 → 2026-10-08 (5226 bars); bars before 2006-01-03 dropped
- TLT: cboe 2006-01-03 → 2026-10-08 (5225 bars); bars before 2006-01-03 dropped
- TSLA: cboe 2010-06-29 → 2026-10-08 (4096 bars)
- XLE: cboe 2006-01-03 → 2026-10-08 (5224 bars); 2018-11-22 bad print dropped (65.98); 2025-05-26 bad print dropped (81.99); bars before 2006-01-03 dropped
- XLP: cboe 2006-01-03 → 2026-10-08 (5226 bars); bars before 2006-01-03 dropped
- XLU: cboe 2006-01-03 → 2026-10-08 (5224 bars); 2018-11-22 bad print dropped (54.08); 2025-05-26 bad print dropped (81.06); bars before 2006-01-03 dropped
- XLV: cboe 2006-01-03 → 2026-10-08 (5226 bars); bars before 2006-01-03 dropped
- _GVZ: yahoo+cboe 2008-06-03 → 2026-10-09 (4616 bars)
- _VIX: cboe 1990-01-02 → 2026-10-09 (9291 bars)
- _VXN: yahoo+cboe 2001-01-23 → 2026-10-09 (6469 bars)

## Caveats

- Option prices are Black-Scholes, not market quotes. Index names use VXN/VIX/GVZ × 0.9 as ATM IV with a fixed skew; single stocks use an assumed IV/HV multiple, so their premium (and the basket's edge) is a modelling choice: read the sensitivity rows.
- The basket is today's universe applied to the past (hindsight and survivorship bias in its favour).
- Prices exclude dividends (buy-and-hold is understated by ~0.6%/yr for QQQ, ~1.5% for SPY).
- Earnings IV, early assignment, rolling for credit beyond `max_rolls`, and integer contract sizes are not modelled.
- Trades fill at the signal day's close; the live scanner alerts intraday on delayed quotes.
