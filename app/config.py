import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    translation_model: str = os.getenv("TRANSLATION_MODEL", "claude-haiku-4-5-20251001")

    max_refinement_attempts: int = int(os.getenv("MAX_REFINEMENT_ATTEMPTS", "2"))
    validation_pass_score: int = int(os.getenv("VALIDATION_PASS_SCORE", "75"))

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

    @property
    def jira_configured(self) -> bool:
        return all([self.jira_base_url, self.jira_email, self.jira_api_token, self.jira_project_key])


settings = Settings()
