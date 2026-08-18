# VetGlobal Backend Technical Project

## Context

VetGlobal processes clinical audio and documents asynchronously. The backend receives user input, creates jobs, workers process those jobs, and the frontend needs to track progress without blocking the user.

This project is a simplified version of that workflow.

You may use LLM tools to help write code. That is allowed. We are interested in your ability to understand requirements, make good technical decisions, review generated code, handle ambiguity, test your work, and explain tradeoffs.

## Goal

Build a small Python API that lets a frontend upload a pet document, creates an asynchronous summary job, simulates a worker completing that job, and exposes a polling endpoint so the frontend can know when the summary is ready.

The goal is not to write a large system. The goal is to build a small, clean, working system and explain your decisions.

## Required Stack

- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- pytest

## Optional Stack

- Docker Compose
- Alembic
- React frontend
- Redis, fake SQS, or an in-memory queue

## Functional Requirements

### 1. Create A Pet

Create an endpoint:

```http
POST /pets
```

Example request:

```json
{
  "name": "Hank",
  "owner_name": "John Bergeson"
}
```

The response should include the created pet id.

### 2. Upload A Document

Create an endpoint:

```http
POST /pets/{pet_id}/documents
```

The endpoint should receive a `.txt` or `.pdf` file.

Expected behavior:

- accept a valid document upload for the pet
- start an asynchronous summarization workflow
- return enough information for the frontend to track progress
- return `202 Accepted`

Example response:

```json
{
  "document_id": 10,
  "job_id": 55,
  "status": "ENQUEUED"
}
```

### 3. Complete A Job

Create an internal endpoint:

```http
POST /internal/jobs/{job_id}/complete
```

This endpoint simulates a worker callback.

Example success payload:

```json
{
  "status": "DONE",
  "summary": "Patient has a history of intermittent vomiting."
}
```

Example failure payload:

```json
{
  "status": "FAILED",
  "error": "Could not parse document"
}
```

Expected behavior:

- mark the job as completed or failed
- make the result available to the public document endpoints
- unblock or notify any pending polling request if your design supports it

### 4. Get A Document

Create an endpoint:

```http
GET /documents/{document_id}
```

It should return the document metadata and summary if available.

### 5. Poll A Document

Create an endpoint:

```http
GET /documents/{document_id}/poll?after_job_id=0
```

This endpoint should long-poll for up to 25 seconds.

It should return one of:

- the document when the summary is ready
- a failed job status if processing failed
- no result if the timeout expires

You may choose between returning `204 No Content` or `200 null` on timeout. Document your decision.

## Non-Functional Requirements

Your submission should include:

- clear README with setup, run, and test commands
- automated tests
- reasonable error handling
- organized code
- basic type hints
- stateless API design; request handling must not depend on in-memory state that would break with multiple API instances
- a short explanation of key technical decisions
- a list of what you intentionally left out of scope

Avoid returning `500` for predictable client or domain errors.

## Ambiguity

Some details are intentionally unspecified. We want to see how you handle ambiguity.

Examples:

- How should the queue be simulated?
- How should files be stored?
- How should duplicate uploads be handled?
- What should happen if the worker completes the same job twice?
- What should the polling endpoint return on timeout?
- How should access control or tenant isolation be modeled?
- How should the system behave if the document does not exist?

You may ask questions, make assumptions, or document your decisions.

## Bonus Points

These are optional. Do not sacrifice the core requirements to implement all of them.

- Alembic migrations
- Docker Compose
- PostgreSQL `LISTEN/NOTIFY` for long polling
- simple React screen for upload and status polling
- idempotency for upload or job completion
- pagination for listing documents
- tests for failure and retry cases
- basic observability around job duration

## Evaluation Criteria

We will evaluate:

```text
Architecture and organization: 20%
Functional correctness: 20%
Handling ambiguity: 15%
Tests: 15%
Communication and README: 10%
Code quality: 10%
Proactivity: 10%
```

## What We Value

Strong signals:

- you ask or document good questions
- you explain tradeoffs
- you keep the solution appropriately small
- you test important behavior
- you use LLM tools responsibly and review the output
- you understand your own code
- you handle failed jobs
- you think about concurrency and polling

Weak signals:

- only the happy path works
- no useful README
- no tests
- unclear error handling
- unnecessary abstractions
- inability to explain decisions
- generated code that was not reviewed

## Deadline

You have until next Monday, 24/08, to complete the project.

After finishing, request a 30-minute meeting so you can present the project, explain your decisions, and discuss tradeoffs.

## Submission

Send:

- repository link
- README
- instructions to run the API
- instructions to run tests
- short notes about design decisions and tradeoffs
- anything that is intentionally incomplete

## Follow-Up Discussion

Be prepared to discuss the main technical areas involved in the project:

- LLM usage and code review
- scalability
- stateless API design
- long polling
- idempotency
- queue semantics
- account or tenant isolation
- error handling
- observability
- testing strategy
- tradeoffs and possible refactors
