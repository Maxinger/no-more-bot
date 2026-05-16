import datetime
import unittest

from ddd.domain import Activity, Record, RecordTime, WeekGoal, WeekStart
from ddd.infra import (
    InMemoryRecordRepository,
    InMemoryRepositories,
    InMemoryWeekGoalRepository,
)


class InMemoryRecordRepositoryTest(unittest.TestCase):
    def test_find_returns_record_by_user_activity_and_logical_day(self) -> None:
        repository = InMemoryRecordRepository()
        record = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30)),
        )
        repository.save(record)

        self.assertEqual(
            repository.find(123, Activity.HOME, datetime.date(2026, 5, 8)),
            record,
        )
        self.assertIsNone(repository.find(123, Activity.BED, datetime.date(2026, 5, 8)))
        self.assertIsNone(repository.find(456, Activity.HOME, datetime.date(2026, 5, 8)))

    def test_save_replaces_same_user_activity_and_logical_day(self) -> None:
        repository = InMemoryRecordRepository()
        repository.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 0)),
            )
        )
        replacement = Record(
            user_id=123,
            activity=Activity.BED,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(23, 30)),
        )
        repository.save(replacement)

        self.assertEqual(
            repository.find_for_week(123, Activity.BED, WeekStart(datetime.date(2026, 5, 4))),
            (replacement,),
        )

    def test_find_for_week_filters_scope_and_sorts_by_logical_day(self) -> None:
        repository = InMemoryRecordRepository()
        later = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 7), datetime.time(18, 15)),
        )
        earlier = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 5), datetime.time(17, 50)),
        )
        repository.save(later)
        repository.save(earlier)
        repository.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 11), datetime.time(17, 30)),
            )
        )
        repository.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(23, 0)),
            )
        )

        self.assertEqual(
            repository.find_for_week(123, Activity.HOME, WeekStart(datetime.date(2026, 5, 4))),
            (earlier, later),
        )


class InMemoryWeekGoalRepositoryTest(unittest.TestCase):
    def test_find_returns_goal_by_user_activity_and_week_start(self) -> None:
        repository = InMemoryWeekGoalRepository()
        goal = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(18, 0),
        )
        repository.save(goal)

        self.assertEqual(
            repository.find(123, Activity.HOME, WeekStart(datetime.date(2026, 5, 4))),
            goal,
        )
        self.assertIsNone(
            repository.find(123, Activity.HOME, WeekStart(datetime.date(2026, 5, 11)))
        )
        self.assertIsNone(
            repository.find(456, Activity.HOME, WeekStart(datetime.date(2026, 5, 4)))
        )

    def test_save_replaces_same_user_activity_and_week_start(self) -> None:
        repository = InMemoryWeekGoalRepository()
        week = WeekStart(datetime.date(2026, 5, 4))
        repository.save(
            WeekGoal(
                user_id=123,
                activity=Activity.BED,
                week=week,
                target_time=datetime.time(22, 0),
            )
        )
        replacement = WeekGoal(
            user_id=123,
            activity=Activity.BED,
            week=week,
            target_time=datetime.time(23, 30),
        )
        repository.save(replacement)

        self.assertEqual(repository.find(123, Activity.BED, week), replacement)


class InMemoryRepositoriesTest(unittest.TestCase):
    def test_bundle_creates_record_and_goal_repositories(self) -> None:
        repositories = InMemoryRepositories()

        self.assertIsInstance(repositories.records, InMemoryRecordRepository)
        self.assertIsInstance(repositories.goals, InMemoryWeekGoalRepository)


if __name__ == "__main__":
    unittest.main()
