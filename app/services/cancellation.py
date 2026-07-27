"""In-memory registry of in-flight generation tasks, so a separate request can stop one.

Like ``clarification_store``, this relies on the whole app running on a single asyncio event loop (one
uvicorn worker): the still-open ``POST /api/chat`` request registers its generation task here, and
``POST /api/generation/{id}/stop`` cancels it. Cancelling the task propagates ``asyncio.CancelledError``
through every ``await`` in the pipeline — in-flight LLM calls and clarification waits included — so a run
stops promptly instead of only at cooperative checkpoints. This state is ephemeral, exactly like the rest
of an in-progress run; nothing is persisted to the DB.
"""

import asyncio

# session_id -> the task currently running that session's generation.
_tasks: dict[str, asyncio.Task] = {}
# session_ids whose most recent cancellation was an explicit user stop (vs. e.g. a client disconnect),
# so the awaiter can tell a "user pressed Stop" apart from an unexpected cancellation.
_requested: set[str] = set()


def register(session_id: str, task: asyncio.Task) -> None:
    """Record the task running this session's generation, clearing any stale stop request for it."""
    _tasks[session_id] = task
    _requested.discard(session_id)


def request_stop(session_id: str) -> bool:
    """Cancel the active generation task for this session. Returns False if nothing is running."""
    task = _tasks.get(session_id)
    if task is None or task.done():
        return False
    _requested.add(session_id)
    task.cancel()
    return True


def was_requested(session_id: str) -> bool:
    """Whether the last cancellation for this session came from an explicit user stop."""
    return session_id in _requested


def is_running(session_id: str) -> bool:
    """Whether a generation run is currently in flight for this session."""
    task = _tasks.get(session_id)
    return task is not None and not task.done()


def unregister(session_id: str) -> None:
    """Forget a session's run once it has finished (or been stopped)."""
    _tasks.pop(session_id, None)
    _requested.discard(session_id)
