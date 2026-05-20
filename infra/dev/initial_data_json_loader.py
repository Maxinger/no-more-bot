"""Parse ``tests/initial-data.json`` into repositories for local bootstrap."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from domain.ports import RecordRepository, WeekGoalRepository
from domain.record import Record, RecordTime, WeekStart
from domain.week_goal import WeekGoal
from infra.initial_data_format import DAY_INDEX, JSON_ACTIVITY

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INITIAL_DATA_PATH = _REPO_ROOT / "tests" / "initial-data.json"


class RepositoryBundle(Protocol):
    records: RecordRepository
    goals: WeekGoalRepository


def parse_initial_data_document(data: dict) -> tuple[int, list[dict]]:
    """Validate the fixture's top-level shape and return user id plus week blocks."""
    if "user_id" not in data or "weeks" not in data:
        raise ValueError("fixture must contain 'user_id' and 'weeks'")
    user_id = data["user_id"]
    if not isinstance(user_id, int):
        raise TypeError("user_id must be int")
    weeks = data["weeks"]
    if not isinstance(weeks, list):
        raise TypeError("weeks must be a list")
    return user_id, weeks


def apply_parsed_week_block(
    records: RecordRepository,
    goals: WeekGoalRepository,
    user_id: int,
    block: dict,
) -> None:
    """Apply goals and records from one fixture week into repositories."""
    week = WeekStart(date.fromisoformat(block["startDate"]))
    for key, hhmm in (block.get("goals") or {}).items():
        if key not in JSON_ACTIVITY:
            raise ValueError(f"unknown goal activity {key!r}")
        goals.save(
            WeekGoal(
                user_id=user_id,
                activity=JSON_ACTIVITY[key],
                week=week,
                target_time=datetime.strptime(str(hhmm).strip(), "%H:%M").time(),
            )
        )

    for activity_key, days in (block.get("data") or {}).items():
        if activity_key not in JSON_ACTIVITY:
            raise ValueError(f"unknown data activity {activity_key!r}")
        activity = JSON_ACTIVITY[activity_key]
        for day_abbr, hhmm in days.items():
            idx = DAY_INDEX.get(day_abbr.lower())
            if idx is None:
                raise ValueError(f"unknown weekday {day_abbr!r}")
            records.save(
                Record(
                    user_id=user_id,
                    activity=activity,
                    time=RecordTime(
                        date=week.value + timedelta(days=idx),
                        time=datetime.strptime(str(hhmm).strip(), "%H:%M").time(),
                    ),
                )
            )


def apply_initial_data_fixture(
    repositories: RepositoryBundle,
    *,
    json_path: Path | None = None,
) -> None:
    path = json_path or DEFAULT_INITIAL_DATA_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    user_id, weeks = parse_initial_data_document(raw)
    for block in weeks:
        apply_parsed_week_block(repositories.records, repositories.goals, user_id, block)
