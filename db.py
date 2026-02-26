"""SQLite storage for NoMoreBot activity records."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "no-more.db"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Create the no_more table if it does not exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS no_more (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recorded_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_no_more_user_recorded "
            "ON no_more (user_id, recorded_at)"
        )


def record_event(user_id: int) -> datetime:
    """Insert an activity record with current UTC timestamp. Returns recorded_at."""
    now = datetime.utcnow()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO no_more (user_id, recorded_at, created_at) VALUES (?, ?, ?)",
            (user_id, now, now),
        )
    return now


def get_history(user_id: int, days: int = 14) -> list[datetime]:
    """Return activity records for the last N days, most recent first."""
    since = datetime.utcnow() - timedelta(days=days)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT recorded_at FROM no_more "
            "WHERE user_id = ? AND recorded_at >= ? ORDER BY recorded_at DESC",
            (user_id, since),
        ).fetchall()
    return [r[0] if isinstance(r[0], datetime) else datetime.fromisoformat(str(r[0])) for r in rows]
