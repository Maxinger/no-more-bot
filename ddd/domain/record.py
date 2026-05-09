"""Record domain objects for the DDD learning path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum


class Activity(str, Enum):
    HOME = "going_home"
    BED = "going_to_bed"


DAY_START = time(6, 0)


@dataclass(frozen=True)
class WeekStart:
    value: date

    def __post_init__(self) -> None:
        if self.value.weekday() != 0:
            raise ValueError("WeekStart value must be a Monday.")

    @classmethod
    def from_any_date(cls, value: date) -> "WeekStart":
        monday = value - timedelta(days=value.weekday())
        return cls(monday)


@dataclass(frozen=True)
class RecordTime:
    date: date
    time: time

    @classmethod
    def from_datetime(cls, value: datetime) -> "RecordTime":
        logical_date = value.date()
        if value.time() < DAY_START:
            logical_date -= timedelta(days=1)

        return cls(date=logical_date, time=value.time())

    def to_datetime(self) -> datetime:
        actual_date = self.date
        if self.time < DAY_START:
            actual_date += timedelta(days=1)

        return datetime.combine(actual_date, self.time, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Record:
    activity: Activity
    user_id: int
    time: RecordTime
