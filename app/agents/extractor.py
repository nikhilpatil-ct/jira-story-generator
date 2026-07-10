from app.agents.base import structured_call
from app.models.schemas import ExtractionResult

SYSTEM_PROMPT = """You are a requirements analyst. Given raw, unstructured meeting notes or free-form \
product/engineering discussion, identify each distinct, independently deliverable user story or piece \
of work implied by the text.

Rules:
- Split compound requirements into separate stories when they represent independently shippable \
increments of value.
- Do not invent requirements that are not grounded in the source text.
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
