"""Week progress aggregate: weekly goal plus records and derived progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from ddd.domain.record import Record, WeekStart
from ddd.domain.week_goal import WeekGoal


@dataclass(frozen=True)
class WeekProgressLine:
    date: date
    time: time
    reward: int


@dataclass(frozen=True)
class WeekProgress:
    """Goal for a calendar week plus activity records for that scope.

    ``reward()`` sums per-day contributions: whole minutes of
    ``target_instant - actual_instant``, where sub-minute parts truncate toward
    zero. Positive means the actual time was earlier than the goal that day.
    """

    goal: WeekGoal
    records: tuple[Record, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        week_begin = self.goal.week.value
        week_end = week_begin + timedelta(days=6)
        seen_dates: set[date] = set()
        for record in self.records:
            if record.user_id != self.goal.user_id:
                raise ValueError(
                    "All records must match the goal's user_id "
                    f"(expected {self.goal.user_id}, got {record.user_id})."
                )
            if record.activity != self.goal.activity:
                raise ValueError(
                    "All records must match the goal's activity "
                    f"(expected {self.goal.activity!r}, got {record.activity!r})."
                )
            logical_day = record.time.date
            if logical_day < week_begin or logical_day > week_end:
                raise ValueError(
                    "Each record's logical day must fall within the goal week "
                    f"[{week_begin} .. {week_end}], got {logical_day}."
                )
            if logical_day in seen_dates:
                raise ValueError(f"Duplicate record for logical day {logical_day}.")
            seen_dates.add(logical_day)

    def reward(self) -> int:
        return sum(
            record.time.reward_for_goal(self.goal.target_time)
            for record in self.records
        )

    def report_lines(self) -> tuple[WeekProgressLine, ...]:
        return tuple(
            WeekProgressLine(
                date=record.time.date,
                time=record.time.time,
                reward=record.time.reward_for_goal(self.goal.target_time),
            )
            for record in sorted(self.records, key=lambda r: r.time.date)
        )

    def next_week_goal(self) -> WeekGoal:
        """Suggested goal for the following week based on aggregated ``reward()``."""
        r = self.reward()
        if r > 0:
            delta_minutes = -5
        elif r < 0:
            delta_minutes = 5
        else:
            delta_minutes = 0

        anchor = datetime.combine(date(2000, 1, 1), self.goal.target_time)
        new_target = (anchor + timedelta(minutes=delta_minutes)).time()

        following_monday = self.goal.week.value + timedelta(days=7)
        return WeekGoal(
            user_id=self.goal.user_id,
            activity=self.goal.activity,
            week=WeekStart(following_monday),
            target_time=new_target,
        )

