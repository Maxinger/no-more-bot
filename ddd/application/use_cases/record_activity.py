"""Use case for recording an activity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from ddd.application.use_case import UseCase, handles
from ddd.domain.ports import RecordRepository
from ddd.domain.record import Activity, Record, RecordTime
from ddd.domain.user import User


@dataclass(frozen=True)
class RecordActivityNowCommand:
    user: User
    activity: Activity
    occurred_at: datetime


@dataclass(frozen=True)
class RecordActivityForDayCommand:
    user: User
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
            user=command.user,
            activity=command.activity,
            record_time=RecordTime.from_datetime(
                command.occurred_at, command.user.time_zone
            ),
        )

    @handles(RecordActivityForDayCommand)
    def _record_for_day(
        self, command: RecordActivityForDayCommand
    ) -> RecordActivityResult:
        return self._record(
            user=command.user,
            activity=command.activity,
            record_time=RecordTime(command.activity_date, command.activity_time),
        )

    def _record(
        self, user: User, activity: Activity, record_time: RecordTime
    ) -> RecordActivityResult:
        logical_day = record_time.date
        replaced_existing = self._records.find(user.id, activity, logical_day) is not None
        record = Record(
            activity=activity,
            user_id=user.id,
            time=record_time,
        )
        self._records.save(record)
        return RecordActivityResult(record=record, replaced_existing=replaced_existing)
