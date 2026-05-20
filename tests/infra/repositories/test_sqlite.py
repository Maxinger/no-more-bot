import datetime
import tempfile
import unittest
from pathlib import Path

from domain import Activity, Record, RecordTime, WeekGoal, WeekStart
from infra import (
    SQLiteDatabase,
    SQLiteRecordRepository,
    SQLiteRepositories,
    SQLiteWeekGoalRepository,
)


class SQLiteRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "bot.sqlite3"
        self.repositories = SQLiteRepositories(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()


class SQLiteRecordRepositoryTest(SQLiteRepositoryTestCase):
    def test_find_returns_record_by_user_activity_and_logical_day(self) -> None:
        record = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30)),
        )
        self.repositories.records.save(record)

        self.assertEqual(
            self.repositories.records.find(123, Activity.HOME, datetime.date(2026, 5, 8)),
            record,
        )
        self.assertIsNone(
            self.repositories.records.find(123, Activity.BED, datetime.date(2026, 5, 8))
        )
        self.assertIsNone(
            self.repositories.records.find(456, Activity.HOME, datetime.date(2026, 5, 8))
        )

    def test_save_replaces_same_user_activity_and_logical_day(self) -> None:
        self.repositories.records.save(
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
        self.repositories.records.save(replacement)

        self.assertEqual(
            self.repositories.records.find_for_week(
                123, Activity.BED, WeekStart(datetime.date(2026, 5, 4))
            ),
            (replacement,),
        )

    def test_find_for_week_filters_scope_and_sorts_by_logical_day(self) -> None:
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
        self.repositories.records.save(later)
        self.repositories.records.save(earlier)
        self.repositories.records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 11), datetime.time(17, 30)),
            )
        )
        self.repositories.records.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(23, 0)),
            )
        )

        self.assertEqual(
            self.repositories.records.find_for_week(
                123, Activity.HOME, WeekStart(datetime.date(2026, 5, 4))
            ),
            (earlier, later),
        )

    def test_find_all_for_user_filters_scope_and_sorts_by_date_then_activity(self) -> None:
        other_user = Record(
            user_id=456,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 5), datetime.time(19, 0)),
        )
        bed = Record(
            user_id=123,
            activity=Activity.BED,
            time=RecordTime(datetime.date(2026, 5, 5), datetime.time(23, 0)),
        )
        home = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 5), datetime.time(18, 0)),
        )
        later = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 6), datetime.time(18, 30)),
        )
        self.repositories.records.save(later)
        self.repositories.records.save(other_user)
        self.repositories.records.save(bed)
        self.repositories.records.save(home)

        self.assertEqual(
            self.repositories.records.find_all_for_user(123),
            (home, bed, later),
        )


class SQLiteWeekGoalRepositoryTest(SQLiteRepositoryTestCase):
    def test_find_returns_goal_by_user_activity_and_week_start(self) -> None:
        goal = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(18, 0),
        )
        self.repositories.goals.save(goal)

        self.assertEqual(
            self.repositories.goals.find(
                123, Activity.HOME, WeekStart(datetime.date(2026, 5, 4))
            ),
            goal,
        )
        self.assertIsNone(
            self.repositories.goals.find(
                123, Activity.HOME, WeekStart(datetime.date(2026, 5, 11))
            )
        )
        self.assertIsNone(
            self.repositories.goals.find(
                456, Activity.HOME, WeekStart(datetime.date(2026, 5, 4))
            )
        )

    def test_save_replaces_same_user_activity_and_week_start(self) -> None:
        week = WeekStart(datetime.date(2026, 5, 4))
        self.repositories.goals.save(
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
        self.repositories.goals.save(replacement)

        self.assertEqual(self.repositories.goals.find(123, Activity.BED, week), replacement)

    def test_find_all_for_user_filters_scope_and_sorts_by_week_then_activity(self) -> None:
        later = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 11)),
            target_time=datetime.time(18, 30),
        )
        bed = WeekGoal(
            user_id=123,
            activity=Activity.BED,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(23, 0),
        )
        home = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(18, 0),
        )
        other_user = WeekGoal(
            user_id=456,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(17, 0),
        )
        self.repositories.goals.save(later)
        self.repositories.goals.save(other_user)
        self.repositories.goals.save(bed)
        self.repositories.goals.save(home)

        self.assertEqual(
            self.repositories.goals.find_all_for_user(123),
            (home, bed, later),
        )


class SQLiteRepositoriesTest(unittest.TestCase):
    def test_bundle_creates_database_and_repository_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "bot.sqlite3"

            repositories = SQLiteRepositories(path)

            self.assertTrue(path.exists())
            self.assertIsInstance(repositories.database, SQLiteDatabase)
            self.assertIsInstance(repositories.records, SQLiteRecordRepository)
            self.assertIsInstance(repositories.goals, SQLiteWeekGoalRepository)
            self.assertTrue(repositories.database.main_tables_are_empty())


if __name__ == "__main__":
    unittest.main()
