"""Use case for loading week progress for one activity."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
class LoadCurrentWeekGoalPreviewCommand:
    user: User
    activity: Activity
    date: date


@dataclass(frozen=True)
class LoadCurrentWeekGoalPreviewResult:
    progress: WeekProgress | None
    is_auto: bool


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


@dataclass(frozen=True)
class LoadActivityAvailableWeeksCommand:
    user: User
    activity: Activity


@dataclass(frozen=True)
class LoadActivityAvailableWeeksResult:
    weeks: tuple[WeekStart, ...]


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

    @handles(LoadCurrentWeekGoalPreviewCommand)
    def _load_current_week_goal_preview(
        self, command: LoadCurrentWeekGoalPreviewCommand
    ) -> LoadCurrentWeekGoalPreviewResult:
        week = WeekStart.from_any_date(command.date)
        current_progress = self._load_progress(command.user, command.activity, week)
        if current_progress is not None:
            return LoadCurrentWeekGoalPreviewResult(
                progress=current_progress,
                is_auto=False,
            )

        latest_goal = self._find_latest_goal_before_week(
            command.user, command.activity, week
        )
        if latest_goal is None:
            return LoadCurrentWeekGoalPreviewResult(progress=None, is_auto=False)

        previous_progress = self._load_progress(
            command.user, command.activity, latest_goal.week
        )
        if previous_progress is None:
            return LoadCurrentWeekGoalPreviewResult(progress=None, is_auto=False)

        recommended_goal = previous_progress.next_week_goal()
        records = self._records.find_for_week(command.user.id, command.activity, week)
        return LoadCurrentWeekGoalPreviewResult(
            progress=WeekProgress(
                goal=replace(recommended_goal, week=week),
                records=records,
            ),
            is_auto=True,
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

    @handles(LoadActivityAvailableWeeksCommand)
    def _load_activity_available_weeks(
        self, command: LoadActivityAvailableWeeksCommand
    ) -> LoadActivityAvailableWeeksResult:
        user_id = command.user.id
        activity = command.activity
        week_mondays: set[date] = set()
        for goal in self._goals.find_all_for_user(user_id):
            if goal.activity == activity:
                week_mondays.add(goal.week.value)
        for record in self._records.find_all_for_user(user_id):
            if record.activity == activity:
                week_mondays.add(WeekStart.from_any_date(record.time.date).value)
        weeks = tuple(WeekStart(week_monday) for week_monday in sorted(week_mondays))
        return LoadActivityAvailableWeeksResult(weeks=weeks)

    def _load_progress(
        self, user: User, activity: Activity, week: WeekStart
    ) -> WeekProgress | None:
        goal = self._goals.find(user.id, activity, week)
        if goal is None:
            return None

        records = self._records.find_for_week(user.id, activity, week)
        return WeekProgress(goal=goal, records=records)

    def _find_latest_goal_before_week(
        self, user: User, activity: Activity, week: WeekStart
    ):
        matching_goals = (
            goal
            for goal in self._goals.find_all_for_user(user.id)
            if goal.activity == activity and goal.week.value < week.value
        )
        return max(matching_goals, key=lambda goal: goal.week.value, default=None)
