# FastAPI Phase 1 Task Breakdown

## Scope

This document defines the implementation task breakdown for `Phase 1` of the Django-to-FastAPI migration.

Phase 1 focus:

- create the new FastAPI backend workspace
- establish core infrastructure
- preserve current DB schema
- preserve current frontend contracts
- migrate the first low-risk modules

Phase 1 does **not** include:

- full `api_automation` migration
- `ui_automation` websocket migration
- `testcases` execution migration
- `knowledge` and `requirements` deep business migration
- orchestrator runtime migration

## Phase 1 Success Definition

Phase 1 is considered complete only when all below are true:

- `FlyTest_FastAPI/` exists and boots in development
- SQLAlchemy can read the current database safely
- Alembic baseline is created
- auth endpoints are contract-compatible
- `prompts`, `api_keys`, `skills`, `testcase_templates`, `projects` are migrated to FastAPI
- frontend can call those modules without contract change
- contract tests exist for all migrated routes
- rollback back to Django routing is verified

## Delivery Milestones

### Milestone M1: Repository Bootstrap

Goal:

- create the FastAPI project skeleton and run a minimal app

Tasks:

1. Create new backend workspace:
   - `FlyTest_FastAPI/`
2. Add dependency management:
   - `pyproject.toml` or `requirements.txt`
3. Create application bootstrap:
   - `app/main.py`
   - `app/config.py`
   - `app/logging.py`
   - `app/lifespan.py`
4. Add base routing:
   - `/health`
   - `/ready`
   - `/api/_meta/version`
5. Add local development startup scripts:
   - Windows startup
   - Linux startup

Deliverables:

- FastAPI app starts locally
- app returns health responses

Acceptance:

- `GET /health` returns `200`
- app starts with environment config and structured logging

### Milestone M2: Database Foundation

Goal:

- connect FastAPI to the current DB without changing schema

Tasks:

1. Create SQLAlchemy foundation:
   - `app/db/base.py`
   - `app/db/session.py`
   - `app/db/metadata.py`
2. Configure engine/session lifecycle
3. Add read-only DB smoke script
4. Initialize Alembic
5. Generate baseline revision without mutating existing tables
6. Verify table-name mappings strategy

Initial table mappings required:

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

Deliverables:

- SQLAlchemy session handling
- Alembic baseline
- first mapped models

Acceptance:

- FastAPI can query mapped tables
- no schema drift introduced
- Alembic revision chain is valid

### Milestone M3: Shared Core Infrastructure

Goal:

- make FastAPI compatible with current auth and API style

Tasks:

1. Create response envelope helpers:
   - success response
   - error response
   - validation error response
2. Create auth dependency layer
3. Create permission evaluation layer compatible with current semantics
4. Create pagination helpers
5. Create exception mapping layer
6. Create request context helpers:
   - current user
   - current project scope
   - permission shortcuts

Deliverables:

- `app/core/auth.py`
- `app/core/permissions.py`
- `app/core/responses.py`
- `app/core/errors.py`
- `app/core/dependencies.py`

Acceptance:

- login-protected endpoint rejects anonymous access the same way as Django
- envelope structure matches current frontend expectation

### Milestone M4: Auth Compatibility

Goal:

- migrate the auth entrypoints first because all modules depend on them

Tasks:

1. Implement `/api/token/`
2. Implement `/api/token/refresh/`
3. Implement current-user profile endpoint parity
4. Implement user/group/permission query compatibility needed by frontend
5. Match JWT payload format used today
6. Add contract tests against current Django responses

Deliverables:

- FastAPI auth router
- JWT generation/refresh logic
- permission lookup compatibility

Acceptance:

- existing frontend login works against FastAPI
- token refresh works
- permission-dependent pages still render correctly

### Milestone M5: First CRUD Module Migration

Goal:

- establish repeatable CRUD migration pattern on low-risk modules

Migration order:

1. `prompts`
2. `api_keys`
3. `skills`
4. `testcase_templates`
5. `projects`

For each module, required tasks are identical:

1. Add SQLAlchemy table mappings
2. Add Pydantic schemas
3. Add repository layer
4. Add service layer
5. Add FastAPI router
6. Add contract tests
7. Add integration tests

Deliverables per module:

- `app/db/models/<module>.py`
- `app/schemas/<module>.py`
- `app/repositories/<module>.py`
- `app/services/<module>/`
- `app/api/v1/<module>.py`
- tests for read/write/permission parity

Acceptance per module:

- list/create/update/delete parity
- permission parity
- frontend page for module works unchanged

### Milestone M6: Routing and Parallel Run

Goal:

- run FastAPI in parallel without cutting all traffic

Tasks:

1. Introduce routing switch mechanism
2. Allow module-level traffic forwarding
3. Support side-by-side envs:
   - Django reference
   - FastAPI candidate
4. Add request replay / contract comparison tooling
5. Add rollback procedure documentation

Deliverables:

- module-level route switch plan
- comparison tool or replay script
- rollback runbook

Acceptance:

- migrated modules can be routed independently
- rollback can be completed quickly without DB rollback

## Work Breakdown Structure

## Epic A: FastAPI Platform Bootstrap

### A1. Create project skeleton

Tasks:

- create `FlyTest_FastAPI/`
- create `app/`
- create `tests/`
- create `alembic/`
- add `README.md`

Acceptance:

- repository structure matches scaffold plan

### A2. Add dependency baseline

Tasks:

- add FastAPI
- add uvicorn
- add SQLAlchemy 2.x
- add Alembic
- add Pydantic v2
- add pytest stack

Acceptance:

- project installs cleanly in virtual env

### A3. Add app bootstrap

Tasks:

- create `create_app()` factory
- wire startup/shutdown hooks
- add health routes
- add logging setup

Acceptance:

- app starts cleanly and returns health data

## Epic B: Database Compatibility Layer

### B1. Session and engine management

Tasks:

- sync engine config
- async engine evaluation decision
- request-scoped session dependency
- transaction helper

Acceptance:

- CRUD request can open and close sessions correctly

### B2. Alembic baseline

Tasks:

- initialize Alembic
- create baseline revision
- document “no schema change” rule

Acceptance:

- Alembic can run without altering existing schema

### B3. First model mappings

Tasks:

- map auth tables
- map projects tables
- map prompts tables
- map api_keys tables
- map skills tables
- map testcase_templates tables

Acceptance:

- read-only queries return same record counts and shapes as Django

## Epic C: Core Compatibility

### C1. Response compatibility

Tasks:

- define standard success envelope
- define standard error envelope
- define validation error conversion

Acceptance:

- frontend parsing logic does not need changes for migrated modules

### C2. Permission compatibility

Tasks:

- implement superuser checks
- implement project creator checks
- implement project membership checks
- implement app-level permission checks

Acceptance:

- permission-protected endpoints behave the same as Django

### C3. Auth compatibility

Tasks:

- password validation/check
- JWT issue and refresh
- current-user permission loading

Acceptance:

- login and refresh contract tests pass

## Epic D: Contract Test Harness

### D1. Baseline capture

Tasks:

- select critical endpoints in scope
- capture representative requests/responses

Acceptance:

- golden contract fixtures exist

### D2. Comparison tooling

Tasks:

- request replay script
- payload normalizer
- field-by-field diff output

Acceptance:

- FastAPI and Django responses can be compared automatically

## Epic E: Module Migration

### E1. Prompts

Tasks:

- map `prompts_userprompt`
- migrate CRUD router
- verify prompt type handling

Acceptance:

- prompt management UI works against FastAPI

### E2. API Keys

Tasks:

- migrate list/create/update/delete
- preserve permission checks

Acceptance:

- API key management UI works unchanged

### E3. Skills

Tasks:

- migrate skill CRUD
- preserve project-scoped behavior if used

Acceptance:

- skill management UI works unchanged

### E4. Testcase Templates

Tasks:

- migrate template CRUD
- preserve import/export semantics

Acceptance:

- template management flows work

### E5. Projects

Tasks:

- migrate project CRUD
- migrate project member operations
- preserve nested routing behavior as required by frontend

Acceptance:

- project list, create, edit, membership flows work

## Phase 1 Task Order

Recommended exact execution order:

1. `A1`
2. `A2`
3. `A3`
4. `B1`
5. `B2`
6. `C1`
7. `C2`
8. `C3`
9. `D1`
10. `D2`
11. `B3`
12. `E1`
13. `E2`
14. `E3`
15. `E4`
16. `E5`
17. `M6` routing and rollback validation

## Definition of Done Per Task

A task is not done if it only has code.

Each task must include:

- implementation
- tests
- docs or runbook update where needed
- verification note

## Phase 1 Exit Gate

Before moving to Phase 2:

- all phase-1 modules pass contract tests
- auth parity is verified
- project scope and permission checks are verified
- frontend smoke tests pass for migrated modules
- rollback to Django routing is proven
- no unresolved P0/P1 regressions remain

## After Phase 1

Once phase 1 is green, the next migration target should be:

- `api_automation`

Reason:

- richest representative complex module
- combines CRUD, reporting, AI jobs, and task-like behavior
- ideal as the first serious end-to-end migration sample

