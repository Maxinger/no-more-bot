"""Domain record entity and activity types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum


class Activity(str, Enum):
    HOME = "going_home"
    BED = "going_to_bed"


BED_PREVIOUS_DAY_CUTOFF = time(6, 0)


def activity_day(activity: Activity, timestamp: datetime) -> date:
    """Logical day for reporting an activity."""
    if activity == Activity.BED and timestamp.time() < BED_PREVIOUS_DAY_CUTOFF:
        return timestamp.date() - timedelta(days=1)
    return timestamp.date()


def timestamp_for_activity_day(activity: Activity, day: date, time_value: time) -> datetime:
    """Build an actual UTC timestamp from the user's logical activity day."""
    actual_day = day
    if activity == Activity.BED and time_value < BED_PREVIOUS_DAY_CUTOFF:
        actual_day = day + timedelta(days=1)
    return datetime.combine(actual_day, time_value, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Record:
    user_id: int
    activity: Activity
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
