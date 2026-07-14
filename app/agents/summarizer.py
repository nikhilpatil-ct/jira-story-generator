from app.agents.base import structured_call
from app.models.schemas import GeneratedStory
from pydantic import BaseModel, Field

SYSTEM_PROMPT = """You are a concise technical program manager. Given a set of generated JIRA items \
(epics, stories, bugs) drafted from a meeting transcript, along with any risks and open questions, write a \
short executive summary (3-6 sentences) covering: what was discussed, the overall shape of the work \
(counts/themes), and anything that stands out (major risks, low-quality items, open questions). Plain \
prose, no bullet lists.
"""


class SummaryResult(BaseModel):
    summary: str = Field(description="3-6 sentence executive summary")


async def summarize(
    stories: list[GeneratedStory], risks: list[str], open_questions: list[str], action_items: list[str]
) -> str:
    if not stories:
        return "No items generated yet."

    lines = [f"Items ({len(stories)}):"]
    for gs in stories:
        s = gs.story
        lines.append(f"- [{s.issue_type.value}] {s.summary} (priority={s.priority.value}, score={gs.validation.score})")
    if risks:
        lines.append("\nRisks:\n" + "\n".join(f"- {r}" for r in risks))
    if action_items:
        lines.append("\nAction items:\n" + "\n".join(f"- {a}" for a in action_items))
    if open_questions:
        lines.append("\nOpen questions:\n" + "\n".join(f"- {q}" for q in open_questions))

    result = await structured_call(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n".join(lines)}],
        output_format=SummaryResult,
        max_tokens=1000,
        thinking=False,
    )
    return result.summary
