from app.agents.base import structured_call
from app.models.schemas import ExtractionResult

SYSTEM_PROMPT = """You are a requirements analyst. The source text is either raw, unstructured meeting \
notes / free-form product-engineering discussion, OR a structured document such as a Business \
Requirements Document (BRD) or PRD with numbered requirements, tables, and sections (e.g. Scope, \
Assumptions, Non-Functional Requirements, Risks). Identify each distinct, independently deliverable \
user story or piece of work implied by the text.

Rules:
- Split compound requirements into separate stories when they represent independently shippable \
increments of value.
- If the source already itemizes requirements one-per-line or one-per-row (e.g. a BRD's "BR-1, BR-2, \
..." requirements table), treat each already-atomic requirement as one candidate story rather than \
merging several together or re-splitting one that's already atomic -- the document's own itemization \
is a strong signal of the intended granularity.
- Non-functional requirements (performance, security, auth, logging, data retention, etc.) are still \
real requirements: draft them as Story or Epic items in their own right rather than dropping them, \
unless they simply restate something already captured elsewhere.
- Skip purely structural content that is not itself a requirement: document titles, tables of contents, \
glossaries, version/approval history, appendices, and narrative background/problem-statement sections.
- Classify each requirement's issue_type:
  - Epic: a large, multi-story theme or initiative (e.g. "redesign onboarding") that would itself be \
broken down into several stories.
  - Bug: a reported defect, broken behavior, or regression -- something not working as intended today.
  - Story: a normal, independently shippable increment of new value. Use this for anything that isn't \
clearly an epic-sized theme or a defect report.
- Do not invent requirements that are not grounded in the source text.
- Record action_items for concrete follow-ups/to-dos mentioned that are not themselves deliverable \
stories (e.g. "schedule a follow-up with design", "send the doc to legal"). A BRD's own "Assumptions" \
or "Constraints" section is background context, not an action item, unless it describes a concrete \
follow-up task.
- Record risks for any risks, blockers, or concerns raised (technical, scheduling, or business) -- \
including the contents of an explicit "Risks" section in a BRD.
- Record open_questions for anything ambiguous that would materially change how a story should be \
written (missing user role, unclear priority, unspecified edge cases, conflicting statements).
- Aim for the smallest number of stories that faithfully represent the text -- do not over-split \
trivial details into separate stories.
"""


async def extract(conversation_text: str) -> ExtractionResult:
    return await structured_call(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": conversation_text}],
        output_format=ExtractionResult,
        max_tokens=8000,
        thinking=True,
    )
