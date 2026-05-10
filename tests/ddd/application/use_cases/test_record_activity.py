import datetime
import unittest

from ddd.application import (
    RecordActivityForDayCommand,
    RecordActivityNowCommand,
    RecordActivityResult,
    RecordActivityUseCase,
)
from ddd.domain import Activity, Record, RecordTime


class FakeRecordRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[int, Activity, datetime.date], Record] = {}

    def find(self, user_id: int, activity: Activity, date: datetime.date) -> Record | None:
        return self._by_key.get((user_id, activity, date))

    def save(self, record: Record) -> None:
        self._by_key[(record.user_id, record.activity, record.time.date)] = record

    @property
    def saved_records(self) -> list[Record]:
        return list(self._by_key.values())


class RecordActivityUseCaseTest(unittest.TestCase):
    def test_record_activity_now_saves_record_from_timestamp(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        expected_record = Record(
            activity=Activity.HOME,
            user_id=123,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30)),
        )
        result = use_case.handle(
            RecordActivityNowCommand(
                user_id=123,
                activity=Activity.HOME,
                occurred_at=datetime.datetime(2026, 5, 8, 22, 30, tzinfo=datetime.timezone.utc),
            )
        )

        self.assertEqual(
            result,
            RecordActivityResult(record=expected_record, replaced_existing=False),
        )
        self.assertEqual(repository.saved_records, [expected_record])

    def test_record_activity_now_uses_logical_day_for_early_time(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        result = use_case.handle(
            RecordActivityNowCommand(
                user_id=123,
                activity=Activity.BED,
                occurred_at=datetime.datetime(2026, 5, 9, 0, 15, tzinfo=datetime.timezone.utc),
            )
        )

        self.assertFalse(result.replaced_existing)
        self.assertEqual(
            result.record.time,
            RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15)),
        )

    def test_record_activity_for_day_saves_record_from_logical_date_and_time(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        expected_record = Record(
            activity=Activity.BED,
            user_id=123,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15)),
        )
        result = use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.BED,
                activity_date=datetime.date(2026, 5, 8),
                activity_time=datetime.time(0, 15),
            )
        )

        self.assertEqual(
            result,
            RecordActivityResult(record=expected_record, replaced_existing=False),
        )
        self.assertEqual(
            result.record.time.to_datetime(),
            datetime.datetime(2026, 5, 9, 0, 15, tzinfo=datetime.timezone.utc),
        )

    def test_second_record_same_user_activity_and_logical_day_replaces_first(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        first = use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.BED,
                activity_date=datetime.date(2026, 5, 8),
                activity_time=datetime.time(22, 0),
            )
        )
        second_expected = Record(
            activity=Activity.BED,
            user_id=123,
            time=RecordTime(datetime.date(2026, 5, 8), datetime.time(23, 30)),
        )
        second = use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.BED,
                activity_date=datetime.date(2026, 5, 8),
                activity_time=datetime.time(23, 30),
            )
        )

        self.assertEqual(
            first,
            RecordActivityResult(
                record=Record(
                    activity=Activity.BED,
                    user_id=123,
                    time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 0)),
                ),
                replaced_existing=False,
            ),
        )
        self.assertEqual(
            second,
            RecordActivityResult(record=second_expected, replaced_existing=True),
        )
        self.assertEqual(repository.saved_records, [second_expected])

    def test_different_activities_same_logical_day_are_distinct(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.HOME,
                activity_date=datetime.date(2026, 5, 8),
                activity_time=datetime.time(21, 0),
            )
        )
        bed = use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.BED,
                activity_date=datetime.date(2026, 5, 8),
                activity_time=datetime.time(23, 0),
            )
        )

        self.assertFalse(bed.replaced_existing)
        self.assertEqual(len(repository.saved_records), 2)

    def test_records_on_different_logical_days_are_not_replacements(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        day1 = use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.HOME,
                activity_date=datetime.date(2026, 5, 8),
                activity_time=datetime.time(22, 0),
            )
        )
        day2 = use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.BED,
                activity_date=datetime.date(2026, 5, 9),
                activity_time=datetime.time(22, 0),
            )
        )

        self.assertFalse(day1.replaced_existing)
        self.assertFalse(day2.replaced_existing)
        self.assertEqual(len(repository.saved_records), 2)

    def test_unsupported_command_is_rejected(self) -> None:
        use_case = RecordActivityUseCase(FakeRecordRepository())

        with self.assertRaises(TypeError):
            use_case.handle(object())


if __name__ == "__main__":
    unittest.main()
