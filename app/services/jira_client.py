import httpx

from app.config import settings
from app.models.schemas import JiraStory


class JiraError(Exception):
    pass


def _build_adf_description(story: JiraStory) -> dict:
    content: list[dict] = [
        {"type": "paragraph", "content": [{"type": "text", "text": story.user_story}]},
    ]
    if story.description:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": story.description}]})
    if story.acceptance_criteria:
        content.append(
            {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Acceptance Criteria"}]}
        )
        content.append(
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": ac}]}]}
                    for ac in story.acceptance_criteria
                ],
            }
        )
    return {"type": "doc", "version": 1, "content": content}


async def create_issue(story: JiraStory) -> dict:
    """Create a single issue in JIRA via the Cloud REST API v3. Raises JiraError on failure."""
    if not settings.jira_configured:
        raise JiraError(
            "JIRA is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY."
        )

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
    if story.story_points is not None and settings.jira_story_points_field:
        fields[settings.jira_story_points_field] = story.story_points

    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json={"fields": fields},
            auth=(settings.jira_email, settings.jira_api_token),
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code >= 300:
        raise JiraError(f"JIRA API error {resp.status_code}: {resp.text}")

    data = resp.json()
    key = data["key"]
    return {"key": key, "url": f"{settings.jira_base_url.rstrip('/')}/browse/{key}"}
