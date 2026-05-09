import datetime
from dataclasses import FrozenInstanceError
import unittest

from ddd.domain import Activity, Record, RecordTime, WeekStart


class DddRecordTest(unittest.TestCase):
    def test_record_is_value_object(self) -> None:
        record = Record(
            activity=Activity.HOME,
            user_id=123,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30)),
        )

        same_record = Record(
            activity=Activity.HOME,
            user_id=123,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30)),
        )

        self.assertEqual(record, same_record)
        with self.assertRaises(FrozenInstanceError):
            record.user_id = 456

    def test_record_time_converts_to_actual_datetime_after_day_start(self) -> None:
        record_time = RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30))

        self.assertEqual(
            record_time.to_datetime(),
            datetime.datetime(2026, 5, 8, 22, 30, tzinfo=datetime.timezone.utc),
        )

    def test_record_time_converts_early_time_to_next_calendar_day(self) -> None:
        record_time = RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15))

        self.assertEqual(
            record_time.to_datetime(),
            datetime.datetime(2026, 5, 9, 0, 15, tzinfo=datetime.timezone.utc),
        )

    def test_record_time_can_be_created_from_datetime_after_day_start(self) -> None:
        record_time = RecordTime.from_datetime(
            datetime.datetime(2026, 5, 8, 22, 30, tzinfo=datetime.timezone.utc)
        )

        self.assertEqual(
            record_time,
            RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30)),
        )

    def test_record_time_can_be_created_from_early_datetime(self) -> None:
        record_time = RecordTime.from_datetime(
            datetime.datetime(2026, 5, 9, 0, 15, tzinfo=datetime.timezone.utc)
        )

        self.assertEqual(
            record_time,
            RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15)),
        )

    def test_week_start_keeps_monday(self) -> None:
        week_start = WeekStart(datetime.date(2026, 5, 4))

        self.assertEqual(week_start.value, datetime.date(2026, 5, 4))

    def test_week_start_rejects_non_monday(self) -> None:
        with self.assertRaises(ValueError):
            WeekStart(datetime.date(2026, 5, 8))

    def test_week_start_can_be_created_from_any_date(self) -> None:
        week_start = WeekStart.from_any_date(datetime.date(2026, 5, 8))

        self.assertEqual(week_start.value, datetime.date(2026, 5, 4))


if __name__ == "__main__":
    unittest.main()
