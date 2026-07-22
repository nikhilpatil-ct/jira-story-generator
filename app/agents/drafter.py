from app.agents.base import structured_call
from app.models.schemas import ExtractedRequirement, IssueType, JiraBug, JiraEpic, JiraItem, JiraUserStory

DRAFT_SYSTEM_PROMPTS = {
    IssueType.EPIC: (
        "You are a senior agile business analyst who writes excellent JIRA epics. Given a requirement "
        "extracted from meeting notes (plus the original source text for grounding), write a complete "
        "epic: business_value explains why this matters to the business, goal is the overall outcome, "
        "success_criteria is 3-6 measurable statements that define when the epic is done. priority and "
        "labels should be inferred from the language and context."
    ),
    IssueType.STORY: (
        "You are a senior agile business analyst who writes excellent JIRA stories following INVEST "
        "principles. Given a requirement extracted from meeting notes (plus the original source text for "
        "grounding): user_story must follow 'As a <role>, I want <capability>, so that <benefit>' (infer a "
        "sensible role from context if not stated explicitly); acceptance_criteria: 3-6 concrete, "
        "testable, unambiguous statements a QA engineer could verify directly; story_points: estimate "
        "using a Fibonacci-like scale (1, 2, 3, 5, 8, 13), null only if truly not estimable. priority and "
        "labels should be inferred from the language and context."
    ),
    IssueType.BUG: (
        "You are a senior QA/business analyst who writes excellent JIRA bug reports. Given a requirement "
        "extracted from meeting notes (plus the original source text for grounding): steps_to_reproduce is "
        "an ordered list of concrete steps; expected_result and actual_result describe the discrepancy; "
        "severity reflects real-world impact; environment captures browser/OS/deployment context if "
        "mentioned; root_cause is filled only if inferable from the source text, otherwise left null. "
        "priority and labels should be inferred from the language and context."
    ),
}

DRAFT_OUTPUT_FORMATS = {
    IssueType.EPIC: JiraEpic,
    IssueType.STORY: JiraUserStory,
    IssueType.BUG: JiraBug,
}

REFINE_SYSTEM_PROMPT = """You are revising a previously drafted JIRA item based on specific feedback \
(either from an automated quality reviewer or directly from the user). Preserve everything that is \
already good; change only what the feedback asks for. Keep the same overall shape and level of detail as \
the original unless the feedback asks for more or less.
"""


async def draft(requirement: ExtractedRequirement, context: str, app_context: str = "") -> JiraItem:
    issue_type = requirement.issue_type if requirement.issue_type in DRAFT_OUTPUT_FORMATS else IssueType.STORY
    app_block = ""
    if app_context:
        app_block = (
            "Known application context — the business flow, use cases, design, and tech stack of the "
            "application this requirement relates to. Use it to ground terminology, name the right "
            "components/integrations, and add technically accurate detail. Do NOT invent requirements it "
            "does not support; it is background knowledge, not a new source of scope:\n"
            f"{app_context}\n\n"
        )
    user_content = (
        f"{app_block}"
        f"Original source context:\n{context}\n\n"
        f"Requirement to turn into a JIRA {issue_type.value}:\n"
        f"Title: {requirement.title}\n"
        f"Details: {requirement.raw_description}\n"
        f"Why this is a distinct {issue_type.value}: {requirement.rationale}\n"
    )
    return await structured_call(
        system=DRAFT_SYSTEM_PROMPTS[issue_type],
        messages=[{"role": "user", "content": user_content}],
        output_format=DRAFT_OUTPUT_FORMATS[issue_type],
        max_tokens=6000,
        thinking=True,
    )


async def refine(story: JiraItem, feedback: str) -> JiraItem:
    user_content = (
        f"Current item (issue_type={story.issue_type.value}):\n{story.model_dump_json(indent=2)}\n\n"
        f"Feedback / requested change to address:\n{feedback}\n"
    )
    return await structured_call(
        system=REFINE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        output_format=type(story),
        max_tokens=6000,
        thinking=True,
    )
