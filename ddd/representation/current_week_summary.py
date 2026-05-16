"""Text representation for the current week's activity progress."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone

from ddd.application import LoadWeekProgressCommand, LoadWeekProgressUseCase
from ddd.domain import Activity, WeekProgress, WeekStart
from ddd.representation.formatting_utils import format_date, format_reward, format_time

CurrentDateProvider = Callable[[], date]

HOME_ICON = "🏠"
BED_ICON = "🛏️"

ACTIVITIES = (Activity.HOME, Activity.BED)
ACTIVITY_LABELS = {
    Activity.HOME: HOME_ICON,
    Activity.BED: BED_ICON,
}

def current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


class CurrentWeekSummaryText:
    """Prepares bot-ready text while application use cases load domain objects."""

    def __init__(
        self,
        load_week_progress: LoadWeekProgressUseCase,
        current_date: CurrentDateProvider = current_utc_date,
    ):
        self._load_week_progress = load_week_progress
        self._current_date = current_date

    def summary_for_current_week(self, user_id: int) -> str:
        current_date = self._current_date()
        week = WeekStart.from_any_date(current_date)

        lines = [f"Current week ({format_date(week.value)})"]
        for activity in ACTIVITIES:
            progress = self._load_week_progress.handle(
                LoadWeekProgressCommand(
                    user_id=user_id,
                    activity=activity,
                    date=current_date,
                )
            ).progress
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
            return f"{label} {format_time(progress.goal.target_time)} {format_reward(progress.reward())} / {len(progress.records)}"
