"""Use case for recording an activity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from ddd.application.use_case import UseCase, handles
from ddd.domain.ports import RecordRepository
from ddd.domain.record import Activity, Record, RecordTime


@dataclass(frozen=True)
class RecordActivityNowCommand:
    user_id: int
    activity: Activity
    occurred_at: datetime


@dataclass(frozen=True)
class RecordActivityForDayCommand:
    user_id: int
    activity: Activity
    activity_date: date
    activity_time: time


@dataclass(frozen=True)
class RecordActivityResult:
    """Outcome of recording (upsert): new row vs replacing the same user/activity/logical day."""

    record: Record
    replaced_existing: bool


class RecordActivityUseCase(UseCase):
    def __init__(self, records: RecordRepository):
        self._records = records

    @handles(RecordActivityNowCommand)
    def _record_now(self, command: RecordActivityNowCommand) -> RecordActivityResult:
        return self._record(
            user_id=command.user_id,
            activity=command.activity,
            record_time=RecordTime.from_datetime(command.occurred_at),
        )

    @handles(RecordActivityForDayCommand)
    def _record_for_day(self, command: RecordActivityForDayCommand) -> RecordActivityResult:
        return self._record(
            user_id=command.user_id,
            activity=command.activity,
            record_time=RecordTime(command.activity_date, command.activity_time),
        )

    def _record(self, user_id: int, activity: Activity, record_time: RecordTime) -> RecordActivityResult:
        logical_day = record_time.date
        replaced_existing = self._records.find(user_id, activity, logical_day) is not None
        record = Record(
            activity=activity,
            user_id=user_id,
            time=record_time,
        )
        self._records.save(record)
        return RecordActivityResult(record=record, replaced_existing=replaced_existing)
