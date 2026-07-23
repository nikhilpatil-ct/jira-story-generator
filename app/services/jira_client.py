import logging
from difflib import SequenceMatcher

import httpx

from app.config import settings
from app.models.schemas import JiraBug, JiraEpic, JiraItem, JiraUserStory

logger = logging.getLogger("jira_client")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class JiraError(Exception):
    pass


def _text_block(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _heading(text: str) -> dict:
    return {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": text}]}


def _bullet_list(items: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": item}]}]}
            for item in items
        ],
    }


def _build_adf_description(story: JiraItem) -> dict:
    content: list[dict] = []

    if isinstance(story, JiraEpic):
        content += [_heading("Goal"), _text_block(story.goal)]
        content += [_heading("Business Value"), _text_block(story.business_value)]
        if story.description:
            content += [_heading("Description"), _text_block(story.description)]
        if story.success_criteria:
            content += [_heading("Success Criteria"), _bullet_list(story.success_criteria)]

    elif isinstance(story, JiraBug):
        if story.description:
            content.append(_text_block(story.description))
        if story.steps_to_reproduce:
            content += [_heading("Steps to Reproduce"), _bullet_list(story.steps_to_reproduce)]
        content += [_heading("Expected Result"), _text_block(story.expected_result)]
        content += [_heading("Actual Result"), _text_block(story.actual_result)]
        if story.environment:
            content += [_heading("Environment"), _text_block(story.environment)]
        if story.root_cause:
            content += [_heading("Root Cause"), _text_block(story.root_cause)]

    else:
        content.append(_text_block(story.user_story))
        if story.description:
            content.append(_text_block(story.description))
        if story.acceptance_criteria:
            content += [_heading("Acceptance Criteria"), _bullet_list(story.acceptance_criteria)]

    if not content:
        content = [_text_block(story.description or story.summary)]

    return {"type": "doc", "version": 1, "content": content}


def _epic_link_fields(epic_key: str) -> dict:
    """Fields that attach a non-Epic issue to its parent Epic. Configurable because the two Jira Cloud
    project flavors disagree: team-managed projects use the native "parent" field, while a classic
    company-managed project still on the legacy Epic Link needs a custom field id instead."""
    if settings.jira_epic_link_field:
        return {settings.jira_epic_link_field: epic_key}
    return {"parent": {"key": epic_key}}


def build_fields(story: JiraItem, epic_key: str | None = None) -> dict:
    """Build the JIRA issue `fields` payload for a story. Shared by preview and create.

    `epic_key`, when given, attaches this (non-Epic) issue to that Epic as its parent/child.
    """
    fields: dict = {
        "project": {"key": settings.jira_project_key},
        "summary": story.summary[:255],
        "issuetype": {"name": story.issue_type.value},
        "description": _build_adf_description(story),
    }
    if story.labels:
        fields["labels"] = story.labels
    if story.priority:
        fields["priority"] = {"name": story.priority.value}
    if isinstance(story, JiraUserStory) and story.story_points is not None and settings.jira_story_points_field:
        fields[settings.jira_story_points_field] = story.story_points
    if epic_key and not isinstance(story, JiraEpic):
        fields.update(_epic_link_fields(epic_key))
    return fields


async def create_issue(story: JiraItem, epic_key: str | None = None) -> dict:
    """Create a single issue in JIRA via the Cloud REST API v3. Raises JiraError on failure.

    Pass `epic_key` to link a newly created Story/Bug/Task under that Epic; ignored for Epics themselves.
    """
    if not settings.jira_configured:
        raise JiraError(
            "JIRA is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY."
        )

    fields = build_fields(story, epic_key=epic_key)
    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue"

    logger.info("Creating JIRA %s in project %s: %r", story.issue_type.value, settings.jira_project_key, story.summary)

    last_error: str | None = None
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json={"fields": fields},
                auth=(settings.jira_email, settings.jira_api_token),
                headers={"Content-Type": "application/json"},
            )

        if resp.status_code < 300:
            data = resp.json()
            key = data["key"]
            issue_url = f"{settings.jira_base_url.rstrip('/')}/browse/{key}"
            logger.info("Created %s: %s", key, issue_url)
            return {"key": key, "url": issue_url}

        last_error = f"JIRA API error {resp.status_code}: {resp.text}"
        logger.warning("JIRA create attempt %d/3 failed for %r: %s", attempt + 1, story.summary, last_error)
        if resp.status_code not in _RETRYABLE_STATUS or attempt == 2:
            break

    logger.error("Giving up creating %r in JIRA: %s", story.summary, last_error)
    raise JiraError(last_error or "Unknown JIRA error")


def build_update_fields(story: JiraItem, epic_key: str | None = None) -> dict:
    """Fields payload for updating an existing issue: project/issuetype are immutable in practice, so drop them."""
    fields = build_fields(story, epic_key=epic_key)
    fields.pop("project", None)
    fields.pop("issuetype", None)
    return fields


async def update_issue(key: str, story: JiraItem, epic_key: str | None = None) -> dict:
    """Update an existing JIRA issue in place via PUT. Raises JiraError on failure."""
    if not settings.jira_configured:
        raise JiraError(
            "JIRA is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY."
        )

    fields = build_update_fields(story, epic_key=epic_key)
    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue/{key}"
    issue_url = f"{settings.jira_base_url.rstrip('/')}/browse/{key}"

    logger.info("Updating JIRA %s: %r", key, story.summary)

    last_error: str | None = None
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                url,
                json={"fields": fields},
                auth=(settings.jira_email, settings.jira_api_token),
                headers={"Content-Type": "application/json"},
            )

        if resp.status_code < 300:
            logger.info("Updated %s: %s", key, issue_url)
            return {"key": key, "url": issue_url}

        last_error = f"JIRA API error {resp.status_code}: {resp.text}"
        logger.warning("JIRA update attempt %d/3 failed for %s: %s", attempt + 1, key, last_error)
        if resp.status_code not in _RETRYABLE_STATUS or attempt == 2:
            break

    logger.error("Giving up updating %s in JIRA: %s", key, last_error)
    raise JiraError(last_error or "Unknown JIRA error")


async def add_remote_link(issue_key: str, url: str, title: str, global_id: str | None = None) -> dict:
    """Attach a web link (e.g. to a Confluence reference page) to a JIRA issue. Passing `global_id`
    makes this idempotent — JIRA upserts on that id instead of creating a duplicate link if called again
    for the same issue."""
    if not settings.jira_configured:
        raise JiraError(
            "JIRA is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY."
        )

    api_url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/remotelink"
    payload: dict = {"object": {"url": url, "title": title}}
    if global_id:
        payload["globalId"] = global_id

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            api_url,
            json=payload,
            auth=(settings.jira_email, settings.jira_api_token),
            headers={"Content-Type": "application/json"},
        )
    if resp.status_code >= 300:
        raise JiraError(f"JIRA remote link failed {resp.status_code}: {resp.text}")
    return resp.json()


async def attach_file(issue_key: str, filename: str, content: bytes, content_type: str = "application/pdf") -> list[dict]:
    """Attach a file (e.g. a PDF pulled from a linked Confluence page) to an existing JIRA issue."""
    if not settings.jira_configured:
        raise JiraError(
            "JIRA is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY."
        )

    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/attachments"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            files={"file": (filename, content, content_type)},
            auth=(settings.jira_email, settings.jira_api_token),
            # Required by JIRA's attachment endpoint to bypass its XSRF check for non-browser clients.
            headers={"X-Atlassian-Token": "no-check"},
        )
    if resp.status_code >= 300:
        raise JiraError(f"JIRA attachment upload failed {resp.status_code}: {resp.text}")
    return resp.json()


async def search_epics(max_results: int = 50) -> list[dict]:
    """List Epics already in the configured JIRA project (key + summary), newest first. Used to find a
    reusable Epic before creating a new one, instead of creating a fresh Epic for every batch."""
    if not settings.jira_configured:
        raise JiraError(
            "JIRA is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY."
        )

    jql = f'project = "{settings.jira_project_key}" AND issuetype = Epic ORDER BY created DESC'
    # /rest/api/3/search/jql is the current JQL search endpoint (the older /rest/api/3/search was
    # deprecated/sunset by Atlassian).
    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/search/jql"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json={"jql": jql, "maxResults": max_results, "fields": ["summary"]},
            auth=(settings.jira_email, settings.jira_api_token),
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 300:
        raise JiraError(f"JIRA API error {resp.status_code}: {resp.text}")

    data = resp.json()
    return [{"key": issue["key"], "summary": issue["fields"]["summary"]} for issue in data.get("issues", [])]


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


async def find_matching_epic(candidate_title: str, threshold: float = 0.55) -> dict | None:
    """Search existing Epics in the project and return the closest match to `candidate_title` by simple
    summary-text similarity, if any clears `threshold`. Returns None if nothing is close enough — the
    caller decides whether to create a new Epic in that case."""
    try:
        epics = await search_epics()
    except JiraError as exc:
        logger.warning("Could not search existing epics (%s) — treating as none found", exc)
        return None

    best: dict | None = None
    best_score = 0.0
    for epic in epics:
        score = _title_similarity(candidate_title, epic["summary"])
        if score > best_score:
            best, best_score = epic, score

    if best and best_score >= threshold:
        logger.info("Matched existing epic %s (%.2f similarity) for %r", best["key"], best_score, candidate_title)
        return best
    return None
