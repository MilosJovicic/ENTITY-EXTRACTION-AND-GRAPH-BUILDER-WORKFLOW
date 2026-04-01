"""Activity 4: Relationship extraction using PydanticAI + Claude API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent
from temporalio import activity
from .prompts import system_prompt

from graph_normalization import (
    normalize_label,
    normalize_relationship_type,
)
from models import EmailHeaders, Relationship, RelationshipExtractionResult, ValidatedEntity


class ExtractedRelationships(BaseModel):
    """Structured output from Claude for relationship extraction."""

    email_intent: str
    topics: list[str]
    relationships: list[RelationshipEdge]


class RelationshipEdge(BaseModel):
    source: str
    source_label: str
    target: str
    target_label: str
    relation_type: str
    properties: dict[str, str] = Field(default_factory=dict)

    @field_validator("source_label", "target_label", mode="before")
    @classmethod
    def _normalize_entity_labels(cls, value: str) -> str:
        return normalize_label(value)

    @field_validator("relation_type", mode="before")
    @classmethod
    def _normalize_relation_type(cls, value: str) -> str:
        return normalize_relationship_type(value)

_relationship_agent: Agent | None = None


def _get_relationship_agent() -> Agent:
    global _relationship_agent
    if _relationship_agent is None:
        _relationship_agent = Agent(
            "anthropic:claude-sonnet-4-20250514",
            system_prompt=system_prompt,
            output_type=ExtractedRelationships,
        )
    return _relationship_agent


@activity.defn
async def extract_relationships(
    headers: EmailHeaders,
    entities: list[ValidatedEntity],
    email_body: str,
) -> RelationshipExtractionResult:
    """Extract relationships between entities using PydanticAI + Claude."""
    entity_list = "\n".join(
        f"- {ent.text} [{ent.label}] (confidence: {ent.score:.2f}, verified by: {ent.verified_by})"
        for ent in entities
    )

    prompt = (
        f"Email metadata:\n"
        f"  From: {headers.from_address}\n"
        f"  To: {', '.join(headers.to_addresses)}\n"
        f"  CC: {', '.join(headers.cc_addresses) or 'none'}\n"
        f"  Subject: {headers.subject}\n"
        f"  Date: {headers.date}\n\n"
        f"Extracted entities:\n{entity_list}\n\n"
        f"Email body:\n{email_body[:3000]}"
    )

    result = await _get_relationship_agent().run(prompt)
    output = result.output

    relationships = [
        Relationship(
            source=r.source,
            source_label=r.source_label,
            target=r.target,
            target_label=r.target_label,
            relation_type=r.relation_type,
            properties=r.properties,
        )
        for r in output.relationships
    ]

    activity.logger.info(
        "Extracted %d relationships, intent=%s, topics=%s",
        len(relationships),
        output.email_intent,
        output.topics,
    )

    return RelationshipExtractionResult(
        relationships=relationships,
        email_intent=output.email_intent,
        topics=output.topics,
    )
