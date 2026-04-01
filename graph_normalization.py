"""Shared normalization helpers for graph labels and relationship types."""

from __future__ import annotations

import re

_CANONICAL_LABEL_ALIASES = {
    "concept": "Concept",
    "document": "Document",
    "documen": "Document",
    "documents": "Document",
    "email": "Email",
    "event": "Event",
    "legalterm": "LegalTerm",
    "legalterms": "LegalTerm",
    "location": "Location",
    "locations": "Location",
    "monetary": "MonetaryValue",
    "monetaryvalue": "MonetaryValue",
    "monetaryvalues": "MonetaryValue",
    "organization": "Organization",
    "organizations": "Organization",
    "organisation": "Organization",
    "organisations": "Organization",
    "person": "Person",
    "persons": "Person",
    "people": "Person",
    "project": "Project",
    "projects": "Project",
    "time": "Time",
}

_CANONICAL_LABEL_PREFIXES = {
    "documen": "Document",
    "monetary": "MonetaryValue",
    "organiz": "Organization",
    "organis": "Organization",
    "person": "Person",
}

KNOWN_CANONICAL_LABELS = tuple(
    sorted(set(_CANONICAL_LABEL_ALIASES.values()))
)


def normalize_label(label: str, default: str = "Entity") -> str:
    """Normalize free-form labels into stable, canonical Neo4j labels."""
    collapsed = re.sub(r"[^0-9A-Za-z]+", "", label or "").lower()
    if not collapsed:
        return default

    if collapsed in _CANONICAL_LABEL_ALIASES:
        return _CANONICAL_LABEL_ALIASES[collapsed]

    for prefix, canonical in _CANONICAL_LABEL_PREFIXES.items():
        if collapsed.startswith(prefix):
            return canonical

    parts = re.findall(r"[A-Za-z0-9]+", label or "")
    if not parts:
        return default

    normalized = "".join(part[:1].upper() + part[1:].lower() for part in parts)
    if normalized[0].isdigit():
        return f"{default}{normalized}"
    return normalized


def normalize_relationship_type(rel_type: str, default: str = "RELATED_TO") -> str:
    """Normalize free-form relationship names into Neo4j-safe relationship types."""
    parts = re.findall(r"[A-Za-z0-9]+", rel_type or "")
    if not parts:
        return default

    normalized = "_".join(part.upper() for part in parts)
    if normalized[0].isdigit():
        return f"REL_{normalized}"
    return normalized
