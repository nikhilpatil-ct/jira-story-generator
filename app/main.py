from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents import drafter, orchestrator, validator
from app.formatting import format_jira_results_reply, format_stories_reply, summarize_stories
from app.models.schemas import GeneratedStory, OrchestratorAction
from app.pipeline import generate_stories
from app.services import jira_client, session_store

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

app = FastAPI(title="AI JIRA Story Generator")

# Allow the Vite dev server to call the API directly (in addition to its own
# built-in proxy) so `npm run dev` works even if the proxy config changes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    stage: str
    stories: list[dict] = []
    jira_results: list[dict] = []


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/reset")
async def reset_session(session_id: str) -> dict:
    session_store.reset(session_id)
    return {"status": "reset"}


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
                conversation_text = "\n\n".join(state.raw_text_parts)
                generated, open_questions = await generate_stories(conversation_text)
                state.stories = generated
                state.open_questions = open_questions
                state.stage = "reviewing"
                reply = format_stories_reply(generated, open_questions)

        elif state.stage == "reviewing":
            if decision.action == OrchestratorAction.CONFIRM_CREATE:
                for gs in state.stories:
                    try:
                        result = await jira_client.create_issue(gs.story)
                        jira_results.append({"summary": gs.story.summary, **result})
                    except jira_client.JiraError as exc:
                        jira_results.append({"summary": gs.story.summary, "error": str(exc)})
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
                        story=new_story, validation=new_validation, attempts=current.attempts + 1
                    )
                    reply = (
                        f"Updated story {idx + 1}.\n\n"
                        f"{format_stories_reply(state.stories, state.open_questions)}"
                    )

        state.history.append({"role": "assistant", "content": reply})

        return ChatResponse(
            session_id=state.id,
            reply=reply,
            stage=state.stage,
            stories=[gs.model_dump(mode="json") for gs in state.stories],
            jira_results=jira_results or state.jira_results,
        )
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the chat client
        raise HTTPException(status_code=502, detail=f"Story generator error: {exc}") from exc


# Serve the built React app (run `npm run build` in frontend/ first). Registered last so it
# doesn't shadow the /api and /health routes above; falls back to a 404 if not built yet.
app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIST), html=True, check_dir=False),
    name="frontend",
)
