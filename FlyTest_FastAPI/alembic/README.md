# Alembic

This directory is reserved for the FastAPI migration baseline and future SQLAlchemy-managed revisions.

Early migration rule:

- do not mutate existing Django-managed tables during bootstrap
- use Alembic for baseline and future FastAPI-owned schema changes only

