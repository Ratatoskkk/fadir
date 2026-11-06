"""Where a shared refresh must start so an outage leaves no hole in cached history.

The hosted refresh normally asks only for the last few days. When the service was down
for weeks, that left a permanent hole and the history chart fell to zero across it. A
refresh therefore starts from the earliest multi-day hole in the recent cache, if one
exists, or else just before the newest cached day.

Each hole is requested once per process. Yahoo may genuinely have nothing for it (a
trading halt), and re-downloading the same window on every auto-refresh would be waste.
"""

from __future__ import annotations

from datetime import date, timedelta

#: Calendar days between two cached days that weekends and holidays cannot explain.
GAP_DAYS = 7
#: How far back a refresh may reach to repair a hole.
MAX_BACKFILL_DAYS = 400

_requested: set[tuple[str, date]] = set()


def refresh_start(key: str, cached: list[date], today: date, cold_start: date, overlap_days: int) -> date:
    """First day to request for one series, given its cached days in ascending order."""
    if not cached:
        return cold_start
    start = cached[-1] - timedelta(days=overlap_days)
    for before, after in zip(cached, cached[1:]):
        if (after - before).days > GAP_DAYS and (key, before) not in _requested:
            _requested.add((key, before))
            start = min(start, before)
            break
    return max(today - timedelta(days=MAX_BACKFILL_DAYS), start)
