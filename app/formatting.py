from app.models.schemas import GeneratedStory, JiraBug, JiraEpic


def summarize_stories(stories: list[GeneratedStory]) -> str:
    lines = []
    for i, gs in enumerate(stories):
        lines.append(
            f"{i}. [{gs.story.issue_type.value}] {gs.story.summary} (priority={gs.story.priority.value}, "
            f"valid={gs.validation.is_valid}, score={gs.validation.score})"
        )
    return "\n".join(lines)


def _body_for(gs: GeneratedStory) -> str:
    s = gs.story
    if isinstance(s, JiraEpic):
        criteria = "\n".join(f"  - {c}" for c in s.success_criteria)
        return f"Goal: {s.goal}\nBusiness value: {s.business_value}\nSuccess criteria:\n{criteria}"
    if isinstance(s, JiraBug):
        steps = "\n".join(f"  {i + 1}. {step}" for i, step in enumerate(s.steps_to_reproduce))
        return (
            f"Steps to reproduce:\n{steps}\n"
            f"Expected: {s.expected_result}\nActual: {s.actual_result}\nSeverity: {s.severity.value}"
        )
    criteria = "\n".join(f"  - {ac}" for ac in s.acceptance_criteria)
    return f"{s.user_story}\nAcceptance criteria:\n{criteria}"


def format_stories_reply(stories: list[GeneratedStory], open_questions: list[str]) -> str:
    count = len(stories)
    parts = [f"I drafted {count} JIRA item{'s' if count != 1 else ''} from your input:"]
    for i, gs in enumerate(stories):
        s = gs.story
        story_points = getattr(s, "story_points", None)
        points = f" | {story_points} pts" if story_points is not None else ""
        parts.append(
            f"{i + 1}. {s.summary} [{s.issue_type.value} | {s.priority.value}{points}]\n"
            f"{_body_for(gs)}\n"
            f"Quality score: {gs.validation.score}/100"
            + ("" if gs.validation.is_valid else " (needs a look before it's sprint-ready)")
        )
    if open_questions:
        questions = "\n".join(f"- {q}" for q in open_questions)
        parts.append(f"A few things worth clarifying (optional):\n{questions}")
    parts.append(
        'Say "create these in JIRA" to push them, or tell me what to change '
        '(e.g. "make item 2 high priority").'
    )
    return "\n\n".join(parts)


def format_jira_results_reply(results: list[dict]) -> str:
    lines = ["Here's what happened when I pushed to JIRA:"]
    for r in results:
        if "error" in r:
            lines.append(f"- FAILED: {r['summary']}: {r['error']}")
        else:
            lines.append(f"- CREATED: {r['summary']}: {r['key']} - {r['url']}")
    return "\n".join(lines)
