import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Untitled session',
    favorite INTEGER NOT NULL DEFAULT 0,
    stage TEXT NOT NULL DEFAULT 'gathering',
    current_step TEXT NOT NULL DEFAULT 'idle',
    transcript_raw TEXT NOT NULL DEFAULT '',
    transcript_clean TEXT NOT NULL DEFAULT '',
    history TEXT NOT NULL DEFAULT '[]',
    stories TEXT NOT NULL DEFAULT '[]',
    open_questions TEXT NOT NULL DEFAULT '[]',
    action_items TEXT NOT NULL DEFAULT '[]',
    risks TEXT NOT NULL DEFAULT '[]',
    jira_results TEXT NOT NULL DEFAULT '[]',
    logs TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for json_field in (
        "transcript_raw",
        "history",
        "stories",
        "open_questions",
        "action_items",
        "risks",
        "jira_results",
        "logs",
    ):
        d[json_field] = json.loads(d[json_field])
    d["favorite"] = bool(d["favorite"])
    return d
