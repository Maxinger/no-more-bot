"""User identity plus preferences needed by domain decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError


def _minsk_time_zone() -> tzinfo:
    try:
        return ZoneInfo("Europe/Minsk")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=3), "Europe/Minsk")


DEFAULT_TIME_ZONE = _minsk_time_zone()


@dataclass(frozen=True)
class User:
    id: int
    time_zone: tzinfo = field(default=DEFAULT_TIME_ZONE)
