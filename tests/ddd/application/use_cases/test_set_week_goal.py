import datetime
import unittest

from ddd.application import SetWeekGoalCommand, SetWeekGoalResult, SetWeekGoalUseCase
from ddd.domain import Activity, WeekGoal, WeekStart


class FakeWeekGoalRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, Activity, datetime.date], WeekGoal] = {}

    def find(self, user_id: int, activity: Activity, week: WeekStart) -> WeekGoal | None:
        return self._by_key.get((user_id, activity, week.value))

    def save(self, goal: WeekGoal) -> None:
        self._by_key[(goal.user_id, goal.activity, goal.week.value)] = goal

    @property
    def saved_goals(self) -> list[WeekGoal]:
        return list(self._by_key.values())


class SetWeekGoalUseCaseTest(unittest.TestCase):
    def test_first_set_returns_replaced_false(self) -> None:
        repository = FakeWeekGoalRepository()
        use_case = SetWeekGoalUseCase(repository)

        monday = datetime.date(2026, 5, 4)
        expected = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(monday),
            target_time=datetime.time(22, 30),
        )
        result = use_case.handle(
            SetWeekGoalCommand(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(monday),
                target_time=datetime.time(22, 30),
            )
        )

        self.assertEqual(result, SetWeekGoalResult(goal=expected, replaced_existing=False))
        self.assertEqual(repository.saved_goals, [expected])

    def test_second_set_same_triple_different_target_time_returns_replaced_true(self) -> None:
        repository = FakeWeekGoalRepository()
        use_case = SetWeekGoalUseCase(repository)

        monday = datetime.date(2026, 5, 4)
        first = use_case.handle(
            SetWeekGoalCommand(
                user_id=123,
                activity=Activity.BED,
                week=WeekStart(monday),
                target_time=datetime.time(22, 0),
            )
        )
        second_expected = WeekGoal(
            user_id=123,
            activity=Activity.BED,
            week=WeekStart(monday),
            target_time=datetime.time(23, 30),
        )
        second = use_case.handle(
            SetWeekGoalCommand(
                user_id=123,
                activity=Activity.BED,
                week=WeekStart(monday),
                target_time=datetime.time(23, 30),
            )
        )

        self.assertFalse(first.replaced_existing)
        self.assertEqual(second, SetWeekGoalResult(goal=second_expected, replaced_existing=True))
        self.assertEqual(repository.saved_goals, [second_expected])

    def test_same_iso_week_wednesday_then_monday_second_replaces_same_row(self) -> None:
        repository = FakeWeekGoalRepository()
        use_case = SetWeekGoalUseCase(repository)

        wednesday = datetime.date(2026, 5, 6)
        monday = datetime.date(2026, 5, 4)

        first = use_case.handle(
            SetWeekGoalCommand(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart.from_any_date(wednesday),
                target_time=datetime.time(21, 0),
            )
        )
        second_expected = WeekGoal(
            user_id=123,
            activity=Activity.HOME,
            week=WeekStart(monday),
            target_time=datetime.time(22, 0),
        )
        second = use_case.handle(
            SetWeekGoalCommand(
                user_id=123,
                activity=Activity.HOME,
                week=WeekStart(monday),
                target_time=datetime.time(22, 0),
            )
        )

        self.assertFalse(first.replaced_existing)
        self.assertEqual(first.goal.week, WeekStart(monday))
        self.assertEqual(second, SetWeekGoalResult(goal=second_expected, replaced_existing=True))
        self.assertEqual(repository.saved_goals, [second_expected])

    def test_unsupported_command_is_rejected(self) -> None:
        use_case = SetWeekGoalUseCase(FakeWeekGoalRepository())

        with self.assertRaises(TypeError):
            use_case.handle(object())


if __name__ == "__main__":
    unittest.main()
