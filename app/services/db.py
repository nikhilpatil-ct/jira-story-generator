import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
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

-- Maps a known application (by name/aliases) to the knowledge file that describes it. Populated at
-- startup from the knowledge/ directory; the pipeline uses it to inject app context while drafting.
CREATE TABLE IF NOT EXISTS app_catalog (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def sync_app_catalog(entries: list[dict]) -> None:
    """Replace the app_catalog mapping with `entries` (each: key, name, aliases, description, file_path).

    Upserts every entry and prunes any rows whose knowledge file no longer exists, so the DB mapping
    always mirrors the knowledge/ directory on disk.
    """
    keys = [e["key"] for e in entries]
    with get_conn() as conn:
        for e in entries:
            conn.execute(
                """
                INSERT INTO app_catalog (key, name, aliases, description, file_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    name=excluded.name, aliases=excluded.aliases, description=excluded.description,
                    file_path=excluded.file_path, updated_at=excluded.updated_at
                """,
                (e["key"], e["name"], json.dumps(e["aliases"]), e.get("description", ""), e["file_path"], _now()),
            )
        if keys:
            placeholders = ",".join("?" for _ in keys)
            conn.execute(f"DELETE FROM app_catalog WHERE key NOT IN ({placeholders})", keys)
        else:
            conn.execute("DELETE FROM app_catalog")


def all_apps() -> list[dict]:
    """Return the app_catalog mapping, name-sorted."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT key, name, aliases, description, file_path FROM app_catalog ORDER BY name"
        ).fetchall()
    return [
        {
            "key": r["key"],
            "name": r["name"],
            "aliases": json.loads(r["aliases"]),
            "description": r["description"],
            "file_path": r["file_path"],
        }
        for r in rows
    ]


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
