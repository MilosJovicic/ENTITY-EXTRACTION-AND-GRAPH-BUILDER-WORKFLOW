from __future__ import annotations

from pydantic import BaseModel


class EmailInput(BaseModel):
    file_path: str
    raw_message: str


class EmailHeaders(BaseModel):
    message_id: str
    date: str
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    bcc_addresses: list[str]
    subject: str


class ExtractedEntity(BaseModel):
    text: str
    label: str
    score: float


class EntityExtractionResult(BaseModel):
    headers: EmailHeaders
    entities: list[ExtractedEntity]


class ValidatedEntity(BaseModel):
    text: str
    label: str
    score: float
    verified_by: str  # "gliner" or "claude"


class ConfidenceRouterResult(BaseModel):
    high_confidence: list[ValidatedEntity]
    low_confidence: list[ExtractedEntity]


class Relationship(BaseModel):
    source: str
    source_label: str
    target: str
    target_label: str
    relation_type: str
    properties: dict[str, str] = {}


class RelationshipExtractionResult(BaseModel):
    relationships: list[Relationship]
    email_intent: str
    topics: list[str]


class GraphWriteResult(BaseModel):
    nodes_created: int
    nodes_merged: int
    relationships_created: int


class EmailProcessingInput(BaseModel):
    email: EmailInput
    entity_labels: list[str] = [
        "Person",
        "Organization",
        "Location",
        "Project",
        "MonetaryValue",
        "LegalTerm",
    ]
    confidence_threshold: float = 0.7
