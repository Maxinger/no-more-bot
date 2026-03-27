"""Domain record entity and activity types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Activity(str, Enum):
    HOME = "going_home"
    BED = "going_to_bed"


@dataclass(frozen=True)
class Record:
    user_id: int
    activity: Activity
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
