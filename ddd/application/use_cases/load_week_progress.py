"""Use case for loading week progress for one activity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ddd.application.use_case import UseCase, handles
from ddd.domain.ports import RecordRepository, WeekGoalRepository
from ddd.domain.record import Activity, WeekStart
from ddd.domain.week_progress import WeekProgress


@dataclass(frozen=True)
class LoadWeekProgressCommand:
    user_id: int
    activity: Activity
    date: date


@dataclass(frozen=True)
class LoadWeekProgressResult:
    progress: WeekProgress | None


class LoadWeekProgressUseCase(UseCase):
    def __init__(self, goals: WeekGoalRepository, records: RecordRepository):
        self._goals = goals
        self._records = records

    @handles(LoadWeekProgressCommand)
    def _load_week_progress(
        self, command: LoadWeekProgressCommand
    ) -> LoadWeekProgressResult:
        week = WeekStart.from_any_date(command.date)
        goal = self._goals.find(command.user_id, command.activity, week)
        if goal is None:
            return LoadWeekProgressResult(progress=None)

        records = self._records.find_for_week(command.user_id, command.activity, week)
        return LoadWeekProgressResult(progress=WeekProgress(goal=goal, records=records))
