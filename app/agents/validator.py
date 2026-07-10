from app.agents.base import structured_call
from app.models.schemas import JiraStory, ValidationResult

SYSTEM_PROMPT = """You are a meticulous QA reviewer for agile user stories. Evaluate the given JIRA \
story against INVEST criteria and general quality bars:
- Independent, Negotiable, Valuable, Estimable, Small, Testable
- Acceptance criteria must be concrete and testable, not vague
- user_story must follow the correct format and name a real, specific role
- No missing detail that would block a developer from starting work without guessing

Score from 0-100. Set is_valid to true only when the story is genuinely ready to be pulled into a \
sprint with no more than minor nitpicks. List every real issue you find in `issues`, each with a \
concrete, actionable suggestion.
"""


async def validate(story: JiraStory) -> ValidationResult:
    return await structured_call(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": story.model_dump_json(indent=2)}],
        output_format=ValidationResult,
        max_tokens=3000,
        thinking=True,
    )
