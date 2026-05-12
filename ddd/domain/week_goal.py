"""Weekly goal value: user activity target for a concrete week."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from ddd.domain.record import Activity, WeekStart


@dataclass(frozen=True)
class WeekGoal:
    user_id: int
    activity: Activity
    week: WeekStart
    target_time: time
