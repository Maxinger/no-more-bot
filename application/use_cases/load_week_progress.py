"""Use case for loading week progress for one activity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from application.use_case import UseCase, handles
from domain.ports import RecordRepository, WeekGoalRepository
from domain.record import Activity, WeekStart
from domain.user import User
from domain.week_progress import WeekProgress


@dataclass(frozen=True)
class LoadWeekProgressCommand:
    user: User
    activity: Activity
    date: date


@dataclass(frozen=True)
class LoadWeekProgressResult:
    progress: WeekProgress | None


@dataclass(frozen=True)
class WeekProgressInRangeEntry:
    week: WeekStart
    progress: WeekProgress | None


@dataclass(frozen=True)
class LoadWeekProgressInRangeCommand:
    user: User
    activity: Activity
    start_date: date
    end_date: date


@dataclass(frozen=True)
class LoadWeekProgressInRangeResult:
    weeks: tuple[WeekProgressInRangeEntry, ...]


class LoadWeekProgressUseCase(UseCase):
    def __init__(self, goals: WeekGoalRepository, records: RecordRepository):
        self._goals = goals
        self._records = records

    @handles(LoadWeekProgressCommand)
    def _load_week_progress(
        self, command: LoadWeekProgressCommand
    ) -> LoadWeekProgressResult:
        week = WeekStart.from_any_date(command.date)
        return LoadWeekProgressResult(
            progress=self._load_progress(command.user, command.activity, week)
        )

    @handles(LoadWeekProgressInRangeCommand)
    def _load_week_progress_in_range(
        self, command: LoadWeekProgressInRangeCommand
    ) -> LoadWeekProgressInRangeResult:
        start_week = WeekStart.from_any_date(command.start_date)
        end_week = WeekStart.from_any_date(command.end_date)
        if start_week.value > end_week.value:
            raise ValueError("start_date must be before or equal to end_date.")

        entries: list[WeekProgressInRangeEntry] = []
        current_week = start_week
        while current_week.value <= end_week.value:
            entries.append(
                WeekProgressInRangeEntry(
                    week=current_week,
                    progress=self._load_progress(
                        command.user, command.activity, current_week
                    ),
                )
            )
            current_week = WeekStart(current_week.value + timedelta(days=7))

        return LoadWeekProgressInRangeResult(weeks=tuple(entries))

    def _load_progress(
        self, user: User, activity: Activity, week: WeekStart
    ) -> WeekProgress | None:
        goal = self._goals.find(user.id, activity, week)
        if goal is None:
            return None

        records = self._records.find_for_week(user.id, activity, week)
        return WeekProgress(goal=goal, records=records)
