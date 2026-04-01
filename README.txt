ENTITY EXTRACTION AND GRAPH BUILDER WORKFLOW
============================================

Overview
--------
This project uses Temporal to process raw emails from `emails.csv`, extract
entities and relationships, and write the result into a Neo4j knowledge graph.

The code is organized around one Temporal workflow:

  EmailProcessingWorkflow

That workflow orchestrates a set of activities for parsing email metadata,
running NER, verifying uncertain entities, extracting relationships, and
persisting the graph.


SYSTEM STRUCTURE
----------------

                                  +----------------------+
                                  |      emails.csv      |
                                  |  Source email batch  |
                                  +----------+-----------+
                                             |
                                             v
                           +-----------------+-----------------+
                           |             starter.py            |
                           |  - reads CSV rows                 |
                           |  - builds EmailInput objects      |
                           |  - starts Temporal workflows      |
                           +-----------------+-----------------+
                                             |
                                             v
                    +------------------------+------------------------+
                    |      Temporal Server / Task Queue               |
                    |      queue: email-entity-extraction             |
                    +------------------------+------------------------+
                                             |
                                             v
                           +-----------------+-----------------+
                           |              worker.py            |
                           |  Registers:                       |
                           |  - EmailProcessingWorkflow        |
                           |  - 6 activities                   |
                           |  Uses Pydantic data conversion    |
                           +-----------------+-----------------+
                                             |
                                             v
    +--------------------------------------------------------------------------------+
    |                workflows/email_processing.py                                    |
    |                                                                                |
    |  EmailProcessingWorkflow.run(EmailProcessingInput)                              |
    |                                                                                |
    |  1. extract_headers(email)                                                     |
    |  2. extract_entities(email, labels)                                            |
    |  3. route_by_confidence(entities, threshold)                                   |
    |  4. verify_entities_with_claude(...)      [only if low-confidence entities]    |
    |  5. extract_relationships(headers, entities, email_body)                       |
    |  6. write_to_neo4j(headers, entities, relationships)                           |
    +--------------------------------------------------------------------------------+
             |                         |                         |              |
             v                         v                         v              v
    +------------------+     +------------------+     +----------------+  +----------------+
    | Local parsing    |     | GLiNER model     |     | Claude via     |  | Neo4j database |
    | email headers    |     | entity extraction|     | PydanticAI     |  | graph storage  |
    +------------------+     +------------------+     +----------------+  +----------------+


PER-EMAIL PIPELINE
------------------

    EmailInput
       |
       v
    +------------------------------+
    | 1) Header Extraction         |
    | activities/header_extraction |
    | Output: EmailHeaders         |
    +---------------+--------------+
                    |
                    v
    +------------------------------+
    | 2) Entity Extraction         |
    | activities/entity_extraction |
    | Model: GLiNER                |
    | Output: ExtractedEntity[]    |
    +---------------+--------------+
                    |
                    v
    +------------------------------+
    | 3) Confidence Router         |
    | activities/confidence_router |
    | Split into high / low        |
    +--------+-------------+-------+
             |             |
             | high        | low
             |             v
             |   +------------------------------+
             |   | 4) Claude Verification       |
             |   | verify_entities_with_claude  |
             |   | Output: ValidatedEntity[]    |
             |   +---------------+--------------+
             |                   |
             +---------+---------+
                       |
                       v
    +------------------------------+
    | 5) Relationship Extraction   |
    | relationship_extraction      |
    | Output: relationships,       |
    | intent, topics               |
    +---------------+--------------+
                    |
                    v
    +------------------------------+
    | 6) Neo4j Writer              |
    | activities/neo4j_writer      |
    | MERGE nodes + relationships  |
    | Output: GraphWriteResult     |
    +------------------------------+


PROJECT LAYOUT
--------------

.
|-- starter.py
|   Starts a batch of workflow executions from `emails.csv`.
|
|-- worker.py
|   Runs the Temporal worker and registers the workflow + activities.
|
|-- workflows/
|   `-- email_processing.py
|       Orchestrates one email through the full pipeline.
|
|-- activities/
|   |-- header_extraction.py
|   |   Parses Message-ID, From, To, CC, BCC, Subject, and Date.
|   |
|   |-- entity_extraction.py
|   |   Extracts candidate entities from the email body using GLiNER.
|   |
|   |-- confidence_router.py
|   |   Splits high-confidence entities from low-confidence ones and can
|   |   call Claude to verify the uncertain results.
|   |
|   |-- relationship_extraction.py
|   |   Uses Claude to infer graph relationships, email intent, and topics.
|   |
|   |-- neo4j_writer.py
|   |   Writes Email, Person, and extracted entity nodes to Neo4j with MERGE.
|   |
|   `-- prompts.py
|       Reserved for prompt text or prompt helpers.
|
|-- models.py
|   Shared Pydantic models used between workflows and activities.
|
|-- graph_normalization.py
|   Normalizes labels and relationship names before Neo4j writes.
|
|-- scripts/
|   `-- normalize_neo4j_labels.py
|       Utility script for graph cleanup / normalization.
|
|-- requirements.txt
|   Python dependencies for Temporal, GLiNER, PydanticAI, and Neo4j.
|
|-- .env.example
|   Safe template for the environment variables required by the project.
|
`-- .env
    Local-only environment variables for external services.


KEY DATA OBJECTS
----------------

- EmailInput
  Raw email text plus source file path.

- EmailHeaders
  Parsed email metadata used by later graph steps.

- ExtractedEntity
  Initial entity candidate from GLiNER with a confidence score.

- ValidatedEntity
  Final entity after confidence routing and optional Claude verification.

- RelationshipExtractionResult
  Relationship list plus detected email intent and topics.

- GraphWriteResult
  Counts of merged nodes and created relationships.


RUNTIME COMPONENTS
------------------

- Temporal
  Orchestrates workflow execution and retries on task queue
  `email-entity-extraction`.

- GLiNER
  Performs local entity extraction from email bodies.

- Claude via PydanticAI
  Verifies low-confidence entities and extracts relationships.

- Neo4j
  Stores the resulting graph with normalized labels and relationship types.


HOW TO RUN
----------

1. Install dependencies:
   `pip install -r requirements.txt`

2. Create a local `.env` from `.env.example` and fill in your real credentials.

3. Place `emails.csv` in the project root.
   The dataset is expected locally and is not committed to GitHub.

4. Make sure Temporal is running on:
   `localhost:7233`

5. Start the worker:
   `python worker.py`

6. In a second terminal, start workflows:
   `python starter.py`


DEFAULT EXECUTION SETTINGS
--------------------------

- Task queue: `email-entity-extraction`
- Workflow entrypoint: `EmailProcessingWorkflow.run`
- Starter batch size: `5` emails per run
- Workflow input model: `EmailProcessingInput`
