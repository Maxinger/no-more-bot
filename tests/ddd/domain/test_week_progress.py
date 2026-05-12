import datetime
import unittest

from ddd.domain import (
    Activity,
    Record,
    RecordTime,
    WeekGoal,
    WeekProgress,
    WeekProgressLine,
    WeekStart,
)


class WeekProgressTest(unittest.TestCase):
    def _goal(self) -> WeekGoal:
        return WeekGoal(
            user_id=42,
            activity=Activity.BED,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(22, 30),
        )

    def test_reward_empty_records_is_zero(self) -> None:
        wp = WeekProgress(goal=self._goal(), records=())

        self.assertEqual(wp.reward(), 0)

    def test_reward_one_day_actual_earlier_than_goal(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(22, 0)),
            ),
        )
        wp = WeekProgress(goal=goal, records=records)

        self.assertEqual(wp.reward(), 30)

    def test_records_are_normalized_to_immutable_tuple(self) -> None:
        goal = self._goal()
        records = [
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(22, 0)),
            )
        ]
        wp = WeekProgress(goal=goal, records=records)

        self.assertEqual(wp.records, tuple(records))

    def test_reward_sums_multiple_days(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 5), datetime.time(22, 15)),
            ),
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 7), datetime.time(23, 0)),
            ),
        )
        wp = WeekProgress(goal=goal, records=records)

        self.assertEqual(wp.reward(), 15 + (-30))

    def test_report_lines_are_structured_per_day_rewards(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 7), datetime.time(23, 0)),
            ),
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 5), datetime.time(22, 15)),
            ),
        )
        wp = WeekProgress(goal=goal, records=records)

        self.assertEqual(
            wp.report_lines(),
            (
                WeekProgressLine(
                    date=datetime.date(2026, 5, 5),
                    time=datetime.time(22, 15),
                    reward=15,
                ),
                WeekProgressLine(
                    date=datetime.date(2026, 5, 7),
                    time=datetime.time(23, 0),
                    reward=-30,
                ),
            ),
        )

    def test_rejects_mismatched_user_id(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=99,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(22, 0)),
            ),
        )

        with self.assertRaises(ValueError) as ctx:
            WeekProgress(goal=goal, records=records)

        self.assertIn("user_id", str(ctx.exception).lower())

    def test_rejects_mismatched_activity(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.HOME,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(22, 0)),
            ),
        )

        with self.assertRaises(ValueError) as ctx:
            WeekProgress(goal=goal, records=records)

        self.assertIn("activity", str(ctx.exception).lower())

    def test_rejects_record_outside_goal_week(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 11), datetime.time(22, 0)),
            ),
        )

        with self.assertRaises(ValueError) as ctx:
            WeekProgress(goal=goal, records=records)

        self.assertIn("logical day", str(ctx.exception).lower())

    def test_rejects_duplicate_logical_days(self) -> None:
        goal = self._goal()
        day = datetime.date(2026, 5, 8)
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(day, datetime.time(21, 0)),
            ),
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(day, datetime.time(23, 0)),
            ),
        )

        with self.assertRaises(ValueError) as ctx:
            WeekProgress(goal=goal, records=records)

        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_early_morning_logical_day_uses_record_time_instant_semantics(self) -> None:
        """Logical Fri evening cycle: actual after midnight maps to next calendar day."""
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15)),
            ),
        )
        wp = WeekProgress(goal=goal, records=records)

        target = datetime.datetime(
            2026, 5, 8, 22, 30, tzinfo=datetime.timezone.utc
        )
        actual = datetime.datetime(
            2026, 5, 9, 0, 15, tzinfo=datetime.timezone.utc
        )
        expected_minutes = int((target - actual).total_seconds() / 60)

        self.assertEqual(wp.reward(), expected_minutes)

    def test_goal_time_before_day_start_uses_same_logical_day_semantics(self) -> None:
        goal = WeekGoal(
            user_id=42,
            activity=Activity.BED,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(0, 30),
        )
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15)),
            ),
        )
        wp = WeekProgress(goal=goal, records=records)

        self.assertEqual(wp.reward(), 15)

    def test_next_week_goal_zero_reward_keeps_target(self) -> None:
        wp = WeekProgress(goal=self._goal(), records=())

        nxt = wp.next_week_goal()
        self.assertEqual(nxt.user_id, 42)
        self.assertEqual(nxt.activity, Activity.BED)
        self.assertEqual(nxt.week, WeekStart(datetime.date(2026, 5, 11)))
        self.assertEqual(nxt.target_time, datetime.time(22, 30))

    def test_next_week_goal_positive_reward_moves_target_five_minutes_earlier(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(22, 0)),
            ),
        )
        wp = WeekProgress(goal=goal, records=records)

        self.assertEqual(wp.next_week_goal().target_time, datetime.time(22, 25))

    def test_next_week_goal_negative_reward_moves_target_five_minutes_later(self) -> None:
        goal = self._goal()
        records = (
            Record(
                activity=Activity.BED,
                user_id=42,
                time=RecordTime(datetime.date(2026, 5, 6), datetime.time(23, 0)),
            ),
        )
        wp = WeekProgress(goal=goal, records=records)

        self.assertEqual(wp.next_week_goal().target_time, datetime.time(22, 35))


if __name__ == "__main__":
    unittest.main()
