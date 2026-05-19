"""Shared JSON shape for initial-data import and export."""

from __future__ import annotations

import calendar
from collections.abc import Iterable

from domain.record import Activity, Record, WeekStart
from domain.week_goal import WeekGoal

JSON_ACTIVITY = {"work": Activity.HOME, "sleep": Activity.BED}
ACTIVITY_JSON = {activity: key for key, activity in JSON_ACTIVITY.items()}

DAY_INDEX = {abbr.lower(): i for i, abbr in enumerate(calendar.day_abbr)}
INDEX_DAY = {i: abbr.lower() for i, abbr in enumerate(calendar.day_abbr)}


def build_document(
    user_id: int,
    goals: Iterable[WeekGoal],
    records: Iterable[Record],
) -> dict:
    """Build a fixture-shaped document from domain goals and records."""
    goal_list = tuple(goals)
    record_list = tuple(records)

    week_starts: set[WeekStart] = set()
    for goal in goal_list:
        week_starts.add(goal.week)
    for record in record_list:
        week_starts.add(WeekStart.from_any_date(record.time.date))

    sorted_weeks = sorted(week_starts, key=lambda week: week.value)
    weeks_out: list[dict] = []

    for week_number, week in enumerate(sorted_weeks, start=1):
        week_start = week.value
        week_goals = tuple(goal for goal in goal_list if goal.week == week)
        week_records = tuple(
            record
            for record in record_list
            if WeekStart.from_any_date(record.time.date) == week
        )

        block: dict = {
            "week": week_number,
            "startDate": week_start.isoformat(),
        }

        goals_dict: dict[str, str] = {}
        for goal in week_goals:
            goals_dict[ACTIVITY_JSON[goal.activity]] = goal.target_time.strftime("%H:%M")
        if goals_dict:
            block["goals"] = goals_dict

        data_dict: dict[str, dict[str, str]] = {}
        for activity in Activity:
            activity_records = tuple(
                sorted(
                    (record for record in week_records if record.activity == activity),
                    key=lambda record: record.time.date,
                )
            )
            if not activity_records:
                continue
            days_dict: dict[str, str] = {}
            for record in activity_records:
                day_index = (record.time.date - week_start).days
                day_abbr = INDEX_DAY[day_index]
                days_dict[day_abbr] = record.time.time.strftime("%H:%M")
            data_dict[ACTIVITY_JSON[activity]] = days_dict
        if data_dict:
            block["data"] = data_dict

        weeks_out.append(block)

    return {"user_id": user_id, "weeks": weeks_out}
