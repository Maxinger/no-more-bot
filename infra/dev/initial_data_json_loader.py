"""TEMPORARY: Parse ``tests/initial-data.json`` and seed ``InMemoryTracker``.

Delete this package (``infra/dev/``) and the ``apply_initial_data_fixture`` call in
``bot.py`` once persistence uses a real database.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from application.tracking_service import TrackingService
from domain.model.record import Activity, timestamp_for_activity_day

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INITIAL_DATA_PATH = _REPO_ROOT / "tests" / "initial-data.json"

_JSON_ACTIVITY = {"work": Activity.HOME, "sleep": Activity.BED}

_DAY_INDEX = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def parse_initial_data_document(data: dict) -> tuple[int, list[dict]]:
    """Validate top-level JSON shape; return ``user_id`` and week blocks."""
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
    tracking_service: TrackingService,
    user_id: int,
    block: dict,
) -> None:
    """Apply goals and events from one week object in the fixture."""
    start = date.fromisoformat(block["startDate"])
    for key, hhmm in (block.get("goals") or {}).items():
        if key not in _JSON_ACTIVITY:
            raise ValueError(f"unknown goal activity {key!r}")
        tracking_service.set_goal(
            _JSON_ACTIVITY[key],
            datetime.strptime(str(hhmm).strip(), "%H:%M").time(),
            week_start=start,
        )
    for activity_key, days in (block.get("data") or {}).items():
        if activity_key not in _JSON_ACTIVITY:
            raise ValueError(f"unknown data activity {activity_key!r}")
        activity = _JSON_ACTIVITY[activity_key]
        for day_abbr, hhmm in days.items():
            idx = _DAY_INDEX.get(day_abbr.lower())
            if idx is None:
                raise ValueError(f"unknown weekday {day_abbr!r}")
            day = start + timedelta(days=idx)
            time_value = datetime.strptime(str(hhmm).strip(), "%H:%M").time()
            ts = timestamp_for_activity_day(activity, day, time_value)
            tracking_service.record(user_id, activity, ts)


def apply_initial_data_fixture(
    tracking_service: TrackingService,
    *,
    json_path: Path | None = None,
) -> None:
    path = json_path or DEFAULT_INITIAL_DATA_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    user_id, weeks = parse_initial_data_document(raw)
    for block in weeks:
        apply_parsed_week_block(tracking_service, user_id, block)
