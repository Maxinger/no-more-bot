import datetime
import unittest

from ddd.application import (
    RecordActivityForDayCommand,
    RecordActivityNowCommand,
    RecordActivityUseCase,
)
from ddd.domain import Activity, Record, RecordTime


class FakeRecordRepository:
    def __init__(self) -> None:
        self.saved_records: list[Record] = []

    def save(self, record: Record) -> None:
        self.saved_records.append(record)


class RecordActivityUseCaseTest(unittest.TestCase):
    def test_record_activity_now_saves_record_from_timestamp(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        record = use_case.handle(
            RecordActivityNowCommand(
                user_id=123,
                activity=Activity.HOME,
                occurred_at=datetime.datetime(2026, 5, 8, 22, 30, tzinfo=datetime.timezone.utc),
            )
        )

        self.assertEqual(
            record,
            Record(
                activity=Activity.HOME,
                user_id=123,
                time=RecordTime(datetime.date(2026, 5, 8), datetime.time(22, 30)),
            ),
        )
        self.assertEqual(repository.saved_records, [record])

    def test_record_activity_now_uses_logical_day_for_early_time(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        record = use_case.handle(
            RecordActivityNowCommand(
                user_id=123,
                activity=Activity.BED,
                occurred_at=datetime.datetime(2026, 5, 9, 0, 15, tzinfo=datetime.timezone.utc),
            )
        )

        self.assertEqual(
            record.time,
            RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15)),
        )

    def test_record_activity_for_day_saves_record_from_logical_date_and_time(self) -> None:
        repository = FakeRecordRepository()
        use_case = RecordActivityUseCase(repository)

        record = use_case.handle(
            RecordActivityForDayCommand(
                user_id=123,
                activity=Activity.BED,
                activity_date=datetime.date(2026, 5, 8),
                activity_time=datetime.time(0, 15),
            )
        )

        self.assertEqual(
            record,
            Record(
                activity=Activity.BED,
                user_id=123,
                time=RecordTime(datetime.date(2026, 5, 8), datetime.time(0, 15)),
            ),
        )
        self.assertEqual(
            record.time.to_datetime(),
            datetime.datetime(2026, 5, 9, 0, 15, tzinfo=datetime.timezone.utc),
        )

    def test_unsupported_command_is_rejected(self) -> None:
        use_case = RecordActivityUseCase(FakeRecordRepository())

        with self.assertRaises(TypeError):
            use_case.handle(object())


if __name__ == "__main__":
    unittest.main()
