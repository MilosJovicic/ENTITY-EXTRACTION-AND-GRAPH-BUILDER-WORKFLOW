"""Activity 5: Neo4j graph writer — MERGE entities and relationships."""

from __future__ import annotations

import os

from neo4j import GraphDatabase
from temporalio import activity

from graph_normalization import normalize_label, normalize_relationship_type

from models import (
    EmailHeaders,
    GraphWriteResult,
    Relationship,
    RelationshipExtractionResult,
    ValidatedEntity,
)

_driver = None
_database = None
_connection_logged = False


def _get_driver():
    """Lazy-init Neo4j driver (cached across activity invocations)."""
    global _driver, _database, _connection_logged
    if _driver is None:
        uri = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD")
        _database = os.environ.get("NEO4J_DATABASE", "neo4j")
        if not password:
            raise RuntimeError("NEO4J_PASSWORD must be set in the environment.")
        _driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            _driver.verify_connectivity()
            with _driver.session(database=_database) as session:
                session.run("RETURN 1 AS ok").consume()
        except Exception as exc:
            _driver.close()
            _driver = None
            raise RuntimeError(
                f"Unable to connect to Neo4j database '{_database}'. "
                "Check NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, and NEO4J_DATABASE."
            ) from exc

    if not _connection_logged:
        activity.logger.info("Connected to Neo4j database '%s'", _database)
        _connection_logged = True

    return _driver


def _merge_entity(tx, entity: ValidatedEntity) -> None:
    """MERGE a single entity node, creating or updating it."""
    label = normalize_label(entity.label)
    query = (
        f"MERGE (n:{label} {{name: $name}}) "
        "SET n.confidence = $score, n.verified_by = $verified_by"
    )
    tx.run(query, name=entity.text, score=entity.score, verified_by=entity.verified_by)


def _merge_email_node(tx, headers: EmailHeaders) -> None:
    """MERGE the Email node itself."""
    tx.run(
        "MERGE (e:Email {message_id: $message_id}) "
        "SET e.subject = $subject, e.date = $date, e.from_address = $from_address",
        message_id=headers.message_id,
        subject=headers.subject,
        date=headers.date,
        from_address=headers.from_address,
    )


def _merge_relationship(tx, rel: Relationship) -> None:
    """MERGE a relationship between two entity nodes."""
    source_label = normalize_label(rel.source_label)
    target_label = normalize_label(rel.target_label)
    relation_type = normalize_relationship_type(rel.relation_type)
    query = (
        f"MERGE (a:{source_label} {{name: $source}}) "
        f"MERGE (b:{target_label} {{name: $target}}) "
        f"MERGE (a)-[r:{relation_type}]->(b) "
        "SET r += $properties"
    )
    tx.run(
        query,
        source=rel.source,
        target=rel.target,
        properties=rel.properties,
    )


def _merge_email_participant(tx, headers: EmailHeaders, address: str, rel_type: str) -> None:
    """MERGE a Person node for an email participant and link to the Email."""
    tx.run(
        "MERGE (p:Person {email: $address}) "
        "MERGE (e:Email {message_id: $message_id}) "
        f"MERGE (e)-[:{rel_type}]->(p)",
        address=address,
        message_id=headers.message_id,
    )


@activity.defn
def write_to_neo4j(
    headers: EmailHeaders,
    entities: list[ValidatedEntity],
    extraction_result: RelationshipExtractionResult,
) -> GraphWriteResult:
    """Write entities and relationships to Neo4j using MERGE for idempotency."""
    driver = _get_driver()
    nodes_created = 0
    nodes_merged = 0
    relationships_created = 0

    with driver.session(database=_database) as session:
        # 1. MERGE the Email node
        session.execute_write(_merge_email_node, headers)
        nodes_merged += 1

        # 2. MERGE email participants (From, To, CC, BCC)
        session.execute_write(
            _merge_email_participant, headers, headers.from_address, "SENT_BY"
        )
        relationships_created += 1

        for addr in headers.to_addresses:
            session.execute_write(_merge_email_participant, headers, addr, "SENT_TO")
            relationships_created += 1

        for addr in headers.cc_addresses:
            session.execute_write(_merge_email_participant, headers, addr, "CC_TO")
            relationships_created += 1

        for addr in headers.bcc_addresses:
            session.execute_write(_merge_email_participant, headers, addr, "BCC_TO")
            relationships_created += 1

        # 3. MERGE entity nodes
        for entity in entities:
            session.execute_write(_merge_entity, entity)
            nodes_merged += 1

        # 4. MERGE extracted relationships
        for rel in extraction_result.relationships:
            session.execute_write(_merge_relationship, rel)
            relationships_created += 1

        # 5. MERGE email metadata (intent, topics)
        session.execute_write(
            lambda tx: tx.run(
                "MERGE (e:Email {message_id: $message_id}) "
                "SET e.intent = $intent, e.topics = $topics",
                message_id=headers.message_id,
                intent=extraction_result.email_intent,
                topics=extraction_result.topics,
            ),
            # no extra args needed — lambda closes over the values
        )

    activity.logger.info(
        "Neo4j write complete in database '%s': %d nodes merged, %d relationships created",
        _database,
        nodes_merged,
        relationships_created,
    )

    return GraphWriteResult(
        nodes_created=nodes_created,
        nodes_merged=nodes_merged,
        relationships_created=relationships_created,
    )
