from app.agents.base import structured_call
from app.models.schemas import JiraItem, ValidationResult

SYSTEM_PROMPT = """You are a meticulous QA reviewer for agile JIRA items (Epics, Stories, and Bugs). \
Evaluate the given item against the quality bar appropriate for its issue_type:

- Story/Task: judge against INVEST (Independent, Negotiable, Valuable, Estimable, Small, Testable). \
Acceptance criteria must be concrete and testable, not vague. user_story must follow the correct format \
and name a real, specific role.
- Epic: judge whether business_value and goal are clear and the success_criteria are measurable and \
sufficient to know when the epic is done.
- Bug: judge whether steps_to_reproduce are concrete and reproducible, and expected_result/actual_result \
clearly describe the discrepancy. severity should be justified by the description.

For every type: no missing detail that would block someone from starting work without guessing.

Score from 0-100. Set is_valid to true only when the item is genuinely ready to be pulled into a sprint \
with no more than minor nitpicks. List every real issue you find in `issues`, each with a concrete, \
actionable suggestion.
"""


async def validate(story: JiraItem) -> ValidationResult:
    return await structured_call(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": story.model_dump_json(indent=2)}],
        output_format=ValidationResult,
        max_tokens=3000,
        thinking=True,
    )
