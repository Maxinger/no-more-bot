import datetime
import unittest

from ddd.application import (
    LoadWeekProgressCommand,
    LoadWeekProgressResult,
    LoadWeekProgressUseCase,
)
from ddd.domain import Activity, Record, RecordTime, WeekGoal, WeekProgress, WeekStart


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


class LoadWeekProgressUseCaseTest(unittest.TestCase):
    def test_loads_goal_and_records_for_week_containing_date(self) -> None:
        goals = FakeWeekGoalRepository()
        records = FakeRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        week = WeekStart(datetime.date(2026, 5, 4))
        goal = WeekGoal(
            user_id=123,
            activity=Activity.BED,
            week=week,
            target_time=datetime.time(22, 30),
        )
        included = Record(
            user_id=123,
            activity=Activity.BED,
            time=RecordTime(datetime.date(2026, 5, 6), datetime.time(22, 0)),
        )
        goals.save(goal)
        records.save(included)
        records.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 11), datetime.time(22, 0)),
            )
        )

        result = use_case.handle(
            LoadWeekProgressCommand(
                user_id=123,
                activity=Activity.BED,
                date=datetime.date(2026, 5, 7),
            )
        )

        self.assertEqual(
            result,
            LoadWeekProgressResult(
                progress=WeekProgress(goal=goal, records=(included,)),
            ),
        )

    def test_existing_goal_without_records_returns_empty_progress(self) -> None:
        goals = FakeWeekGoalRepository()
        records = FakeRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        goal = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(18, 0),
        )
        goals.save(goal)

        result = use_case.handle(
            LoadWeekProgressCommand(
                user_id=123,
                activity=Activity.HOME,
                date=datetime.date(2026, 5, 4),
            )
        )

        self.assertEqual(
            result,
            LoadWeekProgressResult(progress=WeekProgress(goal=goal, records=())),
        )

    def test_missing_goal_returns_none(self) -> None:
        use_case = LoadWeekProgressUseCase(
            FakeWeekGoalRepository(),
            FakeRecordRepository(),
        )

        result = use_case.handle(
            LoadWeekProgressCommand(
                user_id=123,
                activity=Activity.HOME,
                date=datetime.date(2026, 5, 4),
            )
        )

        self.assertEqual(result, LoadWeekProgressResult(progress=None))

    def test_unsupported_command_is_rejected(self) -> None:
        use_case = LoadWeekProgressUseCase(
            FakeWeekGoalRepository(),
            FakeRecordRepository(),
        )

        with self.assertRaises(TypeError):
            use_case.handle(object())


if __name__ == "__main__":
    unittest.main()
