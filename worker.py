"""Temporal worker for the Entity Extraction and Graph Builder pipeline."""

import asyncio
import concurrent.futures

from dotenv import load_dotenv

load_dotenv()

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from activities.confidence_router import route_by_confidence, verify_entities_with_claude
from activities.entity_extraction import extract_entities
from activities.header_extraction import extract_headers
from activities.neo4j_writer import write_to_neo4j
from activities.relationship_extraction import extract_relationships
from workflows.email_processing import EmailProcessingWorkflow

TASK_QUEUE = "email-entity-extraction"


async def main():
    client = await Client.connect(
        "localhost:7233",
        data_converter=pydantic_data_converter,
    )

    # Sync activities (header extraction, GLiNER, confidence router, neo4j)
    # run on a thread pool executor; async activities (Claude calls) run on
    # the event loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[EmailProcessingWorkflow],
            activities=[
                extract_headers,
                extract_entities,
                route_by_confidence,
                verify_entities_with_claude,
                extract_relationships,
                write_to_neo4j,
            ],
            activity_executor=executor,
        )
        print(f"Worker started, listening on task queue: {TASK_QUEUE}")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
