# FastAPI Full Migration Plan

## Goal

This document defines the full-backend migration plan from Django/DRF to FastAPI for the FlyTest platform.

The objective is:

- preserve the current database and API contract during the transition
- migrate all backend capabilities to FastAPI in stages
- avoid big-bang cutover
- only cut traffic after strict acceptance gates pass

Important constraint:

- zero-bug guarantees are not realistic for a migration of this size
- the practical target is `0 known high-severity regressions at cutover`

## Current Baseline

The current backend is a platform-style Django system, not a lightweight API service.

Measured backend footprint:

- about `68` Django models across the project
- about `46` ViewSets
- about `92` DRF `@action` custom endpoints

Module-level complexity snapshot:

| Module | Models | ViewSets | Celery Tasks | WebSocket Consumers |
|---|---:|---:|---:|---:|
| `accounts` | 0 | 4 | 0 | 0 |
| `projects` | 3 | 1 | 0 | 0 |
| `testcases` | 7 | 4 | 2 | 0 |
| `api_keys` | 1 | 1 | 0 | 0 |
| `knowledge` | 5 | 4 | 0 | 0 |
| `prompts` | 1 | 1 | 0 | 0 |
| `requirements` | 6 | 5 | 1 | 0 |
| `orchestrator_integration` | 4 | 1 | 0 | 0 |
| `skills` | 1 | 1 | 0 | 0 |
| `testcase_templates` | 1 | 1 | 0 | 0 |
| `ui_automation` | 11 | 12 | 0 | 2 |
| `api_automation` | 22 | 7 | 0 | 0 |
| `langgraph_integration` | 4 | 2 | 0 | 0 |
| `mcp_tools` | 2 | 1 | 0 | 0 |

Strong Django coupling currently exists in:

- auth and permissions
- admin
- Django ORM and migrations
- DRF routers and nested routers
- serializers
- Channels/WebSocket
- Celery integration

## Target Architecture

Backend target stack:

- framework: `FastAPI`
- ORM: `SQLAlchemy 2.x`
- schema validation: `Pydantic v2`
- migrations: `Alembic`
- auth: JWT-compatible custom auth layer
- async tasks: keep `Celery + Redis` in early phases
- websocket/streaming: `FastAPI WebSocket`
- docs: FastAPI OpenAPI

Principle:

- keep the current PostgreSQL schema first
- map existing Django tables from FastAPI
- do not redesign the database during framework migration

## Non-Negotiable Migration Rules

1. No big-bang rewrite.
2. Django remains the reference implementation until final cutover.
3. API contract is frozen before migration starts.
4. FastAPI must match current request/response behavior before traffic moves.
5. Cutover is module-based, not repo-wide.
6. Rollback must stay available until the final stabilization window closes.

## Migration Strategy

### Phase 0: Freeze and Inventory

Deliverables:

- frozen API contract list
- module dependency map
- endpoint priority list
- regression checklist

Work:

- export all current routes
- mark user-facing critical flows
- identify admin-only flows
- define cutover metrics

Exit gate:

- all critical APIs and pages are categorized by business priority

### Phase 1: FastAPI Skeleton

Create a parallel backend workspace:

- `FlyTest_FastAPI/`

Suggested structure:

- `app/core`
- `app/db`
- `app/models`
- `app/schemas`
- `app/repositories`
- `app/services`
- `app/api`
- `app/ws`
- `app/tasks`
- `alembic/`

Deliverables:

- FastAPI app bootable
- health endpoint
- SQLAlchemy connection
- Alembic baseline
- shared config loader

Exit gate:

- FastAPI boots in dev/staging and can connect to the current DB safely

### Phase 2: Shared Data Layer

Goal:

- map existing Django tables in SQLAlchemy without changing schema

Work:

- build SQLAlchemy models for existing tables
- keep naming aligned with current table names
- verify relationships for:
  - auth
  - projects
  - api_automation
  - testcases
  - knowledge

Exit gate:

- read-only parity queries match Django results for core entities

### Phase 3: Shared Domain Services

Goal:

- move business logic out of framework-specific layers

Approach:

- introduce service layer equivalents for current complex modules
- keep Django calling the new service layer where practical
- then let FastAPI call the same service layer

Priority service domains:

- auth/session
- project scope and permission checks
- api automation execution/generation/reporting
- testcase execution
- knowledge retrieval

Exit gate:

- core business logic is callable without DRF ViewSet coupling

### Phase 4: Low-Risk Modules First

Recommended order:

1. `prompts`
2. `api_keys`
3. `skills`
4. `testcase_templates`
5. `projects`
6. `accounts`

Reason:

- mostly CRUD or bounded logic
- good for establishing coding patterns and repository/service standards

Exit gate:

- FastAPI version passes contract tests
- front-end can switch to FastAPI for these modules with no UI regression

### Phase 5: Medium-Risk Business Modules

Recommended order:

1. `api_automation`
2. `knowledge`
3. `requirements`

Reason:

- already have stronger local test coverage
- complex enough to validate migration pattern
- not as operationally risky as UI automation or orchestrator runtime

Special note for `api_automation`:

- preserve current request/test-case/environment/report contracts
- preserve async job semantics
- preserve AI generation/report summary behavior

Exit gate:

- module-level UI smoke tests pass against FastAPI
- DB write results match Django behavior

### Phase 6: High-Risk Runtime Modules

Migrate last:

1. `testcases`
2. `ui_automation`
3. `langgraph_integration`
4. `mcp_tools`
5. `orchestrator_integration`

Reason:

- async jobs
- streaming or websocket behavior
- long-running execution
- higher external dependency count

Special note:

- `ui_automation` websocket consumers must be redesigned for FastAPI WebSocket
- Celery integration should be preserved initially, not redesigned at the same time

Exit gate:

- long-running tasks, streaming APIs, and websocket flows pass staged end-to-end validation

### Phase 7: Parallel Run and Shadow Validation

Before full cutover:

- keep Django live
- run FastAPI in parallel
- mirror selected traffic or replay recorded requests

Required comparisons:

- response body equivalence
- status code equivalence
- permission behavior equivalence
- DB write equivalence

Exit gate:

- no unresolved P0/P1 regressions
- measured parity on critical endpoints

### Phase 8: Cutover and Decommission

Steps:

1. switch gateway routing module by module
2. keep Django in rollback-ready state
3. observe production metrics
4. freeze Django writes once confidence is high
5. remove Django runtime only after stabilization period

## API Contract Policy

The existing frontend should not be forced into a broad rewrite during backend migration.

Therefore FastAPI must preserve:

- existing URL paths
- request params/query params
- response envelopes
- status codes
- error payload shape
- auth headers and token behavior

Contract testing is mandatory for all migrated modules.

## Auth and Permission Migration

Do not redesign RBAC during framework migration.

Recommended approach:

- keep existing auth tables
- preserve current JWT payload format
- implement FastAPI permission checks compatible with current permission semantics
- preserve project-scoped access checks

Auth migration milestones:

1. login/token refresh parity
2. current-user parity
3. permission parity
4. project membership parity

## Admin Replacement Strategy

Django admin is not automatically portable.

Plan:

- short term: keep Django admin for internal fallback during migration
- medium term: replace essential admin flows with productized management pages or SQLAdmin
- long term: remove reliance on Django admin for production operations

Before decommissioning Django, inventory all actually used admin workflows.

## Celery and Async Jobs

Do not migrate task framework and web framework at the same time unless necessary.

Keep initially:

- `Celery`
- `Redis`
- existing task boundaries

Migrate only:

- task submission entrypoints
- status polling APIs
- callback or notification integration

## WebSocket and Realtime

Channels-based behavior must be explicitly redesigned.

FastAPI target:

- native WebSocket routes
- Redis-backed event distribution if cross-process coordination is needed

Do not use in-memory state for production realtime migration.

## Testing and Quality Gates

The project should not cut traffic without all gates below passing.

### Gate A: Contract Tests

- endpoint path parity
- request schema parity
- response schema parity
- status code parity

### Gate B: Permission Tests

- role-based access
- project member access
- forbidden cases

### Gate C: Data Consistency Tests

- same write request produces same DB result in Django and FastAPI

### Gate D: UI End-to-End Tests

Minimum required areas:

- login
- project switching
- API automation
- UI automation
- knowledge management
- prompts management
- requirements management
- orchestrator/chat flows

### Gate E: Performance and Stability Tests

- login
- list/detail CRUD endpoints
- reporting endpoints
- async job endpoints
- websocket/streaming endpoints

### Gate F: Rollback Test

- routing rollback works
- no irreversible schema dependency introduced

## Cutover Readiness Checklist

All must be true:

- no unresolved P0 issues
- no unresolved permission regressions
- no contract mismatches on critical APIs
- no blocking UI regressions
- rollback path tested
- ops runbook updated

## Recommended Delivery Order

The recommended macro-order is:

1. Freeze contract
2. Build FastAPI skeleton
3. Add SQLAlchemy mappings
4. Extract service layer
5. Migrate low-risk modules
6. Migrate `api_automation` as first complex sample
7. Migrate remaining business modules
8. Migrate websocket/runtime modules
9. Shadow run
10. Cut over
11. Retire Django

## Risk Register

### Highest Risks

- auth/permission parity failure
- hidden Django admin dependence
- schema drift during migration
- websocket runtime mismatch
- long-running task behavior divergence
- front-end contract regression

### Mitigations

- preserve DB schema first
- preserve JWT shape
- module-level cutover only
- contract tests before cutover
- keep Django rollback path alive

## Recommendation

If the organization insists on full migration, execute it as a controlled multi-phase platform rewrite.

Do not:

- rewrite all modules at once
- redesign database and framework in the same phase
- cut traffic before contract parity and rollback are proven

The first implementation milestone should be:

- create `FlyTest_FastAPI`
- map auth/projects/prompts/api_keys
- build migration toolchain
- migrate `api_automation` as the first full-complexity sample module

