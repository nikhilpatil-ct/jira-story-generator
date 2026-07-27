import re

from app.agents.base import text_call
from app.config import settings

SYSTEM_PROMPT = """You name work sessions. Given requirements text (a meeting transcript or a \
structured document such as a BRD/PRD), reply with a short, specific title of 3-6 words that \
captures its main topic. Use Title Case. Do NOT wrap it in quotes, add trailing punctuation, or \
prefix it with "Title:" or "Session:". Output ONLY the title, nothing else."""

# Titles are cosmetic, so bound the input hard: the opening of the text almost always carries the
# topic, and a small snippet keeps this on the cheap model at negligible cost.
_MAX_INPUT_CHARS = 4000
_MAX_TITLE_CHARS = 60


def _sanitize(raw: str) -> str:
    """Coerce the model's reply into a clean one-line title, defending against stray quotes/prefixes."""
    title = (raw or "").strip()
    if not title:
        return ""
    title = title.splitlines()[0].strip()
    title = title.strip("\"'").strip()
    title = re.sub(r"^(title|session)\s*[:\-]\s*", "", title, flags=re.IGNORECASE).strip()
    title = title.rstrip(".").strip()
    return title[:_MAX_TITLE_CHARS].strip()


async def generate_title(text: str) -> str:
    """A concise session title from already-redacted text. Returns "" if nothing usable came back."""
    snippet = (text or "").strip()[:_MAX_INPUT_CHARS]
    if not snippet:
        return ""
    raw = await text_call(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": snippet}],
        model=settings.translation_model,
        max_tokens=64,
    )
    return _sanitize(raw)
