"""Text representation for the current week's activity progress."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from application import LoadWeekProgressCommand, LoadWeekProgressUseCase
from domain import Activity, User, WeekProgress, WeekStart
from representation.formatting_utils import format_date, format_reward, format_time
from representation.icons import HOME_ICON, BED_ICON

CurrentDateTimeProvider = Callable[[], datetime]

ACTIVITIES = (Activity.HOME, Activity.BED)
ACTIVITY_LABELS = {
    Activity.HOME: HOME_ICON,
    Activity.BED: BED_ICON,
}


def current_utc_datetime() -> datetime:
    return datetime.now(timezone.utc)


class CurrentWeekSummaryText:
    """Prepares bot-ready text while application use cases load domain objects."""

    def __init__(
        self,
        load_week_progress: LoadWeekProgressUseCase,
        current_datetime: CurrentDateTimeProvider = current_utc_datetime,
    ):
        self._load_week_progress = load_week_progress
        self._current_datetime = current_datetime

    def summary_for_current_week(self, user: User) -> str:
        current_date = self._current_datetime().astimezone(user.time_zone).date()
        week = WeekStart.from_any_date(current_date)

        lines = [f"Current week ({format_date(week.value)})"]
        for activity in ACTIVITIES:
            progress = self._load_week_progress.handle(
                LoadWeekProgressCommand(
                    user=user,
                    activity=activity,
                    date=current_date,
                )
            ).progress
            lines.append("")
            lines.append(self._format_activity(activity, progress))

        return "\n".join(lines)

    @staticmethod
    def _format_activity(
        activity: Activity, progress: WeekProgress | None
    ) -> str:
        label = ACTIVITY_LABELS[activity]
        if progress is None:
            return f"{label} not set"
        else:
            n = len(progress.records)
            return (
                f"{label} {format_time(progress.goal.target_time)} "
                f"{format_reward(progress.reward())} ({n})"
            )
