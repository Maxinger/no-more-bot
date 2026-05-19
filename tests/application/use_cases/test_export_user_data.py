import datetime
import unittest

from application.use_cases.export_user_data import (
    ExportUserDataCommand,
    ExportUserDataUseCase,
)
from domain import Activity, Record, RecordTime, WeekGoal, WeekStart
from domain.user import User
from infra import InMemoryRecordRepository, InMemoryWeekGoalRepository


class ExportUserDataUseCaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.records = InMemoryRecordRepository()
        self.goals = InMemoryWeekGoalRepository()
        self.use_case = ExportUserDataUseCase(self.goals, self.records)
        self.user = User(123)

    def test_empty_export_returns_no_weeks(self) -> None:
        result = self.use_case.handle(ExportUserDataCommand(user=self.user))

        self.assertEqual(result.user_id, 123)
        self.assertEqual(result.weeks, ())

    def test_groups_goals_and_records_by_week(self) -> None:
        week_one = WeekStart(datetime.date(2026, 4, 6))
        week_two = WeekStart(datetime.date(2026, 4, 13))
        self.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=week_one,
                target_time=datetime.time(20, 10),
            )
        )
        self.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.BED,
                week=week_two,
                target_time=datetime.time(23, 55),
            )
        )
        self.records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 4, 7), datetime.time(20, 42)),
            )
        )
        self.records.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 4, 14), datetime.time(23, 50)),
            )
        )

        result = self.use_case.handle(ExportUserDataCommand(user=self.user))

        self.assertEqual(len(result.weeks), 2)
        self.assertEqual(result.weeks[0].week_start, week_one)
        self.assertEqual(len(result.weeks[0].goals), 1)
        self.assertEqual(len(result.weeks[0].records), 1)
        self.assertEqual(result.weeks[1].week_start, week_two)
        self.assertEqual(len(result.weeks[1].goals), 1)
        self.assertEqual(len(result.weeks[1].records), 1)

    def test_includes_week_with_only_goals_or_only_records(self) -> None:
        goal_only_week = WeekStart(datetime.date(2026, 5, 4))
        record_only_week = WeekStart(datetime.date(2026, 5, 11))
        self.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=goal_only_week,
                target_time=datetime.time(20, 0),
            )
        )
        self.records.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 12), datetime.time(23, 30)),
            )
        )

        result = self.use_case.handle(ExportUserDataCommand(user=self.user))

        self.assertEqual([week.week_start for week in result.weeks], [goal_only_week, record_only_week])
        self.assertEqual(result.weeks[0].records, ())
        self.assertEqual(result.weeks[1].goals, ())

    def test_ignores_other_users_data(self) -> None:
        week = WeekStart(datetime.date(2026, 4, 6))
        self.goals.save(
            WeekGoal(
                user_id=456,
                activity=Activity.HOME,
                week=week,
                target_time=datetime.time(20, 10),
            )
        )
        self.records.save(
            Record(
                user_id=456,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
            )
        )

        result = self.use_case.handle(ExportUserDataCommand(user=self.user))

        self.assertEqual(result.weeks, ())


if __name__ == "__main__":
    unittest.main()
