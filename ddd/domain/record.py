"""Record domain objects for the DDD learning path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from enum import Enum

from ddd.domain.user import DEFAULT_TIME_ZONE


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
    def from_datetime(
        cls, value: datetime, time_zone: tzinfo = DEFAULT_TIME_ZONE
    ) -> "RecordTime":
        if value.tzinfo is None:
            raise ValueError("RecordTime.from_datetime requires an aware datetime.")

        local_value = value.astimezone(time_zone)
        local_time = local_value.timetz().replace(
            second=0, microsecond=0, tzinfo=None
        )
        logical_date = local_value.date()
        if local_time < DAY_START:
            logical_date -= timedelta(days=1)

        return cls(date=logical_date, time=local_time)

    def to_datetime(self, time_zone: tzinfo = DEFAULT_TIME_ZONE) -> datetime:
        actual_date = self.date
        if self.time < DAY_START:
            actual_date += timedelta(days=1)

        local_value = datetime.combine(actual_date, self.time, tzinfo=time_zone)
        return local_value.astimezone(timezone.utc)

    def reward_for_goal(self, target_time: time) -> int:
        """Minutes from ``to_datetime()`` to the goal instant for ``target_time`` (truncated)."""
        actual = self.to_datetime()
        target_instant = RecordTime(self.date, target_time).to_datetime()
        delta = target_instant - actual
        return int(delta.total_seconds() / 60)


@dataclass(frozen=True)
class Record:
    activity: Activity
    user_id: int
    time: RecordTime
