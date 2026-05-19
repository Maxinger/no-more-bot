"""Use case for exporting all persisted goals and records for a user."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from application.use_case import UseCase, handles
from domain.ports import RecordRepository, WeekGoalRepository
from domain.record import Record, WeekStart
from domain.user import User
from domain.week_goal import WeekGoal


@dataclass(frozen=True)
class ExportUserDataCommand:
    user: User


@dataclass(frozen=True)
class ExportedWeek:
    week_start: WeekStart
    goals: tuple[WeekGoal, ...]
    records: tuple[Record, ...]


@dataclass(frozen=True)
class ExportUserDataResult:
    user_id: int
    weeks: tuple[ExportedWeek, ...]


class ExportUserDataUseCase(UseCase):
    def __init__(self, goals: WeekGoalRepository, records: RecordRepository):
        self._goals = goals
        self._records = records

    @handles(ExportUserDataCommand)
    def _export_user_data(self, command: ExportUserDataCommand) -> ExportUserDataResult:
        user_id = command.user.id
        goals_by_week: dict[date, list[WeekGoal]] = defaultdict(list)
        for goal in self._goals.find_all_for_user(user_id):
            goals_by_week[goal.week.value].append(goal)

        records_by_week: dict[date, list[Record]] = defaultdict(list)
        for record in self._records.find_all_for_user(user_id):
            week_monday = WeekStart.from_any_date(record.time.date).value
            records_by_week[week_monday].append(record)

        all_weeks = sorted(set(goals_by_week) | set(records_by_week))
        weeks = tuple(
            ExportedWeek(
                week_start=WeekStart(week_monday),
                goals=tuple(goals_by_week.get(week_monday, [])),
                records=tuple(records_by_week.get(week_monday, [])),
            )
            for week_monday in all_weeks
        )
        return ExportUserDataResult(user_id=user_id, weeks=weeks)
