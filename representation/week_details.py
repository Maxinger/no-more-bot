"""Text representation for one activity's weekly details."""

from __future__ import annotations

from datetime import date

from application import LoadWeekProgressCommand, LoadWeekProgressUseCase
from domain import Activity, User, WeekProgress, WeekStart
from representation.current_week_summary import ACTIVITY_LABELS
from representation.formatting_utils import (
    SEPARATOR,
    format_date,
    format_reward,
    format_time,
)


class WeekDetailsText:
    """Prepares detailed week progress text for one activity."""

    def __init__(self, load_week_progress: LoadWeekProgressUseCase):
        self._load_week_progress = load_week_progress

    def details_for_week(
        self,
        user: User,
        activity: Activity,
        date: date,
        auto_progress: WeekProgress | None = None,
    ) -> str:
        week = WeekStart.from_any_date(date)
        progress = self._load_week_progress.handle(
            LoadWeekProgressCommand(
                user=user,
                activity=activity,
                date=date,
            )
        ).progress
        is_auto = False
        if progress is None and auto_progress is not None:
            progress = auto_progress
            is_auto = True

        label = ACTIVITY_LABELS[activity]
        lines = [f"{label} Week progress ({format_date(week.value)})", ""]
        if progress is None:
            lines.extend(["Goal: not set", SEPARATOR])
            return "\n".join(lines)

        lines.extend(self._format_progress(progress, is_auto=is_auto))
        return "\n".join(lines)

    @staticmethod
    def _format_progress(progress: WeekProgress, *, is_auto: bool = False) -> list[str]:
        auto_marker = " (auto)" if is_auto else ""
        lines = [
            f"Goal: {format_time(progress.goal.target_time)}{auto_marker} {format_reward(progress.reward())}",
            SEPARATOR,
        ]
        for report_line in progress.report_lines():
            lines.append(
                f"{report_line.date.strftime('%a')}: "
                f"{format_time(report_line.time)} {format_reward(report_line.reward, '👍👍❌')}"
            )
            lines.append("")
        return lines
