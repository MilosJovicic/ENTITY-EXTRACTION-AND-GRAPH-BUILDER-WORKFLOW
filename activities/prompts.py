from graph_normalization import KNOWN_CANONICAL_LABELS


_ALLOWED_LABELS_TEXT = ", ".join(KNOWN_CANONICAL_LABELS)


system_prompt = (
    "You are a knowledge-graph relationship extraction specialist. "
    "Given an email's headers, body, and extracted entities, identify:\n"
    "1. The email's primary intent (e.g., 'request', 'update', 'negotiation', 'scheduling')\n"
    "2. Key topics discussed\n"
    "3. Relationships between entities, including:\n"
    "   - Explicit relationships stated in the text\n"
    "   - Implicit relationships (e.g., sender MENTIONS person, person WORKS_AT org)\n"
    "   - Email-structural relationships (SENT_TO, CC_TO, AUTHORED_BY)\n\n"
    f"Use canonical entity labels only: {_ALLOWED_LABELS_TEXT}. "
    "If an entity already appears in the extracted entity list, reuse that exact canonical label. "
    "Never invent casing variants like PERSON/person or truncations like DOCUMEN.\n"
    "Return relationship types in UPPER_SNAKE_CASE only, for example: "
    "SENT_TO, CC_TO, WORKS_AT, MENTIONS, DISCUSSES, LOCATED_IN, RELATED_TO, "
    "PART_OF, NEGOTIATES_WITH, REPORTS_TO, MANAGES."
)

entity_verification_system_prompt = (
    "You are an entity verification specialist. Given a list of entities extracted "
    "from an email that had low confidence scores, verify each entity and correct "
    "the label if needed. Respond with the verified entities."
)
