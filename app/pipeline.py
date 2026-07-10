from app.agents import drafter, extractor, validator
from app.config import settings
from app.models.schemas import GeneratedStory


async def generate_stories(conversation_text: str) -> tuple[list[GeneratedStory], list[str]]:
    """Run the extract -> draft -> validate -> refine pipeline over raw conversation text."""
    extraction = await extractor.extract(conversation_text)

    generated: list[GeneratedStory] = []
    for requirement in extraction.requirements:
        story = await drafter.draft(requirement, conversation_text)
        attempts = 1
        result = await validator.validate(story)

        while (
            not result.is_valid
            and result.score < settings.validation_pass_score
            and attempts < settings.max_refinement_attempts
        ):
            feedback = "\n".join(f"- [{issue.field}] {issue.problem} -> {issue.suggestion}" for issue in result.issues)
            story = await drafter.refine(story, feedback)
            result = await validator.validate(story)
            attempts += 1

        generated.append(GeneratedStory(story=story, validation=result, attempts=attempts))

    return generated, extraction.open_questions
