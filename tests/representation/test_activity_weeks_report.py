import datetime
import unittest

from application import LoadWeekProgressUseCase
from domain import Activity, Record, RecordTime, User, WeekGoal, WeekStart
from infra.repositories import InMemoryRepositories
from representation import ActivityWeeksReportText


class ActivityWeeksReportTextTest(unittest.TestCase):
    def test_report_shows_last_three_weeks_for_one_activity(self) -> None:
        repositories = InMemoryRepositories()
        report = ActivityWeeksReportText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records)
        )
        self._save_goal_and_records(
            repositories,
            week=datetime.date(2026, 4, 27),
            target=datetime.time(20, 10),
            times=(
                datetime.time(20, 0),
                datetime.time(20, 0),
                datetime.time(20, 0),
                datetime.time(19, 58),
            ),
        )
        self._save_goal_and_records(
            repositories,
            week=datetime.date(2026, 5, 4),
            target=datetime.time(20, 5),
            times=(
                datetime.time(20, 10),
                datetime.time(20, 10),
                datetime.time(20, 5),
                datetime.time(20, 5),
            ),
        )
        self._save_goal_and_records(
            repositories,
            week=datetime.date(2026, 5, 11),
            target=datetime.time(20, 10),
            times=(datetime.time(20, 8),),
        )

        text = report.report_for_activity(
            user=User(123),
            activity=Activity.HOME,
            date=datetime.date(2026, 5, 17),
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "27.04.2026",
                    "🏠 20:10 🟢 +42 (4)",
                    "04.05.2026",
                    "🏠 20:05 🔴 -10 (4)",
                    "11.05.2026",
                    "🏠 20:10 🟢 +2 (1)",
                ]
            ),
        )

    def test_report_for_all_weeks_shows_only_weeks_with_data_without_gaps(self) -> None:
        repositories = InMemoryRepositories()
        report = ActivityWeeksReportText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records)
        )
        self._save_goal_and_records(
            repositories,
            week=datetime.date(2026, 4, 6),
            target=datetime.time(20, 10),
            times=(datetime.time(20, 0),),
        )
        self._save_goal_and_records(
            repositories,
            week=datetime.date(2026, 5, 11),
            target=datetime.time(20, 5),
            times=(datetime.time(20, 5),),
        )

        text = report.report_for_all_weeks(
            user=User(123),
            activity=Activity.HOME,
            date=datetime.date(2026, 5, 17),
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "06.04.2026",
                    "🏠 20:10 🟢 +10 (1)",
                    "11.05.2026",
                    "🏠 20:05 ⚪ +0 (1)",
                ]
            ),
        )

    def test_report_for_all_weeks_returns_empty_message_when_no_data(self) -> None:
        repositories = InMemoryRepositories()
        report = ActivityWeeksReportText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records)
        )

        text = report.report_for_all_weeks(
            user=User(123),
            activity=Activity.BED,
            date=datetime.date(2026, 5, 17),
        )

        self.assertEqual(text, "No 🛏️ weeks yet.")

    def test_report_for_all_weeks_marks_week_with_records_but_no_goal(self) -> None:
        repositories = InMemoryRepositories()
        report = ActivityWeeksReportText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records)
        )
        repositories.records.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 13), datetime.time(23, 30)),
            )
        )

        text = report.report_for_all_weeks(
            user=User(123),
            activity=Activity.BED,
            date=datetime.date(2026, 5, 17),
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "11.05.2026",
                    "🛏️ not set",
                ]
            ),
        )

    def test_report_marks_missing_goal(self) -> None:
        repositories = InMemoryRepositories()
        report = ActivityWeeksReportText(
            LoadWeekProgressUseCase(repositories.goals, repositories.records)
        )
        repositories.goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.BED,
                week=WeekStart(datetime.date(2026, 5, 11)),
                target_time=datetime.time(23, 10),
            )
        )

        text = report.report_for_activity(
            user=User(123),
            activity=Activity.BED,
            date=datetime.date(2026, 5, 17),
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "27.04.2026",
                    "🛏️ not set",
                    "04.05.2026",
                    "🛏️ not set",
                    "11.05.2026",
                    "🛏️ 23:10 ⚪ +0 (0)",
                ]
            ),
        )

    @staticmethod
    def _save_goal_and_records(
        repositories: InMemoryRepositories,
        week: datetime.date,
        target: datetime.time,
        times: tuple[datetime.time, ...],
    ) -> None:
        activity = Activity.HOME
        repositories.goals.save(
            WeekGoal(
                user_id=123,
                activity=activity,
                week=WeekStart(week),
                target_time=target,
            )
        )
        for index, time_value in enumerate(times):
            repositories.records.save(
                Record(
                    user_id=123,
                    activity=activity,
                    time=RecordTime(week + datetime.timedelta(days=index), time_value),
                )
            )


if __name__ == "__main__":
    unittest.main()
