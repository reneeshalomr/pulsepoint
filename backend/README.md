# PULSEPOINT Backend

Phase 1 provides the FastAPI scaffold, SQLite/SQLModel schema, controlled vocabulary, and health endpoint.

From this directory, install dependencies with `pip install -r requirements.txt`, then run `uvicorn app.main:app --reload --port 8000`. Run the scaffold tests with `pytest -q`.

Configuration is read from environment variables or `.env`; see `.env.example`. The default provider is `none`, and the database defaults to `./pulsepoint.db`.
