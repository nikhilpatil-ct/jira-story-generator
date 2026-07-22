"""In-memory registry that lets concurrently-drafting pipeline coroutines pause and ask the user questions.

The whole app runs on a single asyncio event loop (one uvicorn worker), so a plain module-level dict plus
per-group ``asyncio.Event`` is enough to coordinate across requests: the still-open ``/api/chat`` request
holds the drafting coroutines (each awaiting its group's event), the poller reads pending groups via
``pending_view`` on ``GET /api/sessions/{id}``, and ``/api/clarify`` calls ``submit`` to fill answers and
set the event, which immediately resumes the matching draft.

This state is intentionally ephemeral — questions in flight are lost on restart, exactly like the rest of an
in-progress pipeline run. Nothing here is persisted to the DB.
"""

import asyncio
from dataclasses import dataclass, field

# Question groups are keyed session_id -> group_id. There is one group per drafted item; group_id is the
# item's stable index within the requirement list (as a string), which is also how it is numbered to the user.
_registry: dict[str, dict[str, "_Group"]] = {}


@dataclass
class _Group:
    session_id: str
    group_id: str
    item_index: int
    item_title: str
    issue_type: str
    questions: list[dict]  # each: {"id": str, "question": str, "reason": str}
    event: asyncio.Event
    answers: dict[str, str] = field(default_factory=dict)  # question_id -> answer text
    status: str = "pending"  # pending | answered | skipped | timeout


def open_group(
    session_id: str,
    item_index: int,
    item_title: str,
    issue_type: str,
    questions: list[dict],
) -> "_Group":
    """Register a new pending question group for an item and return it (the caller then awaits it)."""
    group = _Group(
        session_id=session_id,
        group_id=str(item_index),
        item_index=item_index,
        item_title=item_title,
        issue_type=issue_type,
        questions=questions,
        event=asyncio.Event(),
    )
    _registry.setdefault(session_id, {})[group.group_id] = group
    return group


async def wait_for_answers(group: "_Group", timeout: float) -> str:
    """Block until the user answers/skips this group or ``timeout`` seconds pass. Returns the final status."""
    try:
        await asyncio.wait_for(group.event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        if group.status == "pending":
            group.status = "timeout"
    return group.status


def submit(session_id: str, group_id: str, answers: dict[str, str], skip: bool) -> bool:
    """Fill in answers (or mark skipped) and wake the waiting draft coroutine. False if no such pending group."""
    group = _registry.get(session_id, {}).get(group_id)
    if group is None or group.status != "pending":
        return False
    group.answers = {k: v for k, v in (answers or {}).items() if v and v.strip()}
    group.status = "skipped" if skip else "answered"
    group.event.set()
    return True


def answers_text(group: "_Group") -> str:
    """Format the answered questions as a grounding block for the drafter. Empty if nothing usable was given."""
    if group.status != "answered":
        return ""
    lines = []
    for q in group.questions:
        answer = group.answers.get(q["id"], "").strip()
        if answer:
            lines.append(f"- Q: {q['question']}\n  A: {answer}")
    return "\n".join(lines)


def pending_view(session_id: str) -> list[dict]:
    """The still-unanswered groups for a session, item-ordered — served to the frontend for rendering forms."""
    groups = _registry.get(session_id, {})
    pending = [g for g in groups.values() if g.status == "pending"]
    pending.sort(key=lambda g: g.item_index)
    return [
        {
            "group_id": g.group_id,
            "item_index": g.item_index,
            "item_title": g.item_title,
            "issue_type": g.issue_type,
            "questions": g.questions,
        }
        for g in pending
    ]


def clear_session(session_id: str) -> None:
    """Drop all groups for a session. Called when a fresh generation starts and when one finishes."""
    _registry.pop(session_id, None)
