import time
import unittest
import datetime
from unittest.mock import patch

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

    def test_record_accepts_explicit_timestamp(self) -> None:
        tracker = InMemoryTracker()
        service = TrackingService(tracker)
        user_id = int(time.time() * 1000) % 1_000_000_000
        timestamp = datetime.datetime(2026, 4, 11, 21, 45, tzinfo=datetime.timezone.utc)

        record = service.record(user_id, Activity.HOME, timestamp)

        self.assertEqual(record.timestamp, timestamp)
        self.assertEqual(tracker.events[-1], record)

    def test_history_can_be_filtered_by_activity(self) -> None:
        tracker = InMemoryTracker()
        service = TrackingService(tracker)
        user_id = int(time.time() * 1000) % 1_000_000_000

        home = service.record(user_id, Activity.HOME)
        bed = service.record(user_id, Activity.BED)

        history = service.history(user_id, days=14, activity=Activity.BED)

        self.assertEqual(history, [bed])
        self.assertNotIn(home, history)

    def test_set_goal_can_be_read_via_get_goal(self) -> None:
        tracker = InMemoryTracker()
        service = TrackingService(tracker)

        week_start = datetime.date(2026, 1, 19)  # Monday
        service.set_goal(Activity.BED, datetime.time(9, 30), week_start)

        goal = service.get_goal(Activity.BED, week_start)
        self.assertEqual(goal, datetime.time(9, 30))

    @patch("application.tracking_service._today_utc_date")
    def test_set_goal_and_get_goal_default_week_to_monday_of_current_week(self, mock_today: object) -> None:
        mock_today.return_value = datetime.date(2026, 1, 21)  # Wednesday; week Monday = 2026-01-19
        tracker = InMemoryTracker()
        service = TrackingService(tracker)

        service.set_goal(Activity.BED, datetime.time(9, 30))
        goal = service.get_goal(Activity.BED)

        self.assertEqual(goal, datetime.time(9, 30))
        self.assertEqual(tracker.goals[Activity.BED][datetime.date(2026, 1, 19)], datetime.time(9, 30))

    def test_get_goals_returns_ordered_week_goal_pairs_respects_limit(self) -> None:
        tracker = InMemoryTracker()
        service = TrackingService(tracker)

        w1 = datetime.date(2026, 1, 5)
        w2 = datetime.date(2026, 1, 12)
        w3 = datetime.date(2026, 1, 19)
        service.set_goal(Activity.HOME, datetime.time(8, 0), w1)
        service.set_goal(Activity.HOME, datetime.time(8, 15), w2)
        service.set_goal(Activity.HOME, datetime.time(8, 30), w3)
        service.set_goal(Activity.BED, datetime.time(22, 0), w3)

        goals = service.get_goals(Activity.HOME, limit=2)
        self.assertEqual(
            goals,
            [
                (w2, datetime.time(8, 15)),
                (w3, datetime.time(8, 30)),
            ],
        )

        self.assertEqual(len(service.get_goals(Activity.HOME)), 3)
        self.assertEqual(service.get_goals(Activity.BED), [(w3, datetime.time(22, 0))])


if __name__ == "__main__":
    unittest.main()
