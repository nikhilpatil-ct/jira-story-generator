from app.agents.base import structured_call
from app.models.schemas import ExtractedRequirement, JiraStory

DRAFT_SYSTEM_PROMPT = """You are a senior agile business analyst who writes excellent JIRA stories.

Given a requirement extracted from meeting notes (plus the original source text for grounding), write a \
complete, high quality JIRA story following INVEST principles (Independent, Negotiable, Valuable, \
Estimable, Small, Testable):
- user_story must follow "As a <role>, I want <capability>, so that <benefit>". Infer a sensible role \
from context if it is not stated explicitly.
- acceptance_criteria: 3-6 concrete, testable, unambiguous statements a QA engineer could verify \
directly -- avoid vague language like "should work well".
- story_points: estimate using a Fibonacci-like scale (1, 2, 3, 5, 8, 13) based on apparent complexity; \
use null only if there is truly not enough information to estimate.
- priority and labels should be inferred from the language and context (urgency words, dependencies, \
technical area).
"""

REFINE_SYSTEM_PROMPT = """You are revising a previously drafted JIRA story based on specific feedback \
(either from an automated quality reviewer or directly from the user). Preserve everything that is \
already good about the story; change only what the feedback asks for. Keep the same overall shape and \
level of detail as the original unless the feedback asks for more or less.
"""


async def draft(requirement: ExtractedRequirement, context: str) -> JiraStory:
    user_content = (
        f"Original source context:\n{context}\n\n"
        f"Requirement to turn into a JIRA story:\n"
        f"Title: {requirement.title}\n"
        f"Details: {requirement.raw_description}\n"
        f"Why this is a distinct story: {requirement.rationale}\n"
    )
    return await structured_call(
        system=DRAFT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        output_format=JiraStory,
        max_tokens=6000,
        thinking=True,
    )


async def refine(story: JiraStory, feedback: str) -> JiraStory:
    user_content = (
        f"Current story:\n{story.model_dump_json(indent=2)}\n\n"
        f"Feedback / requested change to address:\n{feedback}\n"
    )
    return await structured_call(
        system=REFINE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        output_format=JiraStory,
        max_tokens=6000,
        thinking=True,
    )
