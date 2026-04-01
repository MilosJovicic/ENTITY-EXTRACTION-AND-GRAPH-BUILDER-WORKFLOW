"""Activity 2: GLiNER2 entity extraction."""

import email
from email.policy import default as default_policy

from gliner import GLiNER
from temporalio import activity

from models import EmailInput, ExtractedEntity

_model: GLiNER | None = None


def _get_model() -> GLiNER:
    """Lazy-load GLiNER model (cached across activity invocations)."""
    global _model
    if _model is None:
        activity.logger.info("Loading GLiNER model (first call)...")
        _model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
    return _model


def _get_body(raw_message: str) -> str:
    """Extract the plain-text body from a raw email message."""
    msg = email.message_from_string(raw_message, policy=default_policy)
    body = msg.get_body(preferencelist=("plain",))
    if body:
        return body.get_content()
    return raw_message


@activity.defn
def extract_entities(email_input: EmailInput, labels: list[str]) -> list[ExtractedEntity]:
    """Run GLiNER NER over the email body and return scored entities."""
    model = _get_model()
    body = _get_body(email_input.raw_message)

    if not body.strip():
        activity.logger.warning("Empty email body for %s", email_input.file_path)
        return []

    raw_entities = model.predict_entities(body, labels, threshold=0.3)

    entities: list[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()

    for ent in raw_entities:
        key = (ent["text"].strip(), ent["label"])
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            ExtractedEntity(
                text=ent["text"].strip(),
                label=ent["label"],
                score=round(ent["score"], 4),
            )
        )

    activity.logger.info(
        "GLiNER extracted %d entities from %s", len(entities), email_input.file_path
    )
    return entities
