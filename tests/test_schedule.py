from datetime import datetime, timezone

import pytest

from vol_wheel.schedule import resolve_mode

CRONS = {"close": "35 21 * * 1-5", "1030_edt": "30 14 * * 1-5", "1030_est": "30 15 * * 1-5",
         "1530_edt": "30 19 * * 1-5", "1530_est": "30 20 * * 1-5"}


@pytest.fixture
def cfg(rules):
    return rules["schedule"]


def utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


# 2026-10-05 is a Monday in EDT (UTC-4); 2026-12-07 is a Monday in EST (UTC-5).
@pytest.mark.parametrize("cron,now,mode,slot", [
    ("1030_edt", utc(2026, 10, 5, 14, 30), "intraday", "10:30"),
    ("1030_est", utc(2026, 10, 5, 15, 30), "skip", None),       # 11:30 EDT: the EST twin
    ("1530_edt", utc(2026, 10, 5, 19, 30), "intraday", "15:30"),
    ("1530_est", utc(2026, 10, 5, 20, 30), "skip", None),       # 16:30 EDT
    ("1030_edt", utc(2026, 12, 7, 14, 30), "skip", None),       # 09:30 EST
    ("1030_est", utc(2026, 12, 7, 15, 30), "intraday", "10:30"),
    ("1530_edt", utc(2026, 12, 7, 19, 30), "skip", None),       # 14:30 EST
    ("1530_est", utc(2026, 12, 7, 20, 30), "intraday", "15:30"),
    ("close", utc(2026, 10, 5, 21, 35), "close", None),
    ("close", utc(2026, 12, 7, 21, 35), "close", None),
])
def test_dst_twins(cfg, cron, now, mode, slot):
    r = resolve_mode("auto", CRONS[cron], now, cfg)
    assert (r["mode"], r["slot"]) == (mode, slot), r


def test_late_cron_still_counts(cfg):
    # GitHub started the 10:30 EDT cron 40 minutes late
    assert resolve_mode("auto", CRONS["1030_edt"], utc(2026, 10, 5, 15, 10), cfg)["mode"] == "intraday"


def test_manual_runs(cfg):
    assert resolve_mode("auto", None, utc(2026, 10, 5, 17, 0), cfg)["mode"] == "intraday"   # 13:00 EDT
    assert resolve_mode("auto", None, utc(2026, 10, 5, 22, 0), cfg)["mode"] == "close"      # 18:00 EDT
    assert resolve_mode("auto", None, utc(2026, 10, 3, 16, 0), cfg)["mode"] == "close"      # Saturday
    assert resolve_mode("intraday", None, utc(2026, 10, 3, 16, 0), cfg)["mode"] == "intraday"
    assert resolve_mode("close", CRONS["1030_edt"], utc(2026, 10, 5, 14, 30), cfg)["mode"] == "close"
