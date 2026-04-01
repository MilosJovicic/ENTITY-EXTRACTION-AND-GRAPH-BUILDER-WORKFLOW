"""Activity 3: Confidence router + PydanticAI/Claude verification for low-confidence entities."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent
from temporalio import activity
from .prompts import entity_verification_system_prompt

from models import ConfidenceRouterResult, ExtractedEntity, ValidatedEntity


class VerifiedEntities(BaseModel):
    """Structured output from Claude verification."""

    entities: list[VerifiedEntity]


class VerifiedEntity(BaseModel):
    text: str
    label: str
    is_valid: bool
    corrected_label: str | None = None


_verification_agent: Agent | None = None


def _get_verification_agent() -> Agent:
    global _verification_agent
    if _verification_agent is None:
        _verification_agent = Agent(
            "anthropic:claude-sonnet-4-20250514",
            system_prompt=entity_verification_system_prompt,
            
            
            output_type=VerifiedEntities,
        )
    return _verification_agent


@activity.defn
def route_by_confidence(
    entities: list[ExtractedEntity], threshold: float
) -> ConfidenceRouterResult:
    """Split entities into high/low confidence buckets (deterministic, no I/O)."""
    high: list[ValidatedEntity] = []
    low: list[ExtractedEntity] = []

    for ent in entities:
        if ent.score >= threshold:
            high.append(
                ValidatedEntity(
                    text=ent.text,
                    label=ent.label,
                    score=ent.score,
                    verified_by="gliner",
                )
            )
        else:
            low.append(ent)

    activity.logger.info(
        "Confidence router: %d high (>= %.2f), %d low", len(high), threshold, len(low)
    )
    return ConfidenceRouterResult(high_confidence=high, low_confidence=low)


@activity.defn
async def verify_entities_with_claude(
    low_confidence_entities: list[ExtractedEntity],
    email_body: str,
) -> list[ValidatedEntity]:
    """Use PydanticAI + Claude to verify and re-extract low-confidence entities."""
    if not low_confidence_entities:
        return []

    entity_descriptions = "\n".join(
        f"- '{ent.text}' (label: {ent.label}, score: {ent.score:.2f})"
        for ent in low_confidence_entities
    )

    prompt = (
        f"The following entities were extracted from an email but had low confidence scores.\n"
        f"Please verify each one against the email content and correct labels if needed.\n\n"
        f"Entities to verify:\n{entity_descriptions}\n\n"
        f"Email content:\n{email_body[:3000]}"
    )

    result = await _get_verification_agent().run(prompt)

    validated: list[ValidatedEntity] = []
    for verified in result.output.entities:
        if verified.is_valid:
            validated.append(
                ValidatedEntity(
                    text=verified.text,
                    label=verified.corrected_label or verified.label,
                    score=0.85,  # Claude-verified confidence
                    verified_by="claude",
                )
            )

    activity.logger.info(
        "Claude verified %d/%d low-confidence entities",
        len(validated),
        len(low_confidence_entities),
    )
    return validated
