# vol-wheel

Daily options scanner and phone dashboard for a volatility wheel + LEAP strategy.
**Signals only, not financial advice.** No trading, no account data.

- Scanner: `python -m vol_wheel.scan` (CBOE free delayed quotes) → `docs/data/latest.json`
- Schedule: GitHub Actions, weekdays 21:35 UTC (`.github/workflows/scan.yml`), plus manual runs
- Dashboard: GitHub Pages from `main` → `/docs`
- Rules: every threshold is in [`config/rules.yaml`](config/rules.yaml)
- IV history accumulates in `data/iv_history/`; IV rank is a realized-vol proxy (VIX/VXN for
  SPY/QQQ) until 60 days are stored, "partial" until 252

See [CLAUDE.md](CLAUDE.md) for how it all works.

```
pip install -r requirements-dev.txt
python -m pytest -q
```
