"""Temporal workflow: Entity Extraction and Graph Builder.

Orchestrates the 5-activity pipeline:
  1. Header extraction (deterministic)
  2. GLiNER2 entity extraction
  3. Confidence router → Claude verification for low-confidence
  4. Relationship extraction (PydanticAI + Claude)
  5. Neo4j graph writer
"""

import email
from datetime import timedelta
from email.policy import default as default_policy

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities.confidence_router import route_by_confidence, verify_entities_with_claude
    from activities.entity_extraction import extract_entities
    from activities.header_extraction import extract_headers
    from activities.neo4j_writer import write_to_neo4j
    from activities.relationship_extraction import extract_relationships
    from models import EmailProcessingInput, GraphWriteResult, ValidatedEntity


@workflow.defn
class EmailProcessingWorkflow:
    """Process a single email through the full entity extraction → graph pipeline."""

    @workflow.run
    async def run(self, input: EmailProcessingInput) -> GraphWriteResult:
        # ── Activity 1: Header extraction (deterministic, no LLM) ──
        headers = await workflow.execute_activity(
            extract_headers,
            input.email,
            start_to_close_timeout=timedelta(seconds=10),
        )

        # ── Activity 2: GLiNER2 entity extraction ──
        entities = await workflow.execute_activity(
            extract_entities,
            args=[input.email, input.entity_labels],
            start_to_close_timeout=timedelta(seconds=60),
        )

        # ── Activity 3: Confidence router ──
        routed = await workflow.execute_activity(
            route_by_confidence,
            args=[entities, input.confidence_threshold],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # If there are low-confidence entities, verify with Claude
        all_entities: list[ValidatedEntity] = list(routed.high_confidence)

        if routed.low_confidence:
            # Extract email body for context
            msg = email.message_from_string(
                input.email.raw_message, policy=default_policy
            )
            body_part = msg.get_body(preferencelist=("plain",))
            email_body = body_part.get_content() if body_part else input.email.raw_message

            claude_verified = await workflow.execute_activity(
                verify_entities_with_claude,
                args=[routed.low_confidence, email_body],
                start_to_close_timeout=timedelta(seconds=30),
            )
            all_entities.extend(claude_verified)

        # ── Activity 4: Relationship extraction (PydanticAI + Claude) ──
        msg = email.message_from_string(
            input.email.raw_message, policy=default_policy
        )
        body_part = msg.get_body(preferencelist=("plain",))
        email_body = body_part.get_content() if body_part else input.email.raw_message

        relationships = await workflow.execute_activity(
            extract_relationships,
            args=[headers, all_entities, email_body],
            start_to_close_timeout=timedelta(seconds=60),
        )

        # ── Activity 5: Neo4j writer ──
        result = await workflow.execute_activity(
            write_to_neo4j,
            args=[headers, all_entities, relationships],
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info(
            "Email %s processed: %d nodes merged, %d relationships created",
            headers.message_id,
            result.nodes_merged,
            result.relationships_created,
        )

        return result
