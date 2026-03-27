import time
import unittest

from application.tracking_service import TrackingService
from domain.model.record import Activity
from infra.tracker.in_memory import InMemoryTracker


class TrackingServiceTest(unittest.TestCase):
    def test_record_and_history_delegate_to_tracker(self) -> None:
        tracker = InMemoryTracker()
        service = TrackingService(tracker)
        user_id = int(time.time() * 1000) % 1_000_000_000

        first = service.record(user_id, Activity.HOME)
        second = service.record(user_id, Activity.BED)
        history = service.history(user_id, days=14)

        self.assertEqual(history[:2], [second, first])

    def test_history_can_be_filtered_by_activity(self) -> None:
        tracker = InMemoryTracker()
        service = TrackingService(tracker)
        user_id = int(time.time() * 1000) % 1_000_000_000

        home = service.record(user_id, Activity.HOME)
        bed = service.record(user_id, Activity.BED)

        history = service.history(user_id, days=14, activity=Activity.BED)

        self.assertEqual(history, [bed])
        self.assertNotIn(home, history)


if __name__ == "__main__":
    unittest.main()
