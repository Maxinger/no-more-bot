import datetime
import unittest

from application import (
    LoadActivityAvailableWeeksCommand,
    LoadActivityAvailableWeeksResult,
    LoadCurrentWeekGoalPreviewCommand,
    LoadCurrentWeekGoalPreviewResult,
    LoadWeekProgressInRangeCommand,
    LoadWeekProgressInRangeResult,
    LoadWeekProgressCommand,
    LoadWeekProgressResult,
    LoadWeekProgressUseCase,
    WeekProgressInRangeEntry,
)
from domain import Activity, Record, RecordTime, User, WeekGoal, WeekProgress, WeekStart
from infra import InMemoryRecordRepository, InMemoryWeekGoalRepository


class LoadWeekProgressUseCaseTest(unittest.TestCase):
    def test_loads_goal_and_records_for_week_containing_date(self) -> None:
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        week = WeekStart(datetime.date(2026, 5, 4))
        goal = WeekGoal(
            user_id=123,
            activity=Activity.BED,
            week=week,
            target_time=datetime.time(22, 30),
        )
        included = Record(
            user_id=123,
            activity=Activity.BED,
            time=RecordTime(datetime.date(2026, 5, 6), datetime.time(22, 0)),
        )
        goals.save(goal)
        records.save(included)
        records.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 11), datetime.time(22, 0)),
            )
        )

        result = use_case.handle(
            LoadWeekProgressCommand(
                user=User(123),
                activity=Activity.BED,
                date=datetime.date(2026, 5, 7),
            )
        )

        self.assertEqual(
            result,
            LoadWeekProgressResult(
                progress=WeekProgress(goal=goal, records=(included,)),
            ),
        )

    def test_existing_goal_without_records_returns_empty_progress(self) -> None:
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        goal = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 4)),
            target_time=datetime.time(18, 0),
        )
        goals.save(goal)

        result = use_case.handle(
            LoadWeekProgressCommand(
                user=User(123),
                activity=Activity.HOME,
                date=datetime.date(2026, 5, 4),
            )
        )

        self.assertEqual(
            result,
            LoadWeekProgressResult(progress=WeekProgress(goal=goal, records=())),
        )

    def test_missing_goal_returns_none(self) -> None:
        use_case = LoadWeekProgressUseCase(
            InMemoryWeekGoalRepository(),
            InMemoryRecordRepository(),
        )

        result = use_case.handle(
            LoadWeekProgressCommand(
                user=User(123),
                activity=Activity.HOME,
                date=datetime.date(2026, 5, 4),
            )
        )

        self.assertEqual(result, LoadWeekProgressResult(progress=None))

    def test_current_week_goal_preview_returns_existing_current_progress(self) -> None:
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        current_goal = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(datetime.date(2026, 5, 11)),
            target_time=datetime.time(20, 0),
        )
        goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(datetime.date(2026, 5, 4)),
                target_time=datetime.time(19, 55),
            )
        )
        goals.save(current_goal)

        result = use_case.handle(
            LoadCurrentWeekGoalPreviewCommand(
                user=User(123),
                activity=Activity.HOME,
                date=datetime.date(2026, 5, 14),
            )
        )

        self.assertEqual(
            result,
            LoadCurrentWeekGoalPreviewResult(
                progress=WeekProgress(goal=current_goal, records=()),
                is_auto=False,
            ),
        )

    def test_current_week_goal_preview_recommends_from_previous_week(self) -> None:
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(datetime.date(2026, 5, 4)),
                target_time=datetime.time(20, 0),
            )
        )
        records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 5), datetime.time(19, 50)),
            )
        )
        current_record = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 12), datetime.time(19, 40)),
        )
        records.save(current_record)

        result = use_case.handle(
            LoadCurrentWeekGoalPreviewCommand(
                user=User(123),
                activity=Activity.HOME,
                date=datetime.date(2026, 5, 14),
            )
        )

        self.assertEqual(result.is_auto, True)
        self.assertEqual(result.progress.goal.week, WeekStart(datetime.date(2026, 5, 11)))
        self.assertEqual(result.progress.goal.target_time, datetime.time(19, 55))
        self.assertEqual(result.progress.records, (current_record,))

    def test_current_week_goal_preview_without_previous_goal_returns_none(self) -> None:
        use_case = LoadWeekProgressUseCase(
            InMemoryWeekGoalRepository(),
            InMemoryRecordRepository(),
        )

        result = use_case.handle(
            LoadCurrentWeekGoalPreviewCommand(
                user=User(123),
                activity=Activity.BED,
                date=datetime.date(2026, 5, 14),
            )
        )

        self.assertEqual(
            result,
            LoadCurrentWeekGoalPreviewResult(progress=None, is_auto=False),
        )

    def test_loads_progress_for_normalized_week_range_in_chronological_order(self) -> None:
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        first_week = WeekStart(datetime.date(2026, 4, 27))
        second_week = WeekStart(datetime.date(2026, 5, 4))
        first_goal = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=first_week,
            target_time=datetime.time(20, 10),
        )
        second_goal = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=second_week,
            target_time=datetime.time(20, 5),
        )
        first_record = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 4, 27), datetime.time(19, 28)),
        )
        second_record = Record(
            user_id=123,
            activity=Activity.HOME,
            time=RecordTime(datetime.date(2026, 5, 4), datetime.time(20, 15)),
        )
        goals.save(first_goal)
        goals.save(second_goal)
        records.save(first_record)
        records.save(second_record)

        result = use_case.handle(
            LoadWeekProgressInRangeCommand(
                user=User(123),
                activity=Activity.HOME,
                start_date=datetime.date(2026, 4, 29),
                end_date=datetime.date(2026, 5, 16),
            )
        )

        self.assertEqual(
            result,
            LoadWeekProgressInRangeResult(
                weeks=(
                    WeekProgressInRangeEntry(
                        week=first_week,
                        progress=WeekProgress(
                            goal=first_goal,
                            records=(first_record,),
                        ),
                    ),
                    WeekProgressInRangeEntry(
                        week=second_week,
                        progress=WeekProgress(
                            goal=second_goal,
                            records=(second_record,),
                        ),
                    ),
                    WeekProgressInRangeEntry(
                        week=WeekStart(datetime.date(2026, 5, 11)),
                        progress=None,
                    ),
                )
            ),
        )

    def test_range_rejects_end_date_before_start_date(self) -> None:
        use_case = LoadWeekProgressUseCase(
            InMemoryWeekGoalRepository(),
            InMemoryRecordRepository(),
        )

        with self.assertRaises(ValueError):
            use_case.handle(
                LoadWeekProgressInRangeCommand(
                    user=User(123),
                    activity=Activity.HOME,
                    start_date=datetime.date(2026, 5, 11),
                    end_date=datetime.date(2026, 5, 4),
                )
            )

    def test_available_weeks_returns_empty_for_user_with_no_data(self) -> None:
        use_case = LoadWeekProgressUseCase(
            InMemoryWeekGoalRepository(),
            InMemoryRecordRepository(),
        )

        result = use_case.handle(
            LoadActivityAvailableWeeksCommand(user=User(123), activity=Activity.HOME)
        )

        self.assertEqual(result, LoadActivityAvailableWeeksResult(weeks=()))

    def test_available_weeks_includes_home_goal_and_record_weeks_only(self) -> None:
        goals = InMemoryWeekGoalRepository()
        records = InMemoryRecordRepository()
        use_case = LoadWeekProgressUseCase(goals, records)
        goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(datetime.date(2026, 4, 6)),
                target_time=datetime.time(20, 0),
            )
        )
        records.save(
            Record(
                user_id=123,
                activity=Activity.HOME,
                time=RecordTime(datetime.date(2026, 5, 15), datetime.time(21, 0)),
            )
        )
        goals.save(
            WeekGoal(
                user_id=123,
                activity=Activity.BED,
                week=WeekStart(datetime.date(2026, 5, 11)),
                target_time=datetime.time(23, 0),
            )
        )

        result = use_case.handle(
            LoadActivityAvailableWeeksCommand(user=User(123), activity=Activity.HOME)
        )

        self.assertEqual(
            result,
            LoadActivityAvailableWeeksResult(
                weeks=(
                    WeekStart(datetime.date(2026, 4, 6)),
                    WeekStart(datetime.date(2026, 5, 11)),
                )
            ),
        )

    def test_available_weeks_includes_bed_record_week_without_goal(self) -> None:
        records = InMemoryRecordRepository()
        use_case = LoadWeekProgressUseCase(InMemoryWeekGoalRepository(), records)
        records.save(
            Record(
                user_id=123,
                activity=Activity.BED,
                time=RecordTime(datetime.date(2026, 5, 13), datetime.time(23, 30)),
            )
        )

        result = use_case.handle(
            LoadActivityAvailableWeeksCommand(user=User(123), activity=Activity.BED)
        )

        self.assertEqual(
            result,
            LoadActivityAvailableWeeksResult(weeks=(WeekStart(datetime.date(2026, 5, 11)),)),
        )

    def test_unsupported_command_is_rejected(self) -> None:
        use_case = LoadWeekProgressUseCase(
            InMemoryWeekGoalRepository(),
            InMemoryRecordRepository(),
        )

        with self.assertRaises(TypeError):
            use_case.handle(object())


if __name__ == "__main__":
    unittest.main()
