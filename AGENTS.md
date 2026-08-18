# Backend Implementation Specification: VetGlobal Technical Project

## 1. Project Overview & Architectural Principles

This document defines the strict engineering guidelines, domain rules, and implementation phases for building the asynchronous document processing API for VetGlobal.

### Core Principles

- **SOLID:**
  - *Single Responsibility:* Clear boundaries between Routers (HTTP), Services (Business Logic), Repositories (Data Access), and Adapters (Storage/IO).
  - *Open/Closed & Liskov Substitution:* Abstract storage interfaces (`StorageService`) allowing pluggable storage engines (Local, S3, GCS) without modifying domain logic.
  - *Interface Segregation:* Lean, purpose-built interfaces.
  - *Dependency Inversion:* Leverage FastAPI's `Depends()` for sessions, adapters, and domain services.
- **DRY (Don't Repeat Yourself):** Reusable hashing, validation, and exception handling without premature model-schema coupling.
- **YAGNI (You Aren't Gonna Need It):** Avoid heavy external message brokers; simulate workers via internal HTTP endpoints per project spec.
- **Stateless API Design:** No local in-memory state dependency for polling, ensuring safe horizontal scaling across multiple instances.

## 1.1. AI Execution Protocol & Governance Rules

When an AI assistant implements this specification, it MUST strictly adhere to the following execution protocol:

1. **Step-by-Step Execution:** Work on only ONE phase at a time. Do not jump ahead or generate code for subsequent phases concurrently.
2. **Pre-Implementation Explanation:** Before creating or modifying files, clearly explain the action plan and detail every file that will be created or changed.
3. **Mandatory Checkpoint & Stop:** Upon completing the deliverables for a given phase, stop execution immediately.
4. **Approval Requirement:** Explicitly present what was implemented, list what is next, and wait for human user approval before generating code or advancing to the next phase.
5. **Code Review Readiness:** Ensure all code is fully implemented, type-checked, tested, and adheres to all outlined architectural principles and domain rules before requesting review.
6. **External System Integration:** Never attempt to execute or interact with external systems, networks, or services (e.g., storage buckets, databases) unless explicitly authorized by the user.
7. **Local-First Implementation:** All development must be done strictly within the local project scope, without external dependencies or side-effects.
8. **Security:** Do not generate or attempt to execute any malicious, harmful, or insecure code.

---

## 2. Technical Stack

- **Runtime:** Python 3.11+
- **Web Framework:** FastAPI (Async ASGI)
- **ORM & Driver:** SQLAlchemy 2.0+ (asyncio) with `asyncpg`
- **Database:** PostgreSQL 16+
- **Database Migrations:** Alembic (async configuration)
- **Validation & Settings:** Pydantic v2 & `pydantic-settings`
- **Testing:** `pytest`, `pytest-asyncio`, `httpx` (AsyncClient)
- **Containerization:** Docker & Docker Compose with health checks

---

## 3. Domain Rules & Technical Decisions

### 3.1. Entity Relationships & Constraints

- **Pet (1) -> Document (N):** A pet can have multiple clinical documents.
- **Document (1) -> Job (N):** A document can have multiple processing jobs (allowing future re-runs); queries default to the latest job.
- **Database-Level Constraint:** `UniqueConstraint('pet_id', 'file_hash', name='uq_pet_document_hash')` to prevent concurrent duplicate uploads.

### 3.2. File Upload & Validation

- **Allowed Formats:** `.txt` and `.pdf` only.
- **Size Limit:** Maximum 10 MB.
- **Duplicate Prevention:** Calculate SHA-256 hash. If `file_hash` already exists for the same `pet_id`, return `409 Conflict`.
- **Storage Strategy:** Disk storage at `./storage/uploads/{pet_id}/{filename}` via abstract `StorageService` adapter.

### 3.3. Job Lifecycle & Idempotency

- **Initial State:** `ENQUEUED` upon upload.
- **Terminal States:** `DONE` (with `summary`) or `FAILED` (with `error_message`).
- **Idempotency Rule (`POST /internal/jobs/{job_id}/complete`):**
  - If a job is already `DONE` or `FAILED`, return `200 OK` with `{"status": "ALREADY_COMPLETED", "message": "Job has already been processed"}` to prevent worker retry loops.
- **Observability:**
  - Track `created_at`, `started_at`, and `completed_at`.
  - Calculate duration upon completion and emit a structured log (`job_id`, `status`, `duration_seconds`).

### 3.4. Long Polling Semantics (`GET /documents/{document_id}/poll?after_job_id=0`)

- **Timeout:** 25 seconds.
- **Polling Loop:** Non-blocking async loop (`await asyncio.sleep(1.0)`) querying PostgreSQL state.
- **Responses:**
  - `200 OK`: Job finished (`DONE` or `FAILED`).
  - `204 No Content`: 25s timeout reached without completion.
  - `404 Not Found`: Document not found.

### 3.5. Error Handling

- Map all predictable domain errors to explicit HTTP status codes (`400`, `404`, `409`).
- Global exception handler catches unhandled exceptions, logs the trace, and returns a safe sanitized `500` JSON payload.

---

## 4. Project Structure

```text
vetglobal-backend/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── models/
│   │   ├── pet.py
│   │   ├── document.py
│   │   └── job.py
│   ├── schemas/
│   │   ├── pet.py
│   │   ├── document.py
│   │   ├── job.py
│   │   └── health.py
│   ├── adapters/
│   │   ├── storage_base.py
│   │   └── local_storage.py
│   ├── repositories/
│   │   ├── pet_repository.py
│   │   ├── document_repository.py
│   │   └── job_repository.py
│   ├── services/
│   │   ├── pet_service.py
│   │   ├── document_service.py
│   │   └── job_service.py
│   ├── routers/
│   │   ├── health.py
│   │   ├── pets.py
│   │   ├── documents.py
│   │   └── internal_jobs.py
│   └── main.py
├── migrations/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_pets.py
│   ├── test_documents.py
│   ├── test_jobs.py
│   └── test_polling.py
├── storage/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
└── README.md
```

---

## 5. Implementation Roadmap

### Phase 1: Environment & Infrastructure Setup

1. Create `requirements.txt` with all dependencies (`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `python-multipart`, `pytest`, `pytest-asyncio`, `httpx`).
2. Set up `Dockerfile` and `docker-compose.yml` (`db` on PostgreSQL 16, `api` with healthcheck on `GET /health`).
3. Configure `app/core/config.py` using `pydantic-settings`.
4. Configure async engine and session factory in `app/core/database.py`.
5. Implement `GET /health` router executing `SELECT 1`.

### Phase 2: Domain Modeling & Migrations

1. Implement SQLAlchemy models:
   - `Pet`: `id`, `name`, `owner_name`, `created_at`.
   - `Document`: `id`, `pet_id` (FK), `filename`, `file_path`, `file_hash`, `created_at`, `UniqueConstraint('pet_id', 'file_hash')`.
   - `Job`: `id`, `document_id` (FK), `status`, `summary`, `error_message`, `created_at`, `started_at`, `completed_at`, `updated_at`.
2. Initialize Alembic, configure async `migrations/env.py`, and generate the initial migration.

### Phase 3: Storage Adapters & Repositories

1. Define `StorageService` interface in `app/adapters/storage_base.py`.
2. Implement `LocalStorageService` with async file operations in `app/adapters/local_storage.py`.
3. Implement `PetRepository`, `DocumentRepository`, and `JobRepository` with session management and `IntegrityError` mapping.

### Phase 4: Services & Endpoints Implementation

1. **`POST /pets`**: Validate input and return `201 Created` with the generated pet ID.
2. **`POST /pets/{pet_id}/documents`**: Validate file (type/size), calculate SHA-256, save via adapter, create `Document` and `Job` (`ENQUEUED`), and return `202 Accepted`.
3. **`POST /internal/jobs/{job_id}/complete`**: Validate job; if already terminal, return `200 OK` (idempotent); otherwise, update to `DONE`/`FAILED`, calculate duration, and emit structured logs.
4. **`GET /documents/{document_id}`**: Return metadata and latest summary.
5. **`GET /documents/{document_id}/poll?after_job_id=0`**: Run async long polling loop (1.0s interval up to 25s); return `200 OK` on completion or `204 No Content` on timeout.

### Phase 5: Exception Handling & App Wiring

1. Implement custom exceptions in `app/core/exceptions.py`.
2. Register exception handlers in `app/main.py` mapping domain errors to `400`, `404`, `409`.
3. Register global catch-all exception handler with structured logging.

### Phase 6: Automated Testing Suite (`pytest`)

1. Configure `tests/conftest.py` with test database fixtures and `httpx.AsyncClient`.
2. Implement test suite:
   - Happy path: Pet -> Upload -> Complete -> Retrieve.
   - Concurrent Long Polling using `asyncio.gather`.
   - Worker failure (`status: FAILED`).
   - Polling timeout (25s -> `204 No Content`).
   - Worker callback idempotency (`200 OK` on duplicate).
   - Duplicate file upload conflict (`409 Conflict`).
   - File validation errors (invalid type, >10 MB).
   - Health check endpoint (`GET /health`).

### Phase 7: Documentation

1. Create `README.md` containing:
   - Setup instructions (Docker Compose & Local).
   - Test running instructions (`pytest -v`).
   - Architectural decisions, trade-offs (Async DB Polling vs LISTEN/NOTIFY, 204 vs 200 on timeout), and intentional out-of-scope items.
