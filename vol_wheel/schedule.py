"""Decide whether a run is the post-close scan, an intraday scan, or should skip.

GitHub cron is UTC-only, so each ET intraday slot has two crons (one for EDT, one for EST).
Both fire every weekday; only the one whose ET time lands in the slot window actually scans.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def resolve_mode(requested: str, schedule: str | None, now_utc: datetime | None, cfg: dict) -> dict:
    """Return {"mode": "close"|"intraday"|"skip", "slot": "10:30"|None, "et": "HH:MM", "reason": str}.

    requested: "close" / "intraday" force a mode (manual runs); "auto" decides from the cron
    string (scheduled runs) or, without one, from the ET clock.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    et = now_utc.astimezone(ZoneInfo(cfg.get("timezone", "America/New_York")))
    et_s = et.strftime("%H:%M")
    mins = et.hour * 60 + et.minute
    slots = cfg.get("intraday_slots", [])

    def nearest_slot():
        before, after = cfg.get("slot_window_before_min", 20), cfg.get("slot_window_after_min", 55)
        for s in slots:
            m = _minutes(_t(s))
            if m - before <= mins < m + after:
                return s
        return None

    if requested == "close":
        return {"mode": "close", "slot": None, "et": et_s, "reason": "forced close"}
    if requested == "intraday":
        return {"mode": "intraday", "slot": nearest_slot(), "et": et_s, "reason": "forced intraday"}

    if schedule:
        if schedule.strip() == cfg.get("close_cron", "").strip():
            return {"mode": "close", "slot": None, "et": et_s, "reason": f"post-close cron {schedule}"}
        if et.weekday() >= 5:
            return {"mode": "skip", "slot": None, "et": et_s, "reason": "weekend"}
        slot = nearest_slot()
        if slot:
            return {"mode": "intraday", "slot": slot, "et": et_s, "reason": f"cron {schedule} = {et_s} ET"}
        return {"mode": "skip", "slot": None, "et": et_s,
                "reason": f"cron {schedule} = {et_s} ET is outside every intraday slot (other DST twin)"}

    # Manual run without a forced mode: intraday during market hours, post-close otherwise.
    open_m, close_m = _minutes(_t(cfg.get("market_open", "09:30"))), _minutes(_t(cfg.get("market_close", "16:00")))
    if et.weekday() < 5 and open_m <= mins < close_m:
        return {"mode": "intraday", "slot": nearest_slot(), "et": et_s, "reason": "manual run during market hours"}
    return {"mode": "close", "slot": None, "et": et_s, "reason": "manual run outside market hours"}
