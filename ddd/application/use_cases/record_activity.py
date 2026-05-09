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


class RecordActivityUseCase(UseCase):
    def __init__(self, records: RecordRepository):
        self._records = records

    @handles(RecordActivityNowCommand)
    def _record_now(self, command: RecordActivityNowCommand) -> Record:
        return self._record(
            user_id=command.user_id,
            activity=command.activity,
            record_time=RecordTime.from_datetime(command.occurred_at),
        )

    @handles(RecordActivityForDayCommand)
    def _record_for_day(self, command: RecordActivityForDayCommand) -> Record:
        return self._record(
            user_id=command.user_id,
            activity=command.activity,
            record_time=RecordTime(command.activity_date, command.activity_time),
        )

    def _record(self, user_id: int, activity: Activity, record_time: RecordTime) -> Record:
        record = Record(
            activity=activity,
            user_id=user_id,
            time=record_time,
        )
        self._records.save(record)
        return record
