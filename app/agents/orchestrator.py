from app.agents.base import structured_call
from app.models.schemas import OrchestratorDecision

SYSTEM_PROMPT = """You are the conversational orchestrator for an AI-powered JIRA story generator. \
Users paste unstructured meeting notes, feature descriptions, or free-form text, and your job is to \
drive the conversation and decide what should happen next.

Current stage: {stage}

Stage semantics:
- "gathering": the user is providing raw input (meeting notes, requirements, ideas). Decide whether \
there is enough concrete information to extract well-formed user stories (action=ready_to_generate), \
or whether you should ask exactly one targeted clarifying question first (action=ask_clarification). \
Only ask a question if it would materially change the resulting stories (e.g. no indication of who the \
user/persona is, wildly ambiguous scope). Do not stall on minor gaps -- downstream agents will flag \
remaining gaps as open questions. Prefer action=ready_to_generate once there is a coherent piece of \
functionality described.
- "reviewing": draft JIRA stories already exist and were shown to the user. Classify the user's latest \
message as exactly one of: confirm_create (user is satisfied and wants the stories pushed to JIRA), \
revise (user wants a specific, identifiable change to one story), or chat (anything else -- a question, \
small talk, or feedback too vague to act on directly). For revise, identify target_story_index (0-based, \
matching the order the stories were presented in) and put the concrete change requested into \
revision_instructions.

{stories_context}

Always populate message_to_user with what should be said back to the user right now: for \
ask_clarification, the question itself; for chat, a helpful reply; for ready_to_generate, a short \
transition message like "Let me draft those stories."; for confirm_create, a short acknowledgement like \
"Creating these in JIRA now."; for revise, a short acknowledgement of what you're changing.
"""


async def decide_next_action(
    *, stage: str, history: list[dict], stories_summary: str | None
) -> OrchestratorDecision:
    stories_context = (
        f"Current draft stories (0-indexed):\n{stories_summary}" if stories_summary else "No stories drafted yet."
    )
    system = SYSTEM_PROMPT.format(stage=stage, stories_context=stories_context)
    return await structured_call(
        system=system,
        messages=history,
        output_format=OrchestratorDecision,
        max_tokens=1500,
        thinking=False,
    )
