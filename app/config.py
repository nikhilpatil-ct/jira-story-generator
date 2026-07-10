import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    max_refinement_attempts: int = int(os.getenv("MAX_REFINEMENT_ATTEMPTS", "2"))
    validation_pass_score: int = int(os.getenv("VALIDATION_PASS_SCORE", "75"))

    jira_base_url: str | None = os.getenv("JIRA_BASE_URL") or None
    jira_email: str | None = os.getenv("JIRA_EMAIL") or None
    jira_api_token: str | None = os.getenv("JIRA_API_TOKEN") or None
    jira_project_key: str | None = os.getenv("JIRA_PROJECT_KEY") or None
    jira_story_points_field: str | None = os.getenv("JIRA_STORY_POINTS_FIELD") or None

    @property
    def jira_configured(self) -> bool:
        return all([self.jira_base_url, self.jira_email, self.jira_api_token, self.jira_project_key])


settings = Settings()
