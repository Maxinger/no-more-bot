import datetime
import unittest

from ddd.application import LoadWeekProgressUseCase
from ddd.domain import Activity, Record, RecordTime, User, WeekGoal, WeekStart
from ddd.infra.repositories import InMemoryRepositories
from ddd.representation import CurrentWeekSummaryText


class CurrentWeekSummaryTextTest(unittest.TestCase):
    def test_summary_loads_current_week_progress_for_home_and_bed(self) -> None:
        repositories = InMemoryRepositories()
        summary = CurrentWeekSummaryText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records),
            current_datetime=lambda: datetime.datetime(
                2026, 5, 7, 9, 0, tzinfo=datetime.timezone.utc
            ),
        )
        week = WeekStart(datetime.date(2026, 5, 4))
        repositories.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=week,
                target_time=datetime.time(18, 0),
            )
        )
        repositories.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.BED,
                week=week,
                target_time=datetime.time(22, 30),
            )
        )
        repositories.records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 5), datetime.time(17, 50)),
            )
        )
        repositories.records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 7), datetime.time(18, 15)),
            )
        )
        repositories.records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 11), datetime.time(17, 30)),
            )
        )

        text = summary.summary_for_current_week(User(123))

        self.assertEqual(
            text,
            "\n".join(
                [
                    "Current week (04.05.2026)",
                    "",
                    "🏠 18:00 🔴 -5 (2)",
                    "",
                    "🛏️ 22:30 ⚪ +0 (0)",
                ]
            ),
        )

    def test_summary_marks_missing_goal_as_not_available(self) -> None:
        repositories = InMemoryRepositories()
        summary = CurrentWeekSummaryText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records),
            current_datetime=lambda: datetime.datetime(
                2026, 5, 7, 9, 0, tzinfo=datetime.timezone.utc
            ),
        )
        repositories.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(datetime.date(2026, 5, 4)),
                target_time=datetime.time(18, 0),
            )
        )

        text = summary.summary_for_current_week(User(123))

        self.assertEqual(
            text,
            "\n".join(
                [
                    "Current week (04.05.2026)",
                    "",
                    "🏠 18:00 ⚪ +0 (0)",
                    "",
                    "🛏️ not set",
                ]
            ),
        )

    def test_summary_uses_user_timezone_when_utc_date_is_still_previous_week(self) -> None:
        repositories = InMemoryRepositories()
        summary = CurrentWeekSummaryText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records),
            current_datetime=lambda: datetime.datetime(
                2026, 5, 17, 22, 30, tzinfo=datetime.timezone.utc
            ),
        )
        repositories.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(datetime.date(2026, 5, 18)),
                target_time=datetime.time(18, 0),
            )
        )

        text = summary.summary_for_current_week(User(123))

        self.assertEqual(
            text,
            "\n".join(
                [
                    "Current week (18.05.2026)",
                    "",
                    "🏠 18:00 ⚪ +0 (0)",
                    "",
                    "🛏️ not set",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
