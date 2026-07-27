import asyncio

from app.agents import clarifier, drafter, extractor, story_actions, titler, validator
from app.config import settings
from app.models.schemas import ExtractionResult, GeneratedStory, IssueType, SourceType
from app.services import (
    app_context,
    clarification_store,
    confluence_client,
    pii_redactor,
    session_store,
    transcript_cleaner,
    translator,
)


async def generate_stories(
    session_id: str,
    conversation_text: str,
    generation_scope: list[IssueType] | None = None,
    source_type: SourceType | None = None,
) -> tuple[list[GeneratedStory], ExtractionResult, str]:
    """Run the clean -> extract -> draft -> validate -> refine pipeline over raw conversation text.

    `source_type` selects the transcript-vs-document path (cleaning strategy + extraction prompt). It
    comes from the user's UI toggle; when None (the "Auto" toggle), it's auto-detected from the text."""

    def log(stage: str, message: str) -> None:
        session_store.append_log(session_id, stage, message)

    session_store.update_step(session_id, "cleaning")
    if source_type is None:
        source_type = transcript_cleaner.detect_source_type(conversation_text)
        origin = "auto-detected"
    else:
        origin = "selected"
    kind = "meeting transcript" if source_type == SourceType.TRANSCRIPT else "structured document (e.g. BRD/PRD)"
    log("cleaning", f"Source {origin}: {kind} ({len(conversation_text):,} characters) — cleaning...")
    cleaned = transcript_cleaner.clean(conversation_text, source_type)
    log("cleaning", f"Cleaned input: {len(conversation_text):,} -> {len(cleaned):,} characters")

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
    log("cleaning", "Input normalized to English")

    session_store.update_step(session_id, "extracting")
    log("extracting", "Extracting requirements, risks, and action items...")
    extraction = await extractor.extract(cleaned, source_type)

    requirements = extraction.requirements
    counts = {t: sum(1 for r in requirements if r.issue_type == t) for t in set(r.issue_type for r in requirements)}
    counts_str = ", ".join(f"{n} {t.value}{'s' if n != 1 else ''}" for t, n in counts.items()) or "nothing"
    log("extracting", f"Extracted {len(requirements)} requirement(s): {counts_str}")
    if extraction.risks:
        log("extracting", f"Identified {len(extraction.risks)} risk(s)")
    if extraction.action_items:
        log("extracting", f"Identified {len(extraction.action_items)} action item(s)")

    # Give a still-unnamed session a concise title now — while drafting (the slow part) is still ahead,
    # so it shows up meaningfully in the sidebar instead of "New session" for the whole run. Titling
    # runs on `cleaned`, which is already PII-redacted, so no raw personal data is sent for naming. It's
    # cosmetic: only spend the (cheap-model) call when the title is still a default, and never let a
    # failure here block generation.
    current = session_store.get(session_id)
    if current is not None and current.title in session_store.DEFAULT_TITLES:
        try:
            proposed = await titler.generate_title(cleaned)
            if proposed and session_store.autoname_if_default(session_id, proposed):
                log("pipeline", f'Named session: "{proposed}"')
        except Exception as exc:  # noqa: BLE001 - naming must never block generation
            log("pipeline", f"Could not auto-name session ({exc}) — keeping current title")

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

    # Confluence is optional bonus grounding (a page's body, plus the text of any PDF attached to it),
    # fetched once per run and reused for every item like the app knowledge base above.
    confluence_ctx = ""
    if settings.confluence_configured:
        log("context", "Fetching Confluence page context...")
        confluence_ctx = await confluence_client.get_page_context()
        if confluence_ctx:
            log("context", f"Loaded Confluence context ({len(confluence_ctx):,} characters, including any attached PDFs)")
        else:
            log("context", "Confluence page returned no usable context")

    session_store.update_step(session_id, "drafting")
    total = len(requirements)
    log("drafting", f"Drafting {total} item(s) in parallel (up to {settings.max_concurrent_drafts} at a time)...")

    # Each concurrent draft may pause to ask the user its own questions, so start from a clean slate: drop
    # any leftover question groups from a previous (e.g. abandoned) run of this same session.
    clarification_store.clear_session(session_id)

    # Bound concurrency so a large transcript doesn't fire dozens of simultaneous calls at the API and
    # trip rate limits. asyncio.gather runs these coroutines concurrently on the event loop — the right
    # kind of parallelism here since every LLM call is async I/O (threads would add overhead, not speed).
    semaphore = asyncio.Semaphore(settings.max_concurrent_drafts)
    completed = 0

    async def draft_and_validate(requirement, item_index: int) -> GeneratedStory:
        nonlocal completed
        # Ground this specific item in the app(s) it mentions; fall back to the transcript-level matches
        # when the requirement text alone names none. Detection is cheap/deterministic, so it's fine per item.
        req_text = f"{requirement.title}\n{requirement.raw_description}\n{requirement.rationale}"
        req_apps = app_context.detect_apps(req_text, catalog) or transcript_apps
        app_ctx = app_context.build_context(req_apps)
        if confluence_ctx:
            app_ctx = "\n\n---\n\n".join(filter(None, [app_ctx, confluence_ctx]))
        grounding = f" (context: {', '.join(a['name'] for a in req_apps)})" if req_apps else ""

        # Anti-hallucination gate: before writing anything, ask whether this item is missing facts we'd
        # otherwise have to invent. Each item raises its own questions independently (that's the "multi-
        # threaded" part), so every question is tagged with this item's index/title/type before it reaches
        # the user — the UI groups them per item so concurrent questions never blur together. The wait
        # itself holds NO semaphore slot, so one item pausing for an answer never blocks the others' drafts.
        clarifications = ""
        if settings.clarifying_questions_enabled:
            async with semaphore:  # the clarifier is an LLM call — bound it like any other
                log("clarifying", f"Reviewing \"{requirement.title}\" for missing details...")
                try:
                    questions = await clarifier.clarify(requirement, cleaned, app_context=app_ctx)
                except Exception as exc:  # noqa: BLE001 - a clarifier hiccup must never block drafting
                    log("clarifying", f"Could not review \"{requirement.title}\" ({exc}) — drafting as-is")
                    questions = []
            if questions:
                payload = [
                    {"id": f"{item_index}-{n}", "question": q.question, "reason": q.reason}
                    for n, q in enumerate(questions)
                ]
                group = clarification_store.open_group(
                    session_id, item_index, requirement.title, requirement.issue_type.value, payload
                )
                log("clarifying", f"Asked {len(payload)} question(s) about \"{requirement.title}\" — waiting for you...")
                status = await clarification_store.wait_for_answers(group, settings.clarification_timeout_seconds)
                clarifications = clarification_store.answers_text(group)
                if status == "answered":
                    log("clarifying", f"Got your answers for \"{requirement.title}\" — drafting with them")
                elif status == "skipped":
                    log("clarifying", f"Skipped \"{requirement.title}\" — drafting with best-guess assumptions")
                else:  # timeout
                    log("clarifying", f"No answer for \"{requirement.title}\" in time — drafting with best-guess assumptions")

        async with semaphore:
            log("drafting", f"Drafting \"{requirement.title}\" [{requirement.issue_type.value}]{grounding}...")
            story = await drafter.draft(requirement, cleaned, app_context=app_ctx, clarifications=clarifications)
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

            log("drafting", f"Writing test cases for \"{story.summary}\"...")
            try:
                test_cases = (await story_actions.generate_test_cases(story)).test_cases
                log("drafting", f"Wrote {len(test_cases)} test case(s) for \"{story.summary}\"")
            except Exception as exc:  # noqa: BLE001 - a test-case hiccup must never block drafting
                log("drafting", f"Could not write test cases for \"{story.summary}\" ({exc}) — continuing without them")
                test_cases = []

            # Single-threaded event loop: this read-modify-write between awaits is safe without a lock.
            completed += 1
            log("drafting", f"Finished {completed}/{total}: \"{story.summary}\"")
            return GeneratedStory(story=story, validation=result, attempts=attempts, test_cases=test_cases)

    # return_exceptions=True so one item failing (even after retries) doesn't discard the items that succeeded.
    try:
        results = await asyncio.gather(
            *(draft_and_validate(r, i) for i, r in enumerate(requirements)), return_exceptions=True
        )
    finally:
        # Drop any pending question groups now that the fan-out is done, so a stale question can't linger
        # in the poller's view after drafting has moved on.
        clarification_store.clear_session(session_id)

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
