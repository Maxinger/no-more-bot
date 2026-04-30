import datetime
import unittest

from domain.model.record import Activity, activity_day, timestamp_for_activity_day


class ActivityDayTest(unittest.TestCase):
    def test_bed_after_midnight_belongs_to_previous_activity_day(self) -> None:
        timestamp = datetime.datetime(2026, 4, 7, 0, 15, tzinfo=datetime.timezone.utc)

        self.assertEqual(activity_day(Activity.BED, timestamp), datetime.date(2026, 4, 6))

    def test_home_after_midnight_uses_actual_date(self) -> None:
        timestamp = datetime.datetime(2026, 4, 7, 0, 15, tzinfo=datetime.timezone.utc)

        self.assertEqual(activity_day(Activity.HOME, timestamp), datetime.date(2026, 4, 7))

    def test_bed_fixture_timestamp_preserves_logical_day(self) -> None:
        timestamp = timestamp_for_activity_day(
            Activity.BED,
            datetime.date(2026, 4, 6),
            datetime.time(0, 15),
        )

        self.assertEqual(timestamp, datetime.datetime(2026, 4, 7, 0, 15, tzinfo=datetime.timezone.utc))
        self.assertEqual(activity_day(Activity.BED, timestamp), datetime.date(2026, 4, 6))


if __name__ == "__main__":
    unittest.main()
