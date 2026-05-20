"""SQLite repository implementations for persistent bot data."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from pathlib import Path

from domain.ports import RecordRepository, WeekGoalRepository
from domain.record import Activity, Record, RecordTime, WeekStart
from domain.week_goal import WeekGoal

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    user_id INTEGER NOT NULL,
    activity TEXT NOT NULL,
    logical_date TEXT NOT NULL,
    time TEXT NOT NULL,
    PRIMARY KEY (user_id, activity, logical_date)
);

CREATE TABLE IF NOT EXISTS week_goals (
    user_id INTEGER NOT NULL,
    activity TEXT NOT NULL,
    week_start TEXT NOT NULL,
    target_time TEXT NOT NULL,
    PRIMARY KEY (user_id, activity, week_start)
);
"""


def _date_to_text(value: date) -> str:
    return value.isoformat()


def _time_to_text(value: time) -> str:
    return value.strftime("%H:%M")


def _parse_time(value: str) -> time:
    return time.fromisoformat(value)


@dataclass(frozen=True)
class SQLiteDatabase:
    """Small connection factory and schema owner for SQLite repositories."""

    path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        logger.info("Opening SQLite database at %s", self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def connection(self):
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_schema(self) -> None:
        logger.debug("Applying SQLite schema at %s", self.path)
        with self.connection() as connection:
            connection.executescript(SCHEMA)
        logger.info("SQLite schema ready at %s", self.path)

    def table_row_counts(self) -> tuple[int, int]:
        with self.connection() as connection:
            record_count = connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            goal_count = connection.execute("SELECT COUNT(*) FROM week_goals").fetchone()[0]
        return record_count, goal_count

    def main_tables_are_empty(self) -> bool:
        record_count, goal_count = self.table_row_counts()
        is_empty = record_count == 0 and goal_count == 0
        logger.info(
            "Database row counts: records=%d, week_goals=%d (empty=%s)",
            record_count,
            goal_count,
            is_empty,
        )
        return is_empty


@dataclass(frozen=True)
class SQLiteRecordRepository(RecordRepository):
    database: SQLiteDatabase

    def find(self, user_id: int, activity: Activity, date: date) -> Record | None:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT user_id, activity, logical_date, time
                FROM records
                WHERE user_id = ? AND activity = ? AND logical_date = ?
                """,
                (user_id, activity.value, _date_to_text(date)),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def find_for_week(
        self, user_id: int, activity: Activity, week: WeekStart
    ) -> tuple[Record, ...]:
        start = week.value
        end = start + timedelta(days=6)
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT user_id, activity, logical_date, time
                FROM records
                WHERE user_id = ?
                  AND activity = ?
                  AND logical_date BETWEEN ? AND ?
                ORDER BY logical_date ASC
                """,
                (
                    user_id,
                    activity.value,
                    _date_to_text(start),
                    _date_to_text(end),
                ),
            ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def find_all_for_user(self, user_id: int) -> tuple[Record, ...]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT user_id, activity, logical_date, time
                FROM records
                WHERE user_id = ?
                ORDER BY logical_date ASC, activity ASC
                """,
                (user_id,),
            ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def save(self, record: Record) -> None:
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO records (user_id, activity, logical_date, time)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, activity, logical_date)
                DO UPDATE SET time = excluded.time
                """,
                (
                    record.user_id,
                    record.activity.value,
                    _date_to_text(record.time.date),
                    _time_to_text(record.time.time),
                ),
            )

    @staticmethod
    def _row_to_record(row: tuple[int, str, str, str]) -> Record:
        return Record(
            user_id=row[0],
            activity=Activity(row[1]),
            time=RecordTime(date=date.fromisoformat(row[2]), time=_parse_time(row[3])),
        )


@dataclass(frozen=True)
class SQLiteWeekGoalRepository(WeekGoalRepository):
    database: SQLiteDatabase

    def find(self, user_id: int, activity: Activity, week: WeekStart) -> WeekGoal | None:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT user_id, activity, week_start, target_time
                FROM week_goals
                WHERE user_id = ? AND activity = ? AND week_start = ?
                """,
                (user_id, activity.value, _date_to_text(week.value)),
            ).fetchone()
        return self._row_to_goal(row) if row else None

    def find_all_for_user(self, user_id: int) -> tuple[WeekGoal, ...]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT user_id, activity, week_start, target_time
                FROM week_goals
                WHERE user_id = ?
                ORDER BY week_start ASC, activity ASC
                """,
                (user_id,),
            ).fetchall()
        return tuple(self._row_to_goal(row) for row in rows)

    def save(self, goal: WeekGoal) -> None:
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO week_goals (user_id, activity, week_start, target_time)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, activity, week_start)
                DO UPDATE SET target_time = excluded.target_time
                """,
                (
                    goal.user_id,
                    goal.activity.value,
                    _date_to_text(goal.week.value),
                    _time_to_text(goal.target_time),
                ),
            )

    @staticmethod
    def _row_to_goal(row: tuple[int, str, str, str]) -> WeekGoal:
        return WeekGoal(
            user_id=row[0],
            activity=Activity(row[1]),
            week=WeekStart(date.fromisoformat(row[2])),
            target_time=_parse_time(row[3]),
        )


@dataclass(frozen=True)
class SQLiteRepositories:
    """Composition helper for sharing SQLite-backed repositories."""

    path: Path

    def __post_init__(self) -> None:
        database = SQLiteDatabase(Path(self.path))
        object.__setattr__(self, "database", database)
        object.__setattr__(self, "records", SQLiteRecordRepository(database))
        object.__setattr__(self, "goals", SQLiteWeekGoalRepository(database))

    database: SQLiteDatabase = field(init=False)
    records: SQLiteRecordRepository = field(init=False)
    goals: SQLiteWeekGoalRepository = field(init=False)
