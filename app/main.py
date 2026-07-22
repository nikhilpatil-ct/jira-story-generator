import csv
import io
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents import drafter, orchestrator, story_actions, summarizer, validator
from app.config import settings
from app.formatting import format_jira_results_reply, format_stories_reply, summarize_stories
from app.models.schemas import GeneratedStory, IssueType, JiraBug, JiraEpic, OrchestratorAction
from app.pipeline import generate_stories
from app.services import app_context, clarification_store, db, file_parser, jira_client, session_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

app = FastAPI(title="AI JIRA Story Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    count = app_context.seed_catalog()
    logging.getLogger(__name__).info("Seeded app knowledge catalog: %d application(s)", count)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    auto_create_jira: bool = False


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    stage: str
    stories: list[dict] = []
    jira_results: list[dict] = []


class SessionPatchRequest(BaseModel):
    title: str | None = None
    favorite: bool | None = None


class StoryActionRequest(BaseModel):
    action: str
    instructions: str | None = None


class JiraRetryRequest(BaseModel):
    session_id: str
    index: int


class ClarifyAnswerRequest(BaseModel):
    group_id: str
    answers: dict[str, str] = {}
    skip: bool = False


def _session_dict(state: session_store.SessionState) -> dict:
    return {
        "id": state.id,
        "title": state.title,
        "favorite": state.favorite,
        "stage": state.stage,
        "current_step": state.current_step,
        "transcript": "\n\n".join(state.raw_text_parts),
        "transcript_clean": state.transcript_clean,
        "history": state.history,
        "stories": [gs.model_dump(mode="json") for gs in state.stories],
        "open_questions": state.open_questions,
        "action_items": state.action_items,
        "risks": state.risks,
        "jira_results": state.jira_results,
        "logs": state.logs,
        "summary": state.summary,
        # Live, in-memory view of any per-item clarifying questions a drafting run is currently waiting on.
        # Ephemeral (not stored in the DB) — the poller reads it here to render the answer forms mid-run.
        "pending_questions": clarification_store.pending_view(state.id),
        "created_at": state.created_at,
        "updated_at": state.updated_at,
    }


def _log(state: session_store.SessionState, stage: str, message: str) -> None:
    state.logs.append({"stage": stage, "message": message, "ts": session_store.now_iso()})


def _find_created_epic_key(state: session_store.SessionState) -> str | None:
    """The JIRA key of this session's Epic, if one has already been created — used to link newly
    created Stories/Bugs under it."""
    for gs in state.stories:
        if isinstance(gs.story, JiraEpic):
            match = next((r for r in state.jira_results if r.get("id") == gs.id and r.get("key")), None)
            if match:
                return match["key"]
    return None


async def _create_in_jira(
    state: session_store.SessionState, items: list[GeneratedStory], log_prefix: str = "jira"
) -> list[dict]:
    """Create the given items in JIRA. Any Epic in the batch is created first; every non-Epic item is
    then linked as a child of that (or an already-created) Epic, so a generation run lands in JIRA as a
    connected Epic + Stories/Bugs hierarchy instead of flat, unrelated issues."""
    ordered = sorted(items, key=lambda gs: 0 if isinstance(gs.story, JiraEpic) else 1)
    epic_key = _find_created_epic_key(state)
    results: list[dict] = []
    for gs in ordered:
        story = gs.story
        try:
            if isinstance(story, JiraEpic):
                result = await jira_client.create_issue(story, test_cases=gs.test_cases)
                epic_key = result["key"]
                _log(state, log_prefix, f"Created epic {result['key']} for \"{story.summary}\"")
            else:
                result = await jira_client.create_issue(story, epic_key=epic_key, test_cases=gs.test_cases)
                note = f" (linked to epic {epic_key})" if epic_key else ""
                _log(state, log_prefix, f"Created {result['key']} for \"{story.summary}\"{note}")
            results.append({"id": gs.id, "summary": story.summary, **result})
        except jira_client.JiraError as exc:
            _log(state, log_prefix, f"FAILED to create \"{story.summary}\": {exc}")
            results.append({"id": gs.id, "summary": story.summary, "error": str(exc)})
    return results


async def _run_generation(
    state: session_store.SessionState, generation_scope: list[IssueType] | None, auto_create_jira: bool
) -> str:
    conversation_text = "\n\n".join(state.raw_text_parts)
    scope_txt = f" (scope: {', '.join(t.value for t in generation_scope)})" if generation_scope else ""
    session_store.append_log(state.id, "pipeline", f"Starting generation{scope_txt}")

    generated, extraction, cleaned = await generate_stories(state.id, conversation_text, generation_scope)

    # pipeline.generate_stories writes fine-grained log entries directly to the DB as it runs (so a
    # concurrent poller can see them mid-run); pick those up now before appending more in-memory, so
    # the eventual session_store.save(state) below doesn't clobber them.
    state.logs = session_store.get(state.id).logs

    if generation_scope:
        kept = [gs for gs in state.stories if gs.story.issue_type not in generation_scope]
        state.stories = kept + generated
    else:
        state.stories = generated

    state.transcript_clean = cleaned
    state.open_questions = extraction.open_questions
    state.action_items = extraction.action_items
    state.risks = extraction.risks
    state.stage = "reviewing"

    held_note = ""
    if auto_create_jira:
        if settings.jira_configured:
            # Gate auto-creation on quality: items that clear the bar are pushed automatically; the rest are
            # held back for a BA to review and update, then create manually (via the Create button / "create
            # these in JIRA"). This only affects AUTO-create — manual creation of a weak item is still allowed.
            bar = settings.auto_create_min_score
            to_create = [gs for gs in generated if gs.validation.score >= bar]
            held = [gs for gs in generated if gs.validation.score < bar]
            _log(state, "jira", f"Auto-create is on — creating {len(to_create)} item(s) meeting the quality bar (score >= {bar})")
            for gs in held:
                state.jira_results = [r for r in state.jira_results if r.get("id") != gs.id]
                reason = (
                    f"Held for manual review: quality score {gs.validation.score}/100 is below the auto-create "
                    f"threshold of {bar}. A BA should review and update it before creating it in JIRA."
                )
                state.jira_results.append(
                    {"id": gs.id, "summary": gs.story.summary, "held_for_review": True, "reason": reason}
                )
                _log(state, "jira", f"Held \"{gs.story.summary}\" (score {gs.validation.score}/100) for BA review — not auto-created")
            to_create_ids = {gs.id for gs in to_create}
            state.jira_results = [r for r in state.jira_results if r.get("id") not in to_create_ids]
            state.jira_results.extend(await _create_in_jira(state, to_create))
            if held:
                held_list = ", ".join(f"\"{gs.story.summary}\" ({gs.validation.score}/100)" for gs in held)
                held_note = (
                    f"\n\n⚠️ {len(held)} item(s) scored below the auto-create quality bar ({bar}) and were NOT "
                    f"created — a BA should review and update them, then create them manually: {held_list}"
                )
        else:
            _log(state, "jira", "Auto-create is on, but JIRA is not configured — skipping")

    _log(state, "pipeline", f"Generated {len(generated)} item(s)")
    state.summary = await summarizer.summarize(
        state.stories, state.risks, state.open_questions, state.action_items
    )
    return format_stories_reply(state.stories, state.open_questions) + held_note


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
async def get_config() -> dict:
    return {
        "jira_configured": settings.jira_configured,
        "jira_project_key": settings.jira_project_key,
        "model": settings.anthropic_model,
    }


@app.get("/api/sessions")
async def list_sessions() -> list[dict]:
    return session_store.list_sessions()


@app.post("/api/sessions")
async def create_session() -> dict:
    state = session_store.create()
    return _session_dict(state)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    state = session_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_dict(state)


@app.patch("/api/sessions/{session_id}")
async def patch_session(session_id: str, req: SessionPatchRequest) -> dict:
    state = session_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if req.title is not None:
        session_store.rename(session_id, req.title)
        state.title = req.title
    if req.favorite is not None:
        session_store.set_favorite(session_id, req.favorite)
        state.favorite = req.favorite
    return _session_dict(state)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    session_store.delete(session_id)
    return {"status": "deleted"}


@app.post("/api/reset")
async def reset_session(session_id: str) -> dict:
    session_store.reset(session_id)
    return {"status": "reset"}


@app.post("/api/upload")
async def upload_file(file: UploadFile) -> dict:
    content = await file.read()
    try:
        text = file_parser.extract_text(file.filename or "upload.txt", content)
    except file_parser.FileParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"text": text}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    state = session_store.get_or_create(req.session_id)
    state.history.append({"role": "user", "content": req.message})

    try:
        stories_summary = summarize_stories(state.stories) if state.stories else None
        decision = await orchestrator.decide_next_action(
            stage=state.stage, history=state.history, stories_summary=stories_summary
        )

        reply = decision.message_to_user
        jira_results: list[dict] = []

        if state.stage == "gathering":
            state.raw_text_parts.append(req.message)
            if decision.action == OrchestratorAction.READY_TO_GENERATE:
                reply = await _run_generation(state, decision.generation_scope, req.auto_create_jira)

        elif state.stage == "reviewing":
            if decision.action == OrchestratorAction.CONFIRM_CREATE:
                already_created = {r["id"] for r in state.jira_results if r.get("key")}
                to_create = [gs for gs in state.stories if gs.id not in already_created]
                jira_results = [r for r in state.jira_results if r.get("key")]
                if len(to_create) < len(state.stories):
                    _log(state, "jira", f"Skipping {len(state.stories) - len(to_create)} item(s) already created in JIRA")
                _log(state, "jira", f"Creating {len(to_create)} item(s) in JIRA project {settings.jira_project_key}")
                jira_results = jira_results + await _create_in_jira(state, to_create)
                state.jira_results = jira_results
                state.stage = "done"
                reply = format_jira_results_reply(jira_results)

            elif decision.action == OrchestratorAction.REVISE and decision.target_story_index is not None:
                idx = decision.target_story_index
                if 0 <= idx < len(state.stories):
                    current = state.stories[idx]
                    new_story = await drafter.refine(current.story, decision.revision_instructions or req.message)
                    new_validation = await validator.validate(new_story)
                    state.stories[idx] = GeneratedStory(
                        id=current.id,
                        story=new_story,
                        validation=new_validation,
                        attempts=current.attempts + 1,
                        test_cases=current.test_cases,
                        risks=current.risks,
                    )
                    reply = (
                        f"Updated item {idx + 1}.\n\n"
                        f"{format_stories_reply(state.stories, state.open_questions)}"
                    )

            elif decision.action == OrchestratorAction.REGENERATE:
                reply = await _run_generation(state, decision.generation_scope, req.auto_create_jira)

        state.history.append({"role": "assistant", "content": reply})
        session_store.save(state)

        return ChatResponse(
            session_id=state.id,
            reply=reply,
            stage=state.stage,
            stories=[gs.model_dump(mode="json") for gs in state.stories],
            jira_results=jira_results or state.jira_results,
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the chat client
        session_store.save(state)
        raise HTTPException(status_code=502, detail=f"Story generator error: {exc}") from exc


@app.post("/api/clarify/{session_id}")
async def submit_clarification(session_id: str, req: ClarifyAnswerRequest) -> dict:
    """Answer (or skip) one item's clarifying questions, resuming the draft that is waiting on them.

    The drafting run lives in the still-open POST /api/chat request; this call just fills the answers and
    releases that item's wait, so it does not itself return the drafted story — the chat request does, once
    every item has been drafted.
    """
    ok = clarification_store.submit(session_id, req.group_id, req.answers, req.skip)
    if not ok:
        raise HTTPException(status_code=409, detail="No pending clarification for this item (it may have already proceeded)")
    state = session_store.get(session_id)
    if state is not None:
        answered = len([v for v in req.answers.values() if v and v.strip()])
        verb = "Skipped" if req.skip else f"Answered {answered}"
        session_store.append_log(session_id, "clarifying", f"{verb} clarification question(s) for item {int(req.group_id) + 1}")
    return {"status": "ok"}


@app.post("/api/stories/{session_id}/{index}/action")
async def story_action(session_id: str, index: int, req: StoryActionRequest) -> dict:
    state = session_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not (0 <= index < len(state.stories)):
        raise HTTPException(status_code=404, detail="Item not found")

    current = state.stories[index]

    try:
        if req.action == "improve_wording":
            new_story = await drafter.refine(current.story, story_actions.IMPROVE_WORDING_FEEDBACK)
            new_validation = await validator.validate(new_story)
            state.stories[index] = GeneratedStory(
                id=current.id,
                story=new_story,
                validation=new_validation,
                attempts=current.attempts + 1,
                test_cases=current.test_cases,
                risks=current.risks,
            )
        elif req.action == "expand_ac":
            new_story = await drafter.refine(current.story, story_actions.EXPAND_AC_FEEDBACK)
            new_validation = await validator.validate(new_story)
            state.stories[index] = GeneratedStory(
                id=current.id,
                story=new_story,
                validation=new_validation,
                attempts=current.attempts + 1,
                test_cases=current.test_cases,
                risks=current.risks,
            )
        elif req.action == "custom":
            instructions = (req.instructions or "").strip()
            if not instructions:
                raise HTTPException(status_code=400, detail="A prompt describing what to change is required")
            new_story = await drafter.refine(current.story, instructions)
            new_validation = await validator.validate(new_story)
            state.stories[index] = GeneratedStory(
                id=current.id,
                story=new_story,
                validation=new_validation,
                attempts=current.attempts + 1,
                test_cases=current.test_cases,
                risks=current.risks,
            )
        elif req.action == "regenerate":
            feedback = req.instructions or "Rewrite this item with a fresh take, keeping the same intent."
            new_story = await drafter.refine(current.story, feedback)
            new_validation = await validator.validate(new_story)
            state.stories[index] = GeneratedStory(
                id=current.id,
                story=new_story,
                validation=new_validation,
                attempts=current.attempts + 1,
                test_cases=current.test_cases,
                risks=current.risks,
            )
        elif req.action == "generate_test_cases":
            result = await story_actions.generate_test_cases(current.story)
            state.stories[index] = GeneratedStory(
                id=current.id,
                story=current.story,
                validation=current.validation,
                attempts=current.attempts,
                test_cases=result.test_cases,
                risks=current.risks,
            )
        elif req.action == "risk_analysis":
            result = await story_actions.analyze_risks(current.story)
            state.stories[index] = GeneratedStory(
                id=current.id,
                story=current.story,
                validation=current.validation,
                attempts=current.attempts,
                test_cases=current.test_cases,
                risks=result.risks,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Action failed: {exc}") from exc

    session_store.save(state)
    return state.stories[index].model_dump(mode="json")


@app.get("/api/sessions/{session_id}/jira-preview/{index}")
async def jira_preview(session_id: str, index: int) -> dict:
    state = session_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not (0 <= index < len(state.stories)):
        raise HTTPException(status_code=404, detail="Item not found")
    if not settings.jira_configured:
        raise HTTPException(status_code=400, detail="JIRA is not configured")
    gs = state.stories[index]
    story = gs.story
    epic_key = None if isinstance(story, JiraEpic) else _find_created_epic_key(state)
    return jira_client.build_fields(story, epic_key=epic_key, test_cases=gs.test_cases)


@app.post("/api/jira/retry")
async def jira_retry(req: JiraRetryRequest) -> dict:
    """Create the item in JIRA, or update the existing issue in place if it was already created."""
    state = session_store.get(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not (0 <= req.index < len(state.stories)):
        raise HTTPException(status_code=404, detail="Item not found")

    gs = state.stories[req.index]
    story = gs.story
    existing = next((r for r in state.jira_results if r.get("id") == gs.id and r.get("key")), None)

    try:
        if existing:
            _log(state, "jira", f"Updating {existing['key']} with latest changes: \"{story.summary}\"")
            result = await jira_client.update_issue(existing["key"], story, test_cases=gs.test_cases)
            entry = {"id": gs.id, "summary": story.summary, **result}
            _log(state, "jira", f"Updated {result['key']} for \"{story.summary}\"")
        else:
            epic_key = None if isinstance(story, JiraEpic) else _find_created_epic_key(state)
            link_note = f" (linking to epic {epic_key})" if epic_key else ""
            _log(state, "jira", f"Creating {story.issue_type.value} in JIRA: \"{story.summary}\"{link_note}")
            result = await jira_client.create_issue(story, epic_key=epic_key, test_cases=gs.test_cases)
            entry = {"id": gs.id, "summary": story.summary, **result}
            _log(state, "jira", f"Created {result['key']} for \"{story.summary}\"")
    except jira_client.JiraError as exc:
        verb = "update" if existing else "create"
        entry = {"id": gs.id, "summary": story.summary, "error": str(exc)}
        _log(state, "jira", f"FAILED to {verb} \"{story.summary}\": {exc}")

    results = [r for r in state.jira_results if r.get("id") != gs.id]
    results.append(entry)
    state.jira_results = results
    session_store.save(state)
    return entry


def _stories_to_csv(stories: list[GeneratedStory]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["Type", "Summary", "Priority", "Story Points", "Description", "Details", "Score", "Valid"]
    )
    for gs in stories:
        s = gs.story
        if isinstance(s, JiraEpic):
            details = f"Goal: {s.goal} | Value: {s.business_value} | Success: {'; '.join(s.success_criteria)}"
        elif isinstance(s, JiraBug):
            details = (
                f"Steps: {'; '.join(s.steps_to_reproduce)} | Expected: {s.expected_result} | "
                f"Actual: {s.actual_result} | Severity: {s.severity.value}"
            )
        else:
            details = f"{s.user_story} | AC: {'; '.join(s.acceptance_criteria)}"
        writer.writerow(
            [
                s.issue_type.value,
                s.summary,
                s.priority.value,
                getattr(s, "story_points", "") or "",
                s.description,
                details,
                gs.validation.score,
                gs.validation.is_valid,
            ]
        )
    return buf.getvalue()


def _stories_to_markdown(stories: list[GeneratedStory]) -> str:
    lines = ["# Generated JIRA Items\n"]
    for i, gs in enumerate(stories):
        s = gs.story
        lines.append(f"## {i + 1}. {s.summary} [{s.issue_type.value}]")
        lines.append(f"- Priority: {s.priority.value}")
        story_points = getattr(s, "story_points", None)
        if story_points is not None:
            lines.append(f"- Story points: {story_points}")
        lines.append(f"- Quality score: {gs.validation.score}/100\n")
        if s.description:
            lines.append(s.description + "\n")
        if isinstance(s, JiraEpic):
            lines.append(f"**Goal:** {s.goal}\n\n**Business value:** {s.business_value}\n")
            if s.success_criteria:
                lines.append("**Success criteria:**")
                lines += [f"- {c}" for c in s.success_criteria]
        elif isinstance(s, JiraBug):
            if s.steps_to_reproduce:
                lines.append("**Steps to reproduce:**")
                lines += [f"{i + 1}. {step}" for i, step in enumerate(s.steps_to_reproduce)]
            lines.append(f"\n**Expected:** {s.expected_result}\n\n**Actual:** {s.actual_result}\n")
            lines.append(f"**Severity:** {s.severity.value}\n")
        else:
            if s.user_story:
                lines.append(f"> {s.user_story}\n")
            if s.acceptance_criteria:
                lines.append("**Acceptance criteria:**")
                lines += [f"- {ac}" for ac in s.acceptance_criteria]
        lines.append("")
    return "\n".join(lines)


@app.get("/api/export/{session_id}")
async def export_session(session_id: str, format: str = "json") -> PlainTextResponse:
    state = session_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if format == "json":
        import json

        body = json.dumps([gs.model_dump(mode="json") for gs in state.stories], indent=2)
        media_type, ext = "application/json", "json"
    elif format == "csv":
        body = _stories_to_csv(state.stories)
        media_type, ext = "text/csv", "csv"
    elif format == "markdown":
        body = _stories_to_markdown(state.stories)
        media_type, ext = "text/markdown", "md"
    else:
        raise HTTPException(status_code=400, detail="format must be json, csv, or markdown")

    return PlainTextResponse(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="jira-items.{ext}"'},
    )


# Serve the built React app (run `npm run build` in frontend/ first). Registered last so it
# doesn't shadow the /api and /health routes above; falls back to a 404 if not built yet.
app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIST), html=True, check_dir=False),
    name="frontend",
)
