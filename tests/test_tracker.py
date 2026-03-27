import time
import unittest

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

