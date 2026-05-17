import datetime
import unittest

from ddd.application import (
    LoadWeekProgressCommand,
    LoadWeekProgressResult,
    LoadWeekProgressUseCase,
)
from ddd.domain import Activity, Record, RecordTime, User, WeekGoal, WeekProgress, WeekStart
from ddd.infra import InMemoryRecordRepository, InMemoryWeekGoalRepository


class LoadWeekProgressUseCaseTest(unittest.TestCase):
    def test_loads_goal_and_records_for_week_containing_date(self) -> None:
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
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
                user=User(123),
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
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
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
                user=User(123),
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
            InMemoryWeekGoalRepository(),
            InMemoryRecordRepository(),
        )

        result = use_case.handle(
            LoadWeekProgressCommand(
                user=User(123),
                activity=Activity.HOME,
                date=datetime.date(2026, 5, 4),
            )
        )

        self.assertEqual(result, LoadWeekProgressResult(progress=None))

    def test_unsupported_command_is_rejected(self) -> None:
        use_case = LoadWeekProgressUseCase(
            InMemoryWeekGoalRepository(),
            InMemoryRecordRepository(),
        )

        with self.assertRaises(TypeError):
            use_case.handle(object())


if __name__ == "__main__":
    unittest.main()
