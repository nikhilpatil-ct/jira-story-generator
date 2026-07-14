import asyncio

from app.agents import drafter, extractor, validator
from app.config import settings
from app.models.schemas import ExtractionResult, GeneratedStory, IssueType
from app.services import pii_redactor, session_store, transcript_cleaner, translator


async def generate_stories(
    session_id: str, conversation_text: str, generation_scope: list[IssueType] | None = None
) -> tuple[list[GeneratedStory], ExtractionResult, str]:
    """Run the clean -> extract -> draft -> validate -> refine pipeline over raw conversation text."""

    def log(stage: str, message: str) -> None:
        session_store.append_log(session_id, stage, message)

    session_store.update_step(session_id, "cleaning")
    log("cleaning", f"Cleaning transcript ({len(conversation_text):,} characters)...")
    cleaned = transcript_cleaner.clean(conversation_text)
    log("cleaning", f"Cleaned transcript: {len(conversation_text):,} -> {len(cleaned):,} characters")

    detected_lang = translator.detect_language(cleaned)
    log("cleaning", f"Detected language: {detected_lang or 'unknown'} — normalizing to English...")
    cleaned = await translator.translate_to_english(cleaned)
    log("cleaning", "Transcript normalized to English")

    log("cleaning", "Scanning for PII (names, emails, phone numbers, etc.)...")
    cleaned, pii_entities = await asyncio.to_thread(pii_redactor.redact, cleaned)
    if pii_entities:
        log("cleaning", f"Redacted {len(pii_entities)} PII type(s): {', '.join(pii_entities)}")
    else:
        log("cleaning", "No PII detected")

    session_store.update_step(session_id, "extracting")
    log("extracting", "Extracting requirements, risks, and action items...")
    extraction = await extractor.extract(cleaned)

    requirements = extraction.requirements
    counts = {t: sum(1 for r in requirements if r.issue_type == t) for t in set(r.issue_type for r in requirements)}
    counts_str = ", ".join(f"{n} {t.value}{'s' if n != 1 else ''}" for t, n in counts.items()) or "nothing"
    log("extracting", f"Extracted {len(requirements)} requirement(s): {counts_str}")
    if extraction.risks:
        log("extracting", f"Identified {len(extraction.risks)} risk(s)")
    if extraction.action_items:
        log("extracting", f"Identified {len(extraction.action_items)} action item(s)")

    if generation_scope:
        requirements = [r for r in requirements if r.issue_type in generation_scope]
        log("extracting", f"Scoped generation to: {', '.join(t.value for t in generation_scope)} ({len(requirements)} matching)")

    generated: list[GeneratedStory] = []
    session_store.update_step(session_id, "drafting")
    for i, requirement in enumerate(requirements, start=1):
        log("drafting", f"Drafting item {i}/{len(requirements)}: \"{requirement.title}\" [{requirement.issue_type.value}]")
        story = await drafter.draft(requirement, cleaned)
        attempts = 1
        result = await validator.validate(story)
        log("validating", f"Validated \"{story.summary}\": score {result.score}/100" + ("" if result.is_valid else " (below quality bar)"))

        while (
            not result.is_valid
            and result.score < settings.validation_pass_score
            and attempts < settings.max_refinement_attempts
        ):
            log("drafting", f"Refining \"{story.summary}\" (attempt {attempts + 1}/{settings.max_refinement_attempts})...")
            feedback = "\n".join(f"- [{issue.field}] {issue.problem} -> {issue.suggestion}" for issue in result.issues)
            story = await drafter.refine(story, feedback)
            result = await validator.validate(story)
            attempts += 1
            log("validating", f"Re-validated \"{story.summary}\": score {result.score}/100")

        generated.append(GeneratedStory(story=story, validation=result, attempts=attempts))

    session_store.update_step(session_id, "validating")
    session_store.update_step(session_id, "done")
    log("pipeline", f"Generated {len(generated)} item(s)")
    return generated, extraction, cleaned
