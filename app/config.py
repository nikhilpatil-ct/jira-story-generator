import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    translation_model: str = os.getenv("TRANSLATION_MODEL", "claude-haiku-4-5-20251001")

    max_refinement_attempts: int = int(os.getenv("MAX_REFINEMENT_ATTEMPTS", "2"))
    validation_pass_score: int = int(os.getenv("VALIDATION_PASS_SCORE", "75"))
    # When auto-create is on, only items scoring at or above this bar are pushed to JIRA automatically.
    # Anything below it is held back for a BA to review and update before creating manually — auto-pushing
    # a weak story to a real project is hard to walk back.
    auto_create_min_score: int = int(os.getenv("AUTO_CREATE_MIN_SCORE", "70"))

    # Before drafting each item, ask the user targeted questions rather than inventing missing details.
    # Each concurrent draft can raise its own questions; the pipeline waits (without holding a draft slot)
    # until the user answers/skips or clarification_timeout_seconds elapses, then drafts with what it has.
    clarifying_questions_enabled: bool = os.getenv("CLARIFYING_QUESTIONS_ENABLED", "true").lower() == "true"
    max_clarifying_questions_per_item: int = int(os.getenv("MAX_CLARIFYING_QUESTIONS_PER_ITEM", "3"))
    clarification_timeout_seconds: float = float(os.getenv("CLARIFICATION_TIMEOUT_SECONDS", "300"))

    # Draft/validate each extracted requirement concurrently, bounded so we don't blow past API rate limits.
    max_concurrent_drafts: int = int(os.getenv("MAX_CONCURRENT_DRAFTS", "20"))
    # Retry transient API failures (timeouts, connection drops, 429s, 5xx) with exponential backoff.
    max_api_retries: int = int(os.getenv("MAX_API_RETRIES", "3"))
    api_retry_base_delay: float = float(os.getenv("API_RETRY_BASE_DELAY", "1.0"))

    jira_base_url: str | None = (os.getenv("JIRA_BASE_URL") or "").strip() or None
    jira_email: str | None = (os.getenv("JIRA_EMAIL") or "").strip() or None
    jira_api_token: str | None = (os.getenv("JIRA_API_TOKEN") or "").strip() or None
    jira_project_key: str | None = (os.getenv("JIRA_PROJECT_KEY") or "").strip() or None
    jira_story_points_field: str | None = (os.getenv("JIRA_STORY_POINTS_FIELD") or "").strip() or None
    # Field used to attach a Story/Bug/Task to its parent Epic. Team-managed (default) Cloud projects
    # use the native "parent" field; a classic company-managed project still on the legacy Epic Link
    # needs its custom field id here instead (e.g. "customfield_10014").
    jira_epic_link_field: str | None = (os.getenv("JIRA_EPIC_LINK_FIELD") or "").strip() or None

    @property
    def jira_configured(self) -> bool:
        return all([self.jira_base_url, self.jira_email, self.jira_api_token, self.jira_project_key])

    # Confluence Cloud — same Atlassian account as JIRA above, so it reuses jira_email/jira_api_token
    # rather than needing its own credentials.
    confluence_base_url: str | None = (os.getenv("CONFLUENCE_BASE_URL") or "").strip() or None
    confluence_page_id: str | None = (os.getenv("CONFLUENCE_PAGE_ID") or "").strip() or None

    @property
    def confluence_configured(self) -> bool:
        return all([self.confluence_base_url, self.confluence_page_id, self.jira_email, self.jira_api_token])


settings = Settings()
