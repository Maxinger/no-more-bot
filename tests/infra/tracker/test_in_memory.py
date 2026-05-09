import time
import unittest
import datetime

from domain.model.record import Activity
from infra.tracker.in_memory import InMemoryTracker


class TrackerTest(unittest.TestCase):
    def test_record_and_history_return_all_records(self) -> None:
        tracker = InMemoryTracker()

        # Use a timestamp-derived user_id to avoid polluting the persistent DB
        # across multiple test runs.
        user_id = int(time.time() * 1000) % 1_000_000_000

        recorded: list = []
        for _ in range(3):
            recorded.append(tracker.record(user_id, Activity.HOME))
            time.sleep(0.05)

        history = tracker.history(user_id, days=14)

        self.assertGreaterEqual(len(history), 3)
        self.assertEqual(history[:3], recorded[::-1])

        for record in recorded:
            self.assertIn(record, history)

    def test_record_uses_explicit_timestamp_and_history_is_sorted_by_timestamp(self) -> None:
        tracker = InMemoryTracker()
        user_id = int(time.time() * 1000) % 1_000_000_000

        older = tracker.record(
            user_id,
            Activity.HOME,
            timestamp=datetime.datetime(2026, 4, 10, 18, 0, tzinfo=datetime.timezone.utc),
        )
        newer = tracker.record(
            user_id,
            Activity.BED,
            timestamp=datetime.datetime(2026, 4, 11, 7, 30, tzinfo=datetime.timezone.utc),
        )
        middle = tracker.record(
            user_id,
            Activity.HOME,
            timestamp=datetime.datetime(2026, 4, 10, 22, 15, tzinfo=datetime.timezone.utc),
        )

        history = tracker.history(user_id, days=36500)

        self.assertEqual(older.timestamp, datetime.datetime(2026, 4, 10, 18, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(history[:3], [newer, middle, older])

    def test_history_can_be_filtered_by_activity(self) -> None:
        tracker = InMemoryTracker()
        user_id = int(time.time() * 1000) % 1_000_000_000

        home = tracker.record(user_id, Activity.HOME)
        bed = tracker.record(user_id, Activity.BED)
        home_again = tracker.record(user_id, Activity.HOME)

        only_home = tracker.history(user_id, days=14, activity=Activity.HOME)
        only_bed = tracker.history(user_id, days=14, activity=Activity.BED)

        self.assertEqual(only_home, [home_again, home])
        self.assertEqual(only_bed, [bed])


if __name__ == "__main__":
    unittest.main()
