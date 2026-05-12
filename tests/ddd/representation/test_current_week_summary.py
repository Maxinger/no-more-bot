import datetime
import unittest

from ddd.application import LoadWeekProgressUseCase
from ddd.domain import Activity, Record, RecordTime, WeekGoal, WeekStart
from ddd.representation import CurrentWeekSummaryText


class FakeWeekGoalRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, Activity, datetime.date], WeekGoal] = {}

    def find(self, user_id: int, activity: Activity, week: WeekStart) -> WeekGoal | None:
        return self._by_key.get((user_id, activity, week.value))

    def save(self, goal: WeekGoal) -> None:
        self._by_key[(goal.user_id, goal.activity, goal.week.value)] = goal


class FakeRecordRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, Activity, datetime.date], Record] = {}

    def find(self, user_id: int, activity: Activity, date: datetime.date) -> Record | None:
        return self._by_key.get((user_id, activity, date))

    def find_for_week(
        self, user_id: int, activity: Activity, week: WeekStart
    ) -> tuple[Record, ...]:
        start = week.value
        end = start + datetime.timedelta(days=6)
        return tuple(
            record
            for (record_user_id, record_activity, record_date), record in sorted(
                self._by_key.items(), key=lambda item: item[0][2]
            )
            if record_user_id == user_id
            and record_activity == activity
            and start <= record_date <= end
        )

    def save(self, record: Record) -> None:
        self._by_key[(record.user_id, record.activity, record.time.date)] = record


class CurrentWeekSummaryTextTest(unittest.TestCase):
    def test_summary_loads_current_week_progress_for_home_and_bed(self) -> None:
        goals = FakeWeekGoalRepository()
        records = FakeRecordRepository()
        summary = CurrentWeekSummaryText(
            LoadWeekProgressUseCase(goals, records),
            current_date=lambda: datetime.date(2026, 5, 7),
        )
        week = WeekStart(datetime.date(2026, 5, 4))
        goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=week,
                target_time=datetime.time(18, 0),
            )
        )
        goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.BED,
                week=week,
                target_time=datetime.time(22, 30),
            )
        )
        records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 5), datetime.time(17, 50)),
            )
        )
        records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 7), datetime.time(18, 15)),
            )
        )
        records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 11), datetime.time(17, 30)),
            )
        )

        text = summary.summary_for_current_week(user_id=123)

        self.assertEqual(
            text,
            "\n".join(
                [
                    "Current week (04.05.2026)",
                    "🏠 18:00 -5 / 2",
                    "",
                    "🛏️ 22:30 =0 / 0",
                ]
            ),
        )

    def test_summary_marks_missing_goal_as_not_available(self) -> None:
        goals = FakeWeekGoalRepository()
        records = FakeRecordRepository()
        summary = CurrentWeekSummaryText(
            LoadWeekProgressUseCase(goals, records),
            current_date=lambda: datetime.date(2026, 5, 7),
        )
        goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(datetime.date(2026, 5, 4)),
                target_time=datetime.time(18, 0),
            )
        )

        text = summary.summary_for_current_week(user_id=123)

        self.assertEqual(
            text,
            "\n".join(
                [
                    "Current week (04.05.2026)",
                    "🏠 18:00 =0 / 0",
                    "",
                    "🛏️ not set",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
