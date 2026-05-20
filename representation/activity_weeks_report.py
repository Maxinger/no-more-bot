"""Text representation for one activity across multiple weeks."""

from __future__ import annotations

from datetime import date, timedelta

from application import (
    LoadActivityAvailableWeeksCommand,
    LoadWeekProgressCommand,
    LoadWeekProgressInRangeCommand,
    LoadWeekProgressUseCase,
)
from domain import Activity, User, WeekProgress, WeekStart
from representation.current_week_summary import ACTIVITY_LABELS
from representation.formatting_utils import format_date, format_reward, format_time


class ActivityWeeksReportText:
    """Prepares compact multi-week progress text for one activity."""

    def __init__(self, load_week_progress: LoadWeekProgressUseCase):
        self._load_week_progress = load_week_progress

    def report_for_activity(
        self,
        user: User,
        activity: Activity,
        date: date,
        weeks_count: int = 3,
    ) -> str:
        if weeks_count < 1:
            raise ValueError("weeks_count must be positive.")

        end_week = WeekStart.from_any_date(date)
        start_date = end_week.value - timedelta(days=7 * (weeks_count - 1))
        result = self._load_week_progress.handle(
            LoadWeekProgressInRangeCommand(
                user=user,
                activity=activity,
                start_date=start_date,
                end_date=end_week.value,
            )
        )

        return self._format_week_entries(
            ACTIVITY_LABELS[activity],
            [(entry.week, entry.progress) for entry in result.weeks],
        )

    def report_for_all_weeks(
        self,
        user: User,
        activity: Activity,
        date: date,
    ) -> str:
        label = ACTIVITY_LABELS[activity]
        available = self._load_week_progress.handle(
            LoadActivityAvailableWeeksCommand(user=user, activity=activity)
        )
        if not available.weeks:
            return f"No {label} weeks yet."

        entries = []
        for week in available.weeks:
            progress = self._load_week_progress.handle(
                LoadWeekProgressCommand(
                    user=user,
                    activity=activity,
                    date=week.value,
                )
            ).progress
            entries.append((week, progress))
        return self._format_week_entries(label, entries)

    def _format_week_entries(
        self,
        label: str,
        entries: list[tuple[WeekStart, WeekProgress | None]],
    ) -> str:
        lines: list[str] = []
        for week, progress in entries:
            lines.append(format_date(week.value))
            lines.append(self._format_progress(label, progress))
        return "\n".join(lines)

    @staticmethod
    def _format_progress(label: str, progress: WeekProgress | None) -> str:
        if progress is None:
            return f"{label} not set"

        return (
            f"{label} {format_time(progress.goal.target_time)} "
            f"{format_reward(progress.reward())} ({len(progress.records)})"
        )
