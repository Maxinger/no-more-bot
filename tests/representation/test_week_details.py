import datetime
import unittest

from application import LoadWeekProgressUseCase
from domain import Activity, Record, RecordTime, User, WeekGoal, WeekStart
from infra.repositories import InMemoryRepositories
from representation import WeekDetailsText


class WeekDetailsTextTest(unittest.TestCase):
    def test_details_show_goal_total_and_per_day_progress(self) -> None:
        repositories = InMemoryRepositories()
        details = WeekDetailsText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records)
        )
        week = WeekStart(datetime.date(2026, 5, 11))
        repositories.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=week,
                target_time=datetime.time(20, 10),
            )
        )
        for day, time_value in (
            (datetime.date(2026, 5, 11), datetime.time(20, 1)),
            (datetime.date(2026, 5, 13), datetime.time(20, 10)),
            (datetime.date(2026, 5, 14), datetime.time(20, 25)),
        ):
            repositories.records.save(
                Record(
                    user_id=123,
                    activity=Activity.HOME,
                    time=RecordTime(day, time_value),
                )
            )

        text = details.details_for_week(
            user=User(123),
            activity=Activity.HOME,
            date=datetime.date(2026, 5, 16),
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "🏠 Week progress (11.05.2026)",
                    "",
                    "Goal: 20:10 🔴 -6",
                    "===============",
                    "Mon: 20:01 👍 +9",
                    "",
                    "Wed: 20:10 👍 +0",
                    "",
                    "Thu: 20:25 ❌ -15",
                    "",
                ]
            ),
        )

    def test_details_mark_missing_goal(self) -> None:
        repositories = InMemoryRepositories()
        details = WeekDetailsText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records)
        )

        text = details.details_for_week(
            user=User(123),
            activity=Activity.BED,
            date=datetime.date(2026, 5, 16),
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "🛏️ Week progress (11.05.2026)",
                    "",
                    "Goal: not set",
                    "===============",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
