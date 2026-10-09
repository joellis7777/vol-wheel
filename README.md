# vol-wheel

Daily options scanner and phone dashboard for a volatility wheel + LEAP strategy.
**Signals only, not financial advice.** No trading, no account data.

- Scanner: `python -m vol_wheel.scan` (CBOE free delayed quotes) → `docs/data/latest.json`
- Schedule: GitHub Actions weekdays at 10:30 and 15:30 ET (intraday) and after the close
  (`.github/workflows/scan.yml`), plus manual runs
- Phone alerts: ntfy push on new SELL PUT / SELL COVERED CALL / LEAP BUY / 10Δ add-on triggers.
  Set the `NTFY_TOPIC` repo secret, subscribe to that topic in the ntfy app, then run the
  "send test alert" workflow
- Dashboard: GitHub Pages from `main` → `/docs`
- Rules: every threshold is in [`config/rules.yaml`](config/rules.yaml)
- IV history accumulates in `data/iv_history/`; IV rank is a realized-vol proxy (VIX/VXN for
  SPY/QQQ) until 60 days are stored, "partial" until 252

See [CLAUDE.md](CLAUDE.md) for how it all works, and [docs/SCHEDULE.md](docs/SCHEDULE.md) to set up
the on-time outside timer (GitHub's own cron runs hours late).

```
pip install -r requirements-dev.txt
python -m pytest -q
```
