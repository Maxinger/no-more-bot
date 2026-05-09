"""Repository contract for activity records."""

from __future__ import annotations

from typing import Protocol

from ddd.domain.record import Record


class RecordRepository(Protocol):
    def save(self, record: Record) -> None:
        raise NotImplementedError
