from app.agents.base import structured_call
from app.models.schemas import JiraItem, RiskAnalysisResult, TestCasesResult

IMPROVE_WORDING_FEEDBACK = (
    "Improve the clarity, tone, and professionalism of the wording throughout (summary, description, "
    "user_story, acceptance criteria, etc. as applicable) without changing scope or meaning."
)

EXPAND_AC_FEEDBACK = (
    "The acceptance criteria (or success_criteria for an Epic) are too thin. Add additional concrete, "
    "testable criteria covering edge cases, error states, and non-functional expectations (e.g. "
    "performance, permissions) implied by the item, while keeping the existing ones."
)

TEST_CASES_SYSTEM_PROMPT = """You are a QA engineer. Given a JIRA item, write a set of concrete test cases \
that verify it. Cover the happy path, edge cases, and error states implied by the item's description and \
acceptance/success criteria. Each test case needs a short title, ordered concrete steps, and an expected \
result.
"""

RISK_ANALYSIS_SYSTEM_PROMPT = """You are a delivery risk analyst. Given a JIRA item, identify concrete \
risks to delivering it successfully -- technical, scope, dependency, or business risks grounded in what \
the item actually says. For each, state the impact if it materializes and a concrete mitigation. Do not \
invent generic risks unrelated to the item's content; if there are genuinely few risks, return fewer items.
"""


async def generate_test_cases(story: JiraItem) -> TestCasesResult:
    return await structured_call(
        system=TEST_CASES_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": story.model_dump_json(indent=2)}],
        output_format=TestCasesResult,
        max_tokens=4000,
        thinking=True,
    )


async def analyze_risks(story: JiraItem) -> RiskAnalysisResult:
    return await structured_call(
        system=RISK_ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": story.model_dump_json(indent=2)}],
        output_format=RiskAnalysisResult,
        max_tokens=3000,
        thinking=True,
    )
