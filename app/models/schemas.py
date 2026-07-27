from enum import Enum
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class Priority(str, Enum):
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"


class IssueType(str, Enum):
    EPIC = "Epic"
    STORY = "Story"
    TASK = "Task"
    BUG = "Bug"


class SourceType(str, Enum):
    """How the raw input should be preprocessed and extracted. `transcript` = spoken meeting dialogue
    (gets ASR/filler cleanup, boundaries inferred); `document` = an already-structured requirements
    doc such as a BRD/PRD (whitespace-only cleanup, itemization preserved)."""

    TRANSCRIPT = "transcript"
    DOCUMENT = "document"


class Severity(str, Enum):
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"
    TRIVIAL = "Trivial"


class ExtractedRequirement(BaseModel):
    title: str = Field(description="Short working title for this requirement")
    raw_description: str = Field(
        description="The relevant portion of the source text this requirement is based on, summarized in the analyst's own words"
    )
    rationale: str = Field(description="Why this was identified as a distinct, independently deliverable story")
    issue_type: IssueType = Field(
        description="Epic for a large multi-story initiative/theme, Bug for a reported defect or broken behavior, "
        "Story for a normal independently shippable increment of value"
    )


class ExtractionResult(BaseModel):
    requirements: list[ExtractedRequirement]
    action_items: list[str] = Field(
        default_factory=list,
        description="Concrete follow-up tasks or to-dos mentioned that are not themselves full stories (e.g. 'schedule a follow-up with design')",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Risks, blockers, or concerns raised in the source text (technical, scheduling, or business)",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Ambiguities or missing details in the source text that would materially improve story quality if clarified",
    )


# Each issue type gets its own focused schema rather than one combined model: Claude's structured-output
# grammar compiler rejects/times out on a single schema mixing all Epic+Story+Bug fields ("Schema is too
# complex" / "Grammar compilation timed out"), so each LLM call is made against one narrow schema.


class JiraEpic(BaseModel):
    issue_type: Literal[IssueType.EPIC] = IssueType.EPIC
    summary: str = Field(description="Concise JIRA issue summary/title, under 100 characters")
    description: str = Field(description="Additional context and background for the epic")
    priority: Priority
    labels: list[str] = Field(default_factory=list)
    business_value: str = Field(description="The business value/why this epic matters")
    goal: str = Field(description="The overall goal/outcome of the epic")
    success_criteria: list[str] = Field(description="3-6 measurable criteria for the epic being complete")


class JiraUserStory(BaseModel):
    issue_type: Literal[IssueType.STORY] = IssueType.STORY
    summary: str = Field(description="Concise JIRA issue summary/title, under 100 characters")
    description: str = Field(description="Additional context and background for the story")
    priority: Priority
    labels: list[str] = Field(default_factory=list)
    user_story: str = Field(description="'As a <role>, I want <capability>, so that <benefit>'")
    acceptance_criteria: list[str] = Field(
        description="3-6 concrete, testable acceptance criteria, each a single self-contained statement"
    )
    story_points: int | None = Field(
        default=None,
        description="Estimated effort on a Fibonacci-like scale (1, 2, 3, 5, 8, 13). Null only if truly not estimable.",
    )


class JiraBug(BaseModel):
    issue_type: Literal[IssueType.BUG] = IssueType.BUG
    summary: str = Field(description="Concise JIRA issue summary/title, under 100 characters")
    description: str = Field(description="Additional context and background for the bug")
    priority: Priority
    labels: list[str] = Field(default_factory=list)
    steps_to_reproduce: list[str] = Field(description="Ordered, concrete repro steps")
    expected_result: str = Field(description="What should happen")
    actual_result: str = Field(description="What actually happens")
    severity: Severity
    environment: str | None = Field(default=None, description="Browser/OS/deployment context if mentioned")
    root_cause: str | None = Field(default=None, description="Only if inferable from the source text")


JiraItem = Annotated[Union[JiraEpic, JiraUserStory, JiraBug], Field(discriminator="issue_type")]


class ClarifyingQuestionDraft(BaseModel):
    """One question the drafter needs answered before it can write an item without inventing details."""

    question: str = Field(
        description="A single, concrete, self-contained question a stakeholder can answer in one sentence"
    )
    reason: str = Field(
        description="Short note naming exactly which part of the item this affects and what would otherwise be guessed"
    )


class ClarificationCheck(BaseModel):
    """Result of reviewing one requirement for must-ask ambiguities before drafting."""

    questions: list[ClarifyingQuestionDraft] = Field(
        default_factory=list,
        description="Empty when the source text and app context already contain everything needed. Otherwise the "
        "minimal set of questions whose answers would materially change the drafted item.",
    )


class ValidationIssue(BaseModel):
    field: str = Field(description="Which part of the story has the problem, e.g. 'acceptance_criteria'")
    problem: str
    suggestion: str


class ValidationResult(BaseModel):
    is_valid: bool = Field(description="True only if the story is genuinely ready for a sprint")
    score: int = Field(description="Overall quality score from 0-100 against INVEST criteria")
    issues: list[ValidationIssue] = Field(default_factory=list)


class TestCase(BaseModel):
    title: str = Field(description="Short name for the test case")
    steps: list[str] = Field(description="Ordered steps to execute the test")
    expected_result: str = Field(description="What should happen if the item behaves correctly")


class TestCasesResult(BaseModel):
    test_cases: list[TestCase]


class RiskItem(BaseModel):
    risk: str = Field(description="The risk itself")
    impact: str = Field(description="What happens if it materializes")
    mitigation: str = Field(description="Concrete suggestion to reduce or handle the risk")


class RiskAnalysisResult(BaseModel):
    risks: list[RiskItem]


class GeneratedStory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    story: JiraItem
    validation: ValidationResult
    attempts: int
    test_cases: list[TestCase] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


class OrchestratorAction(str, Enum):
    ASK_CLARIFICATION = "ask_clarification"
    READY_TO_GENERATE = "ready_to_generate"
    CONFIRM_CREATE = "confirm_create"
    REVISE = "revise"
    REGENERATE = "regenerate"
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
    generation_scope: list[IssueType] | None = Field(
        default=None,
        description="Set for 'ready_to_generate' or 'regenerate' when the user asked to limit generation to "
        "specific issue types (e.g. 'generate bugs only' -> [Bug], 'generate the epic' -> [Epic]). "
        "Null/omitted means generate everything found.",
    )
