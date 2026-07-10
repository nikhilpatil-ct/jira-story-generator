from enum import Enum

from pydantic import BaseModel, Field


class Priority(str, Enum):
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"


class IssueType(str, Enum):
    STORY = "Story"
    TASK = "Task"
    BUG = "Bug"


class ExtractedRequirement(BaseModel):
    title: str = Field(description="Short working title for this requirement")
    raw_description: str = Field(
        description="The relevant portion of the source text this requirement is based on, summarized in the analyst's own words"
    )
    rationale: str = Field(description="Why this was identified as a distinct, independently deliverable story")


class ExtractionResult(BaseModel):
    requirements: list[ExtractedRequirement]
    open_questions: list[str] = Field(
        default_factory=list,
        description="Ambiguities or missing details in the source text that would materially improve story quality if clarified",
    )


class JiraStory(BaseModel):
    summary: str = Field(description="Concise JIRA issue summary/title, under 100 characters")
    user_story: str = Field(
        description="Story in 'As a <role>, I want <capability>, so that <benefit>' format"
    )
    description: str = Field(description="Additional context and background for the story")
    acceptance_criteria: list[str] = Field(
        description="3-6 concrete, testable acceptance criteria, each a single self-contained statement"
    )
    story_points: int | None = Field(
        default=None,
        description="Estimated effort on a Fibonacci-like scale (1, 2, 3, 5, 8, 13). Null only if truly not estimable.",
    )
    priority: Priority
    labels: list[str] = Field(default_factory=list)
    issue_type: IssueType = IssueType.STORY


class ValidationIssue(BaseModel):
    field: str = Field(description="Which part of the story has the problem, e.g. 'acceptance_criteria'")
    problem: str
    suggestion: str


class ValidationResult(BaseModel):
    is_valid: bool = Field(description="True only if the story is genuinely ready for a sprint")
    score: int = Field(description="Overall quality score from 0-100 against INVEST criteria")
    issues: list[ValidationIssue] = Field(default_factory=list)


class GeneratedStory(BaseModel):
    story: JiraStory
    validation: ValidationResult
    attempts: int


class OrchestratorAction(str, Enum):
    ASK_CLARIFICATION = "ask_clarification"
    READY_TO_GENERATE = "ready_to_generate"
    CONFIRM_CREATE = "confirm_create"
    REVISE = "revise"
    CHAT = "chat"


class OrchestratorDecision(BaseModel):
    action: OrchestratorAction
    message_to_user: str = Field(description="What to say back to the user right now")
    target_story_index: int | None = Field(
        default=None, description="0-based index of the story being revised, only set for the 'revise' action"
    )
    revision_instructions: str | None = Field(
        default=None, description="Specific instructions for revision, only set for the 'revise' action"
    )
