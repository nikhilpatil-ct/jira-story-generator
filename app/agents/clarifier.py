from app.agents.base import structured_call
from app.config import settings
from app.models.schemas import ClarificationCheck, ClarifyingQuestionDraft, ExtractedRequirement, IssueType

# Runs once per requirement, right before it is drafted. Its only job is to prevent hallucination: surface
# the specific missing facts the drafter would otherwise have to invent. It is heavily biased toward asking
# NOTHING — a false question is more annoying than a small, safe assumption.
CLARIFIER_SYSTEM_PROMPT = """You are a meticulous business analyst reviewing ONE extracted requirement just \
before it is turned into a JIRA {issue_type}. Your sole purpose is to prevent hallucination: identify only \
the specific facts you would otherwise have to INVENT to write this item accurately.

Ask a clarifying question ONLY when ALL of these hold:
- The detail is genuinely absent from (or contradictory in) both the source text AND the provided app context.
- Without it, drafting forces you to fabricate a concrete specific — a number, a name, a user role, an \
integration, a business rule, an environment, or an expected value.
- Knowing it would materially change the resulting item, not merely polish its wording.

Never ask about:
- Anything already stated in, or reasonably inferable from, the source text or app context.
- Generic best-practice details a reader can safely assume.
- Nice-to-have polish, tone, or formatting.

Strongly prefer asking NOTHING and returning an empty list. When you must ask, return at most {max_questions} \
question(s). Each must be a single, concrete, self-contained question that a non-technical stakeholder could \
answer in one sentence, plus a short 'reason' naming exactly which part of the item it affects.
"""


async def clarify(
    requirement: ExtractedRequirement, context: str, app_context: str = ""
) -> list[ClarifyingQuestionDraft]:
    """Return the minimal set of must-ask questions for this requirement, or [] if none are needed."""
    issue_type = requirement.issue_type if requirement.issue_type in (
        IssueType.EPIC,
        IssueType.STORY,
        IssueType.BUG,
    ) else IssueType.STORY

    app_block = ""
    if app_context:
        app_block = (
            "Known application context (business flow, use cases, design, tech stack). Treat anything "
            "answered here as already known — do NOT ask about it:\n"
            f"{app_context}\n\n"
        )
    user_content = (
        f"{app_block}"
        f"Original source context:\n{context}\n\n"
        f"Requirement to be drafted as a JIRA {issue_type.value}:\n"
        f"Title: {requirement.title}\n"
        f"Details: {requirement.raw_description}\n"
        f"Why this is a distinct {issue_type.value}: {requirement.rationale}\n"
    )
    system = CLARIFIER_SYSTEM_PROMPT.format(
        issue_type=issue_type.value, max_questions=settings.max_clarifying_questions_per_item
    )
    check = await structured_call(
        system=system,
        messages=[{"role": "user", "content": user_content}],
        output_format=ClarificationCheck,
        max_tokens=2000,
        thinking=True,
    )
    return check.questions[: settings.max_clarifying_questions_per_item]
