# FastAPI Project Scaffold Plan

## Purpose

This document turns the full migration strategy into an implementation-ready scaffold plan.

It answers:

- what `FlyTest_FastAPI/` should look like
- how code should be layered
- what should be migrated first
- what must be shared versus rewritten
- what “phase 1 done” actually means

## Guiding Principles

1. Keep the current database schema first.
2. Do not redesign business rules while replacing the framework.
3. Keep frontend contracts stable.
4. Build a parallel FastAPI backend before replacing Django runtime.
5. Extract and share domain logic as early as possible.

## Target Repository Layout

Recommended new backend workspace:

```text
FlyTest_FastAPI/
  alembic/
    versions/
    env.py
    script.py.mako
  app/
    main.py
    config.py
    logging.py
    lifespan.py
    core/
      auth.py
      permissions.py
      security.py
      errors.py
      pagination.py
      responses.py
      dependencies.py
      context.py
    db/
      base.py
      session.py
      metadata.py
      models/
        auth.py
        projects.py
        prompts.py
        api_keys.py
        api_automation.py
        testcases.py
        knowledge.py
        requirements.py
        ui_automation.py
        orchestrator.py
        langgraph.py
        mcp_tools.py
    schemas/
      common.py
      auth.py
      projects.py
      prompts.py
      api_keys.py
      api_automation.py
      testcases.py
      knowledge.py
      requirements.py
      ui_automation.py
      orchestrator.py
      langgraph.py
      mcp_tools.py
    repositories/
      base.py
      auth.py
      projects.py
      prompts.py
      api_keys.py
      api_automation.py
      testcases.py
      knowledge.py
      requirements.py
      ui_automation.py
      orchestrator.py
      langgraph.py
      mcp_tools.py
    services/
      auth/
      projects/
      prompts/
      api_keys/
      api_automation/
      testcases/
      knowledge/
      requirements/
      ui_automation/
      orchestrator/
      langgraph/
      mcp_tools/
    api/
      router.py
      v1/
        auth.py
        projects.py
        prompts.py
        api_keys.py
        api_automation.py
        testcases.py
        knowledge.py
        requirements.py
        ui_automation.py
        orchestrator.py
        langgraph.py
        mcp_tools.py
    ws/
      router.py
      ui_automation.py
      langgraph.py
    tasks/
      celery_app.py
      requirements.py
      testcases.py
      shared.py
    adapters/
      llm/
      vectorstore/
      storage/
      http/
      mcp/
    compatibility/
      django_contracts/
        auth.py
        projects.py
        prompts.py
        api_automation.py
        testcases.py
    tests/
      contract/
      integration/
      repositories/
      services/
      api/
      ws/
  requirements.txt
  pyproject.toml
  README.md
```

## Layer Responsibilities

### `app/core`

Framework-neutral runtime concerns:

- auth dependencies
- permission evaluation helpers
- shared response envelope helpers
- pagination and error handling
- request-scoped context

Nothing in `core` should know module-specific business rules.

### `app/db`

Infrastructure-only data access foundation:

- SQLAlchemy engine/session
- base metadata
- model mappings to existing Django tables

Important rule:

- table names must match existing Django tables exactly in early phases

### `app/schemas`

Pydantic input/output models only.

Use cases:

- request validation
- response serialization
- internal DTO boundaries between API and service layers

Do not put database or permission logic here.

### `app/repositories`

Query/write layer only.

Responsibilities:

- SQLAlchemy query composition
- filtering
- persistence
- transaction-aware DB operations

Repositories should not contain cross-module business decisions.

### `app/services`

This is the migration center of gravity.

Responsibilities:

- business rules
- orchestration
- cross-repository workflows
- adapter coordination

Long term goal:

- Django legacy views and FastAPI routers should both be able to call the same service logic

### `app/api`

FastAPI route definitions only.

Responsibilities:

- request parsing
- dependency injection
- permission guards
- response wrapping

Routers should stay thin.

### `app/ws`

Realtime routes only.

Responsibilities:

- websocket connection lifecycle
- message streaming
- event subscription

Keep business logic delegated to `services` or `adapters`.

### `app/tasks`

Async job entrypoints only.

Responsibilities:

- Celery task registration
- background execution wrappers

Task modules should call `services`, not contain duplicated business logic.

### `app/adapters`

External integration boundary:

- LLM providers
- Qdrant/vector search
- file storage
- HTTP clients
- MCP integration

This keeps provider changes isolated from domain logic.

## Shared Foundations Required Before Module Migration

These are phase-1 mandatory foundations.

### 1. Response Envelope Compatibility

Current frontend expects stable response shapes.

Need a shared helper to return envelopes compatible with the current Django APIs, for example:

```json
{
  "status": "success",
  "code": 200,
  "message": "操作成功",
  "data": {}
}
```

Exact shape should be captured from the current Django baseline before rollout.

### 2. Auth Compatibility

Must preserve:

- login endpoint behavior
- refresh endpoint behavior
- token payload compatibility
- current-user permission checks

FastAPI auth milestone:

- same login request from frontend succeeds without UI changes

### 3. Database Session Policy

Need:

- request-scoped SQLAlchemy sessions
- transaction boundaries for write APIs
- explicit transaction handling in services

Do not rely on implicit autocommit-style behavior.

### 4. Permission Compatibility

Need an internal permission layer that maps existing semantics:

- superuser access
- project creator access
- project member access
- per-module permission checks

This should live in:

- `app/core/permissions.py`

### 5. Contract Test Harness

Before major routing begins, build a comparison harness:

- send same request to Django and FastAPI
- compare status code
- compare normalized JSON payload
- compare permission behavior

Without this harness, migration risk stays too high.

## Phase 1 Modules

Recommended first migration wave:

1. `prompts`
2. `api_keys`
3. `skills`
4. `testcase_templates`
5. `projects`
6. `accounts`

Why these first:

- lower write complexity
- smaller dependency surface
- enough variety to validate patterns
- unlock shared auth and project scope for later modules

## Phase 1 Database Mapping Scope

Create SQLAlchemy mappings first for:

- `auth_user`
- `auth_group`
- `auth_permission`
- `django_content_type`
- `projects_project`
- `projects_projectmember`
- `prompts_userprompt`
- `api_keys_*`
- `skills_*`
- `testcase_templates_*`

Only after these are stable should module routers go live.

## Phase 1 Router Scope

FastAPI routers to build first:

- `/api/token/`
- `/api/token/refresh/`
- `/api/accounts/...`
- `/api/projects/...`
- `/api/prompts/...`
- `/api/api-keys/...`
- `/api/skills/...`
- `/api/testcase-templates/...`

Initial objective:

- read and write parity for core CRUD
- auth parity
- project-scoped permissions

## API Automation as First Complex Sample

After phase 1, use `api_automation` as the first full-complexity migration sample.

Why:

- rich CRUD
- custom actions
- background jobs
- AI integrations
- reporting
- enough tests already exist to support parity work

For `api_automation`, migrate in this order:

1. collections / environments / requests CRUD
2. execution records list/detail/report
3. request execution
4. test case generation jobs
5. import jobs
6. AI report summary

This sequence moves from stable CRUD to higher-risk orchestration.

## Service Extraction Blueprint

For every migrated module, use this pattern:

### Step A

Identify logic currently trapped in:

- DRF serializers
- ViewSets
- helper functions near views

### Step B

Extract to:

- `app/services/<module>/...`

### Step C

Keep repository calls inside:

- `app/repositories/<module>.py`

### Step D

Make the FastAPI router call service layer only.

### Step E

Where useful, make Django legacy code call the same service layer temporarily.

This reduces divergence during parallel run.

## Alembic Strategy

Early migration rule:

- Alembic should not mutate existing tables during bootstrap

Use:

- baseline revision representing current DB
- only create new revisions for FastAPI-owned new tables, if any

Do not:

- recreate Django-managed tables
- rename tables in phase 1
- reshape auth schema in phase 1

## Realtime Strategy

Do not migrate websocket-heavy modules in phase 1.

Target design for later phases:

- FastAPI websocket router
- Redis-backed event bus if multiple workers must share events
- explicit connection manager

Modules delayed for later:

- `ui_automation`
- `langgraph_integration`
- `orchestrator_integration`

## Background Task Strategy

Keep Celery in the short term.

FastAPI should:

- submit Celery tasks
- read task state
- expose task status endpoints

Avoid redesigning the task system while migrating framework layers.

## Phase 1 Deliverables

Phase 1 is complete only when all are true:

- `FlyTest_FastAPI/` bootstrapped
- SQLAlchemy session management works
- Alembic baseline created
- auth parity available
- `projects`, `prompts`, `api_keys`, `skills`, `testcase_templates` FastAPI routes work
- frontend can call those routes without contract breakage
- contract tests exist for migrated endpoints

## Phase 1 Acceptance Checklist

- login from existing frontend succeeds against FastAPI
- token refresh works
- project list/detail/create/update/delete parity verified
- prompt CRUD parity verified
- API key CRUD parity verified
- skill CRUD parity verified
- template CRUD parity verified
- no unresolved P0 permission regression
- rollback route switch tested

## Coding Standards For Migration

1. No business logic in routers.
2. No direct DB access in routers.
3. No provider-specific code in services.
4. All write flows must be transaction-aware.
5. Every migrated endpoint must have contract tests.
6. Every module router must stay under a dedicated file.

## Immediate Next Step

After this scaffold document, the first implementation tasks should be:

1. create `FlyTest_FastAPI/`
2. add FastAPI bootstrap app
3. add SQLAlchemy engine/session/base metadata
4. add auth and response core helpers
5. map first DB tables
6. build first contract tests
7. migrate `prompts` as the first end-to-end sample module

