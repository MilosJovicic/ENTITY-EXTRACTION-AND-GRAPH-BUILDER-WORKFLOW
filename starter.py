"""Start email processing workflows from the Enron emails CSV."""

import asyncio
import csv
import uuid

from dotenv import load_dotenv

load_dotenv()

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from models import EmailInput, EmailProcessingInput
from workflows.email_processing import EmailProcessingWorkflow

TASK_QUEUE = "email-entity-extraction"
CSV_PATH = "emails.csv"
BATCH_SIZE = 5  # Number of emails to process per run


async def main():
    client = await Client.connect(
        "localhost:7233",
        data_converter=pydantic_data_converter,
    )

    # Read emails from CSV
    with open(CSV_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        emails = []
        for i, row in enumerate(reader):
            if i >= BATCH_SIZE:
                break
            emails.append(
                EmailInput(file_path=row["file"], raw_message=row["message"])
            )

    print(f"Starting {len(emails)} email processing workflows...")

    # Start workflows concurrently
    handles = []
    for email_input in emails:
        workflow_id = f"email-{uuid.uuid4()}"
        handle = await client.start_workflow(
            EmailProcessingWorkflow.run,
            EmailProcessingInput(email=email_input),
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
        handles.append(handle)
        print(f"  Started workflow {workflow_id}")

    # Wait for all workflows to complete
    print("\nWaiting for workflows to complete...")
    for handle in handles:
        result = await handle.result()
        print(
            f"  {handle.id}: "
            f"{result.nodes_merged} nodes merged, "
            f"{result.relationships_created} relationships created"
        )

    print("\nAll workflows complete!")


if __name__ == "__main__":
    asyncio.run(main())
