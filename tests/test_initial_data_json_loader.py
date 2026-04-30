import datetime
import unittest

from application.tracking_service import TrackingService
from domain.model.record import Activity, activity_day
from infra.dev.initial_data_json_loader import apply_parsed_week_block
from infra.tracker.in_memory import InMemoryTracker


class InitialDataJsonLoaderTest(unittest.TestCase):
    def test_sleep_after_midnight_is_loaded_as_next_actual_day(self) -> None:
        tracker = InMemoryTracker()
        service = TrackingService(tracker)

        apply_parsed_week_block(
            service,
            123,
            {
                "startDate": "2026-04-06",
                "data": {
                    "sleep": {"mon": "00:15"},
                    "work": {"mon": "00:15"},
                },
            },
        )

        bed_record = next(record for record in tracker.events if record.activity == Activity.BED)
        home_record = next(record for record in tracker.events if record.activity == Activity.HOME)

        self.assertEqual(bed_record.timestamp, datetime.datetime(2026, 4, 7, 0, 15, tzinfo=datetime.timezone.utc))
        self.assertEqual(activity_day(Activity.BED, bed_record.timestamp), datetime.date(2026, 4, 6))
        self.assertEqual(home_record.timestamp, datetime.datetime(2026, 4, 6, 0, 15, tzinfo=datetime.timezone.utc))


if __name__ == "__main__":
    unittest.main()
