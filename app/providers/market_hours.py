"""Market-hours awareness (SPEC §8).

The four exchanges span roughly UTC+0 to UTC+8. Outside a given exchange's session its
symbols are polled slowly and the position is marked "closed - last traded {date}" rather
than implying a live price: a Taipei close must never be presented as live at 20:00
Istanbul time.

Public holidays are not modelled — a holiday simply looks like a day with no new close,
which the staleness check below already catches via `last_traded`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from functools import cached_property
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ExchangeHours:
    code: str
    tz: str
    open_time: time
    close_time: time

    @cached_property
    def zone(self) -> ZoneInfo:
        """Resolved once per exchange. `is_open` runs per position per request, and
        `next_open_for` loops over a week of candidate days."""
        return ZoneInfo(self.tz)

    def is_open(self, now_utc: datetime) -> bool:
        local = now_utc.astimezone(self.zone)
        if local.weekday() >= 5:  # Saturday / Sunday
            return False
        return self.open_time <= local.time() <= self.close_time

    def local_now(self, now_utc: datetime) -> datetime:
        return now_utc.astimezone(self.zone)


EXCHANGES: dict[str, ExchangeHours] = {
    "STO": ExchangeHours("STO", "Europe/Stockholm", time(9, 0), time(17, 30)),
    "ETR": ExchangeHours("ETR", "Europe/Berlin", time(9, 0), time(17, 30)),
    "TPE": ExchangeHours("TPE", "Asia/Taipei", time(9, 0), time(13, 30)),
    "NYSE": ExchangeHours("NYSE", "America/New_York", time(9, 30), time(16, 0)),
    "NASDAQ": ExchangeHours("NASDAQ", "America/New_York", time(9, 30), time(16, 0)),
}


def is_open(exchange: str, now_utc: datetime) -> bool:
    hours = EXCHANGES.get(exchange.upper())
    if hours is None:
        return False  # unknown exchange: assume closed rather than imply a live price
    return hours.is_open(now_utc)


def session_state(exchange: str, now_utc: datetime) -> str:
    return "open" if is_open(exchange, now_utc) else "closed"


def next_open_for(exchange: str, now_utc: datetime) -> datetime | None:
    """When this exchange next opens, in UTC. None if the code is unknown.

    Walks forward a day at a time over the next week, which covers weekends and the
    wrap from "already closed today" to tomorrow's session. Public holidays are not
    modelled, so a holiday simply means the first poll after waking finds no new close —
    harmless, since the position stays flagged with its true `last_traded` date.
    """
    hours = EXCHANGES.get(exchange.upper())
    if hours is None:
        return None

    tz = hours.zone
    local_now = now_utc.astimezone(tz)

    for offset in range(0, 8):
        candidate_day = (local_now + timedelta(days=offset)).date()
        if candidate_day.weekday() >= 5:
            continue
        candidate = datetime.combine(candidate_day, hours.open_time, tzinfo=tz)
        if candidate > local_now:
            return candidate.astimezone(timezone.utc)

    return None


def next_open(exchanges: Iterable[str], now_utc: datetime) -> datetime | None:
    """Earliest next open across several exchanges — the moment polling should resume."""
    candidates = [
        opening
        for opening in (next_open_for(e, now_utc) for e in exchanges)
        if opening is not None
    ]
    return min(candidates) if candidates else None
