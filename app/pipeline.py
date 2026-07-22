import asyncio

from app.agents import drafter, extractor, validator
from app.config import settings
from app.models.schemas import ExtractionResult, GeneratedStory, IssueType
from app.services import app_context, pii_redactor, session_store, transcript_cleaner, translator


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

    # Redact PII BEFORE any LLM call (translation/extraction) so raw personal data never leaves the
    # local boundary. This ordering is a compliance guarantee: every downstream model only ever sees
    # masked <ENTITY_TYPE> tokens.
    log("cleaning", "Scanning for PII (names, emails, phone numbers, etc.)...")
    cleaned, pii_entities = await asyncio.to_thread(pii_redactor.redact, cleaned)
    if pii_entities:
        log("cleaning", f"Redacted {len(pii_entities)} PII type(s) before any model call: {', '.join(pii_entities)}")
    else:
        log("cleaning", "No PII detected")

    detected_lang = translator.detect_language(cleaned)
    log("cleaning", f"Detected language: {detected_lang or 'unknown'} — normalizing to English...")
    cleaned = await translator.translate_to_english(cleaned)
    log("cleaning", "Transcript normalized to English")

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

    # Detect which known applications this transcript refers to and load their pre-written context
    # (business flow, use cases, design, tech stack) so the drafter is grounded in what each app actually
    # does — not just what this one meeting happened to mention. The DB app_catalog is the name->file map.
    session_store.update_step(session_id, "context")
    catalog = app_context.list_catalog()  # the DB name->file mapping, read once and reused per requirement
    transcript_apps = app_context.detect_apps(cleaned, catalog)
    if transcript_apps:
        log("context", f"Detected {len(transcript_apps)} known application(s): {', '.join(a['name'] for a in transcript_apps)}")
        for a in transcript_apps:
            log("context", f"Loaded context for {a['name']} from {a['file_path']}")
    else:
        log("context", "No known applications detected — drafting without app context")

    session_store.update_step(session_id, "drafting")
    total = len(requirements)
    log("drafting", f"Drafting {total} item(s) in parallel (up to {settings.max_concurrent_drafts} at a time)...")

    # Bound concurrency so a large transcript doesn't fire dozens of simultaneous calls at the API and
    # trip rate limits. asyncio.gather runs these coroutines concurrently on the event loop — the right
    # kind of parallelism here since every LLM call is async I/O (threads would add overhead, not speed).
    semaphore = asyncio.Semaphore(settings.max_concurrent_drafts)
    completed = 0

    async def draft_and_validate(requirement) -> GeneratedStory:
        nonlocal completed
        # Ground this specific item in the app(s) it mentions; fall back to the transcript-level matches
        # when the requirement text alone names none. Detection is cheap/deterministic, so it's fine per item.
        req_text = f"{requirement.title}\n{requirement.raw_description}\n{requirement.rationale}"
        req_apps = app_context.detect_apps(req_text, catalog) or transcript_apps
        app_ctx = app_context.build_context(req_apps)
        grounding = f" (context: {', '.join(a['name'] for a in req_apps)})" if req_apps else ""
        async with semaphore:
            log("drafting", f"Drafting \"{requirement.title}\" [{requirement.issue_type.value}]{grounding}...")
            story = await drafter.draft(requirement, cleaned, app_context=app_ctx)
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

            # Single-threaded event loop: this read-modify-write between awaits is safe without a lock.
            completed += 1
            log("drafting", f"Finished {completed}/{total}: \"{story.summary}\"")
            return GeneratedStory(story=story, validation=result, attempts=attempts)

    # return_exceptions=True so one item failing (even after retries) doesn't discard the items that succeeded.
    results = await asyncio.gather(*(draft_and_validate(r) for r in requirements), return_exceptions=True)

    generated: list[GeneratedStory] = []  # preserves requirement order (gather returns results in input order)
    for requirement, result in zip(requirements, results):
        if isinstance(result, BaseException):
            log("drafting", f"Failed to draft \"{requirement.title}\" after retries: {result}")
        else:
            generated.append(result)

    session_store.update_step(session_id, "validating")
    session_store.update_step(session_id, "done")
    log("pipeline", f"Generated {len(generated)} item(s)")
    return generated, extraction, cleaned
