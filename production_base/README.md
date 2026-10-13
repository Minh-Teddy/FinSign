# Production Base — FastAPI

A practical starting structure for a production-oriented Python API.

## Requirements
- Python 3.12+
- PostgreSQL
- Docker (optional)

## Local setup
1. Create and activate a virtual environment.
2. Install dependencies: `pip install -e ".[dev]"`
3. Copy `.env.example` to `.env` and update settings.
4. Run the API: `uvicorn app.main:app --reload --app-dir src`
5. Open `/docs` for the interactive API docs.

## Tests
`pytest`

## Notes
- Never commit `.env` or real secrets.
- Add database migrations with Alembic before evolving production schemas.
- Configure production secrets through your deployment platform.
- This is a scaffold, not a fully hardened production deployment.
