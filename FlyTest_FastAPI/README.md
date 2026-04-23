# FlyTest FastAPI

This workspace contains the parallel FastAPI backend scaffold for the FlyTest platform migration.

Current status:

- bootstrap application structure is in place
- shared configuration and logging are in place
- DB session scaffolding is in place
- health and metadata endpoints are available
- phase-1 module routers are created as placeholders

This scaffold is intentionally non-destructive:

- it does not replace the current Django backend
- it does not alter the existing database schema
- it is meant to evolve in parallel with the current implementation

## Local Run

1. Create a virtual environment.
2. Install dependencies from `pyproject.toml`.
3. Copy `.env.example` to `.env` and adjust values.
4. Run:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

## Initial Endpoints

- `GET /health`
- `GET /ready`
- `GET /api/_meta/version`

## Migration Audits

- Route coverage audit: `python FlyTest_FastAPI/scripts/route_audit.py`
- Django proxy audit: `python FlyTest_FastAPI/scripts/proxy_audit.py`
