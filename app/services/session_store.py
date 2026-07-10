import uuid
from dataclasses import dataclass, field

from app.models.schemas import GeneratedStory


@dataclass
class SessionState:
    id: str
    stage: str = "gathering"
    history: list[dict] = field(default_factory=list)
    raw_text_parts: list[str] = field(default_factory=list)
    stories: list[GeneratedStory] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    jira_results: list[dict] = field(default_factory=list)


_sessions: dict[str, SessionState] = {}


def get_or_create(session_id: str | None) -> SessionState:
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    new_id = session_id or str(uuid.uuid4())
    state = SessionState(id=new_id)
    _sessions[new_id] = state
    return state


def reset(session_id: str) -> None:
    _sessions.pop(session_id, None)
