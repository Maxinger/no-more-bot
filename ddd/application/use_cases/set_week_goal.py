"""Use case for setting a weekly time goal for an activity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from ddd.application.use_case import UseCase, handles
from ddd.domain.ports import WeekGoalRepository
from ddd.domain.record import Activity, WeekStart
from ddd.domain.week_goal import WeekGoal


@dataclass(frozen=True)
class SetWeekGoalCommand:
    user_id: int
    activity: Activity
    week: WeekStart
    target_time: time


@dataclass(frozen=True)
class SetWeekGoalResult:
    goal: WeekGoal
    replaced_existing: bool


class SetWeekGoalUseCase(UseCase):
    def __init__(self, goals: WeekGoalRepository):
        self._goals = goals

    @handles(SetWeekGoalCommand)
    def _set_week_goal(self, command: SetWeekGoalCommand) -> SetWeekGoalResult:
        replaced_existing = (
            self._goals.find(command.user_id, command.activity, command.week) is not None
        )
        goal = WeekGoal(
            user_id=command.user_id,
            activity=command.activity,
            week=command.week,
            target_time=command.target_time,
        )
        self._goals.save(goal)
        return SetWeekGoalResult(goal=goal, replaced_existing=replaced_existing)
