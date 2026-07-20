"""SQLite persistence: rate cache, media-group buffer, message map."""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_cache (
    key TEXT PRIMARY KEY,
    value REAL NOT NULL,
    fetched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS message_map (
    source_chat_id INTEGER NOT NULL,
    source_message_id INTEGER NOT NULL,
    dest_chat_id INTEGER NOT NULL,
    dest_message_id INTEGER NOT NULL,
    PRIMARY KEY (source_chat_id, source_message_id)
);
"""


def init() -> None:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_cached_rate(key: str, ttl_seconds: int) -> float | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT value, fetched_at FROM rate_cache WHERE key = ?", (key,)
        ).fetchone()
    if not row:
        return None
    if time.time() - row["fetched_at"] > ttl_seconds:
        return None
    return row["value"]


def set_cached_rate(key: str, value: float) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO rate_cache (key, value, fetched_at) VALUES (?, ?, ?)",
            (key, value, int(time.time())),
        )


def get_last_rate(key: str) -> float | None:
    """Return last known rate ignoring TTL (fallback when fetch fails)."""
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM rate_cache WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else None


def record_message_map(source_chat: int, source_msg: int, dest_chat: int, dest_msg: int) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO message_map "
            "(source_chat_id, source_message_id, dest_chat_id, dest_message_id) VALUES (?, ?, ?, ?)",
            (source_chat, source_msg, dest_chat, dest_msg),
        )


def lookup_dest(source_chat: int, source_msg: int) -> tuple[int, int] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT dest_chat_id, dest_message_id FROM message_map "
            "WHERE source_chat_id = ? AND source_message_id = ?",
            (source_chat, source_msg),
        ).fetchone()
    return (row["dest_chat_id"], row["dest_message_id"]) if row else None
