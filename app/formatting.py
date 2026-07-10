from app.models.schemas import GeneratedStory


def summarize_stories(stories: list[GeneratedStory]) -> str:
    lines = []
    for i, gs in enumerate(stories):
        lines.append(
            f"{i}. {gs.story.summary} (priority={gs.story.priority.value}, "
            f"points={gs.story.story_points}, valid={gs.validation.is_valid}, score={gs.validation.score})"
        )
    return "\n".join(lines)


def format_stories_reply(stories: list[GeneratedStory], open_questions: list[str]) -> str:
    count = len(stories)
    parts = [f"I drafted {count} JIRA stor{'y' if count == 1 else 'ies'} from your input:"]
    for i, gs in enumerate(stories):
        s = gs.story
        criteria = "\n".join(f"  - {ac}" for ac in s.acceptance_criteria)
        parts.append(
            f"{i + 1}. {s.summary} [{s.issue_type.value} | {s.priority.value} | "
            f"{s.story_points if s.story_points is not None else '?'} pts]\n"
            f"{s.user_story}\n"
            f"Acceptance criteria:\n{criteria}\n"
            f"Quality score: {gs.validation.score}/100"
            + ("" if gs.validation.is_valid else " (needs a look before it's sprint-ready)")
        )
    if open_questions:
        questions = "\n".join(f"- {q}" for q in open_questions)
        parts.append(f"A few things worth clarifying (optional):\n{questions}")
    parts.append(
        'Say "create these in JIRA" to push them, or tell me what to change '
        '(e.g. "make story 2 high priority").'
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
