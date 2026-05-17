import datetime
import tempfile
import unittest
from pathlib import Path

from domain import Activity, RecordTime, WeekStart
from infra import InMemoryRecordRepository, InMemoryRepositories, InMemoryWeekGoalRepository
from infra.dev.initial_data_json_loader import (
    apply_initial_data_fixture,
    apply_parsed_week_block,
    parse_initial_data_document,
)


class InitialDataJsonLoaderTest(unittest.TestCase):
    def test_parse_initial_data_document_returns_user_id_and_weeks(self) -> None:
        user_id, weeks = parse_initial_data_document(
            {
                "user_id": 123,
                "weeks": [{"startDate": "2026-04-06"}],
            }
        )

        self.assertEqual(user_id, 123)
        self.assertEqual(weeks, [{"startDate": "2026-04-06"}])

    def test_apply_week_block_loads_goals_and_records(self) -> None:
        records = InMemoryRecordRepository()
        goals = InMemoryWeekGoalRepository()

        apply_parsed_week_block(
            records,
            goals,
            123,
            {
                "startDate": "2026-04-06",
                "goals": {
                    "work": "20:10",
                    "sleep": "23:55",
                },
                "data": {
                    "work": {"mon": "20:42"},
                    "sleep": {"tue": "23:50"},
                },
            },
        )

        week = WeekStart(datetime.date(2026, 4, 6))
        self.assertEqual(
            goals.find(123, Activity.HOME, week).target_time,
            datetime.time(20, 10),
        )
        self.assertEqual(
            goals.find(123, Activity.BED, week).target_time,
            datetime.time(23, 55),
        )
        self.assertEqual(
            records.find(123, Activity.HOME, datetime.date(2026, 4, 6)).time,
            RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
        )
        self.assertEqual(
            records.find(123, Activity.BED, datetime.date(2026, 4, 7)).time,
            RecordTime(datetime.date(2026, 4, 7), datetime.time(23, 50)),
        )

    def test_sleep_after_midnight_is_loaded_as_logical_fixture_day(self) -> None:
        records = InMemoryRecordRepository()
        goals = InMemoryWeekGoalRepository()

        apply_parsed_week_block(
            records,
            goals,
            123,
            {
                "startDate": "2026-04-06",
                "data": {
                    "sleep": {"mon": "00:15"},
                    "work": {"mon": "00:15"},
                },
            },
        )

        bed_record = records.find(123, Activity.BED, datetime.date(2026, 4, 6))
        home_record = records.find(123, Activity.HOME, datetime.date(2026, 4, 6))

        self.assertIsNotNone(bed_record)
        self.assertIsNotNone(home_record)
        self.assertEqual(bed_record.time, RecordTime(datetime.date(2026, 4, 6), datetime.time(0, 15)))
        self.assertEqual(
            bed_record.time.to_datetime(),
            datetime.datetime(2026, 4, 6, 21, 15, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(
            home_record.time.to_datetime(),
            datetime.datetime(2026, 4, 6, 21, 15, tzinfo=datetime.timezone.utc),
        )

    def test_apply_initial_data_fixture_loads_json_file_into_repository_bundle(self) -> None:
        repositories = InMemoryRepositories()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "initial-data.json"
            path.write_text(
                """
                {
                  "user_id": 123,
                  "weeks": [
                    {
                      "startDate": "2026-04-06",
                      "goals": {"work": "20:10"},
                      "data": {"work": {"mon": "20:42"}}
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            apply_initial_data_fixture(repositories, json_path=path)

        week = WeekStart(datetime.date(2026, 4, 6))
        self.assertEqual(
            repositories.goals.find(123, Activity.HOME, week).target_time,
            datetime.time(20, 10),
        )
        self.assertEqual(
            repositories.records.find(123, Activity.HOME, datetime.date(2026, 4, 6)).time,
            RecordTime(datetime.date(2026, 4, 6), datetime.time(20, 42)),
        )

    def test_unknown_activity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            apply_parsed_week_block(
                InMemoryRecordRepository(),
                InMemoryWeekGoalRepository(),
                123,
                {
                    "startDate": "2026-04-06",
                    "data": {"exercise": {"mon": "20:42"}},
                },
            )


if __name__ == "__main__":
    unittest.main()
