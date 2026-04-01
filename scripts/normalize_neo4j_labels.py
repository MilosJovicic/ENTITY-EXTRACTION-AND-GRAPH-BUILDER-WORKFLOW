"""Normalize existing Neo4j node labels in-place using the shared label rules."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from graph_normalization import normalize_label


def _quote_identifier(value: str) -> str:
    return f"`{value.replace('`', '``')}`"


def main() -> None:
    load_dotenv(dotenv_path=Path(".env"))

    uri = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD must be set in the environment.")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session(database=database) as session:
        labels = [
            row["label"]
            for row in session.run(
                "CALL db.labels() YIELD label RETURN label ORDER BY label"
            )
        ]

        changes: list[tuple[str, str, int]] = []
        for label in labels:
            normalized = normalize_label(label)
            if normalized == label:
                continue

            result = session.run(
                f"MATCH (n:{_quote_identifier(label)}) "
                f"SET n:{_quote_identifier(normalized)} "
                f"REMOVE n:{_quote_identifier(label)} "
                "RETURN count(n) AS relabeled"
            ).single()
            changes.append((label, normalized, result["relabeled"]))

    driver.close()

    if not changes:
        print("No label changes were needed.")
        return

    for old_label, new_label, count in changes:
        print(f"{old_label} -> {new_label}: {count} node(s)")


if __name__ == "__main__":
    main()
