import logging

from app.agents.base import text_call
from app.config import settings

logger = logging.getLogger("translator")

SYSTEM_PROMPT = """You are a professional translator and localization editor. The following meeting \
transcript may contain non-English text, code-switching between languages, or English words/phrases used \
with a non-English idiomatic or borrowed meaning (false friends, calques, regional slang) that would \
confuse a literal English reading.

Rewrite the ENTIRE transcript in clear, natural English:
- Translate any non-English words, phrases, or sentences into English.
- Where an English word or phrase is used with a foreign/idiomatic meaning that differs from its literal \
English meaning, rewrite it using the correct English meaning instead.
- Preserve structure: speaker labels, timestamps, and line breaks, and keep the order of the conversation.
- Do not summarize, shorten, add commentary, or invent content. Do not translate proper nouns, product \
names, or technical identifiers that should stay as-is.
- If a portion is already clear, natural English, leave it unchanged.

Return ONLY the rewritten transcript text, with no preamble, explanation, or markdown formatting.
"""

try:
    from langdetect import DetectorFactory, LangDetectException, detect_langs

    DetectorFactory.seed = 0  # deterministic results
    _langdetect_available = True
except Exception as exc:  # noqa: BLE001 - detection is only used for a log message, never blocking
    _langdetect_available = False
    logger.warning("langdetect unavailable: %s", exc)


def detect_language(text: str) -> str | None:
    """Best-effort language code for logging/visibility. Returns None if detection isn't available."""
    if not _langdetect_available or not text.strip():
        return None
    try:
        langs = detect_langs(text)
    except LangDetectException:
        return None
    return langs[0].lang if langs else None


async def translate_to_english(text: str) -> str:
    """Ask a light/fast Claude model to translate and normalize the transcript into English.

    Runs unconditionally (not just when a non-English language is detected): a purely statistical
    language detector reports transcripts as "en" even when they contain English words used with a
    foreign/idiomatic meaning, which only an LLM can actually catch and fix.
    """
    if not text.strip():
        return text
    try:
        return await text_call(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            model=settings.translation_model,
            max_tokens=8000,
        )
    except Exception as exc:  # noqa: BLE001 - translation is best-effort, never block the pipeline
        logger.warning("Translation failed, using original text: %s", exc)
        return text
