import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.schemas import GeneratedStory
from app.services import db


@dataclass
class SessionState:
    id: str
    title: str = "Untitled session"
    favorite: bool = False
    stage: str = "gathering"
    current_step: str = "idle"
    history: list[dict] = field(default_factory=list)
    raw_text_parts: list[str] = field(default_factory=list)
    transcript_clean: str = ""
    stories: list[GeneratedStory] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    jira_results: list[dict] = field(default_factory=list)
    logs: list[dict] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""
    updated_at: str = ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_now = now_iso


def _row_to_state(row: dict) -> SessionState:
    return SessionState(
        id=row["id"],
        title=row["title"],
        favorite=row["favorite"],
        stage=row["stage"],
        current_step=row["current_step"],
        history=row["history"],
        raw_text_parts=row["transcript_raw"],
        transcript_clean=row["transcript_clean"],
        stories=[GeneratedStory.model_validate(s) for s in row["stories"]],
        open_questions=row["open_questions"],
        action_items=row["action_items"],
        risks=row["risks"],
        jira_results=row["jira_results"],
        logs=row["logs"],
        summary=row["summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create(title: str | None = None) -> SessionState:
    now = _now()
    state = SessionState(id=str(uuid.uuid4()), title=title or "New session", created_at=now, updated_at=now)
    save(state)
    return state


def get(session_id: str) -> SessionState | None:
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    return _row_to_state(db.row_to_dict(row))


def get_or_create(session_id: str | None) -> SessionState:
    if session_id:
        existing = get(session_id)
        if existing is not None:
            return existing
        now = _now()
        state = SessionState(id=session_id, created_at=now, updated_at=now)
        save(state)
        return state
    return create()


def save(state: SessionState) -> None:
    state.updated_at = _now()
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                id, title, favorite, stage, current_step, transcript_raw, transcript_clean,
                history, stories, open_questions, action_items, risks, jira_results, logs,
                summary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, favorite=excluded.favorite, stage=excluded.stage,
                current_step=excluded.current_step, transcript_raw=excluded.transcript_raw,
                transcript_clean=excluded.transcript_clean, history=excluded.history,
                stories=excluded.stories, open_questions=excluded.open_questions,
                action_items=excluded.action_items, risks=excluded.risks,
                jira_results=excluded.jira_results, logs=excluded.logs, summary=excluded.summary,
                updated_at=excluded.updated_at
            """,
            (
                state.id,
                state.title,
                int(state.favorite),
                state.stage,
                state.current_step,
                json.dumps(state.raw_text_parts),
                state.transcript_clean,
                json.dumps(state.history),
                json.dumps([s.model_dump(mode="json") for s in state.stories]),
                json.dumps(state.open_questions),
                json.dumps(state.action_items),
                json.dumps(state.risks),
                json.dumps(state.jira_results),
                json.dumps(state.logs),
                state.summary,
                state.created_at,
                state.updated_at,
            ),
        )


def update_step(session_id: str, step: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET current_step = ?, updated_at = ? WHERE id = ?",
            (step, _now(), session_id),
        )


def append_log(session_id: str, stage: str, message: str) -> None:
    """Append one log entry directly in the DB, so a concurrent poller sees it mid-pipeline-run."""
    with db.get_conn() as conn:
        row = conn.execute("SELECT logs FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return
        logs = json.loads(row["logs"])
        logs.append({"stage": stage, "message": message, "ts": now_iso()})
        conn.execute(
            "UPDATE sessions SET logs = ?, updated_at = ? WHERE id = ?",
            (json.dumps(logs), now_iso(), session_id),
        )


def list_sessions() -> list[dict]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
    result = []
    for row in rows:
        d = db.row_to_dict(row)
        result.append(
            {
                "id": d["id"],
                "title": d["title"],
                "favorite": d["favorite"],
                "stage": d["stage"],
                "story_count": len(d["stories"]),
                "created_at": d["created_at"],
                "updated_at": d["updated_at"],
            }
        )
    return result


def rename(session_id: str, title: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?", (title, _now(), session_id)
        )


def set_favorite(session_id: str, favorite: bool) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET favorite = ?, updated_at = ? WHERE id = ?",
            (int(favorite), _now(), session_id),
        )


def delete(session_id: str) -> None:
    with db.get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def reset(session_id: str) -> None:
    delete(session_id)
