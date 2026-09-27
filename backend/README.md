# PULSEPOINT Backend

FastAPI + SQLite backend for the PULSEPOINT clinical-question huddle prototype. It structures scrubbed questions, retrieves committed evidence, routes to synthetic demo experts, stores responses, builds a source-checked Huddle Brief, and exposes anonymized category trends. This is a prototype decision-support workflow, not a diagnostic tool, medical advice, EMR, or ad platform.

## Requirements

- Python 3.11 or newer
- No API key or network connection is required for local development, tests, or the demo (`LLM_PROVIDER=none`).
- Network access is only needed when deliberately refreshing the PubMed/ClinicalTrials.gov corpus or selecting a hosted LLM provider.

## Local setup

Run commands from `backend/`; the default SQLite database path is relative to the current working directory.

```bash
cd backend
python -m venv .venv
```

Activate the environment, then install and configure:

```bash
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

The checked-in `.env.example` is already configured for a deterministic offline demo. Start the app:

```bash
uvicorn app.main:app --reload --port 8000
```

The app initializes its SQLite tables and seeds the demo experts, committed corpus records, and anonymized demo signals on startup. Visit [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive Swagger UI and [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) for readiness information.

### Seed and corpus commands

The startup hook is the normal path. These commands are useful for preparing or refreshing a local checkout:

```bash
python -m scripts.fetch_corpus
python -m scripts.seed
```

`fetch_corpus` contacts public PubMed E-utilities and ClinicalTrials.gov APIs. If those services are unavailable or return no records, it preserves a valid committed `data/corpus.json` as the deterministic offline fallback. It does not generate realistic-looking fake citations. `scripts.seed` writes the fixed-seed category-only `data/demo_signals.json` and idempotently seeds experts, corpus sources/chunks, and demo signals into SQLite. If a refreshed corpus contains verified live records, seeding removes only obsolete `[SIMULATED]` placeholder source rows and their chunks; unrelated imported evidence is preserved. Restart the API after refreshing to clear process-local retrieval caches. Startup also seeds the refreshed corpus.

## Configuration

Environment variables are loaded from `.env` in the process working directory. Environment variables override that file. Keep keys local; `.env` and SQLite database files are gitignored.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `none` | `none`, `openai`, or `anthropic`; provider failures fall back to rules/templates. |
| `LLM_API_KEY` | empty | Optional provider key. Never commit it. |
| `LLM_MODEL` | empty | Optional model name for the selected provider. |
| `LLM_TIMEOUT_SECONDS` | `8` | Upper bound for provider HTTP calls. |
| `DATABASE_URL` | `sqlite:///./pulsepoint.db` | SQLModel database URL. The relative SQLite path is under `backend/` when commands run there. |
| `CORS_ORIGINS` | empty | Comma-separated additional browser origins; `http://localhost:3000` is always allowed. |
| `USE_EMBEDDINGS` | `false` | Reserved optional retrieval setting; default retrieval remains deterministic BM25. |
| `DEMO_MODE` | `true` | Enables `POST /api/demo/reset`. Set false to disable that destructive demo-only operation. |
| `NCBI_TOOL` | empty | Optional NCBI identification parameter for corpus fetches. |
| `NCBI_EMAIL` | empty | Optional NCBI contact parameter for corpus fetches. |

For a guaranteed offline setup, use `LLM_PROVIDER=none` and `DEMO_MODE=true`. The committed corpus file is read locally at runtime; runtime API requests do not fetch evidence over the network.

## Tests and response fixtures

From `backend/`:

```bash
LLM_PROVIDER=none DEMO_MODE=true pytest -q
python -m scripts.generate_fixtures
```

In PowerShell, set `$env:LLM_PROVIDER = "none"` and `$env:DEMO_MODE = "true"` before invoking `pytest -q`. Tests use isolated in-memory SQLite databases and do not need external services. The fixture generator exercises the API with a temporary database and writes representative JSON responses to `data/fixtures/`.

The full golden-path integration test covers question submission, evidence retrieval, expert matching, huddle creation, simulated response, synthesis, and the resulting analytics signal. Audio upload tests use small synthetic bytes and clean up the file afterward.

## Demo workflow

1. Start the API from `backend/` with `LLM_PROVIDER=none DEMO_MODE=true`.
2. Call `GET /api/demo/golden-path` and submit one returned `text` value to `POST /api/questions`.
3. Call `GET /api/evidence/{question_id}` and `GET /api/experts/match/{question_id}`.
4. Create a huddle with `POST /api/huddles`; evidence IDs can be omitted to use the question's retrieved sources.
5. Use `POST /api/huddles/{id}/simulate-response`, then `POST /api/huddles/{id}/synthesize` for the offline brief.
6. View aggregate counts at `GET /api/analytics/questions`.
7. To restore the demo dataset, call `POST /api/demo/reset`. It removes live questions, huddles, responses, and signals, then restores demo signals and profiles. It does not remove evidence, experts, or uploaded audio.

Demo experts are synthetic profiles and simulated responses are labeled. Corpus entries may be explicitly simulated placeholders; those have `verified: false`, `url: null`, and `[SIMULATED]` titles and are not clinical evidence.

## Deployment notes (Render / Railway)

Use Python 3.11+, install dependencies with `pip install -r requirements.txt`, and set the start command to:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set the service working directory to `backend/` (or otherwise make the `app` package importable and set the working directory to `backend/`). Configure `LLM_PROVIDER=none` for fully offline deterministic behavior. Set `DEMO_MODE=true` only when operators should be able to reset demo data.

SQLite is local to the instance. Attach a persistent disk and point `DATABASE_URL` at its mounted path (for example, `sqlite:////var/data/pulsepoint.db`) if records must survive restarts. Without persistent storage, startup recreates the schema and seeds demo experts, evidence, and signals; live questions and huddles are ephemeral. Do not rely on multiple application instances sharing a local SQLite file.

## Developer handoff

- API paths and payloads: [`../docs/API.md`](../docs/API.md)
- Tables and controlled vocabulary: [`../docs/DATA_MODEL.md`](../docs/DATA_MODEL.md)
- Corpus and retrieval behavior: [`../docs/RAG.md`](../docs/RAG.md)
- Safety and synthetic-data rules: [`../docs/SAFETY.md`](../docs/SAFETY.md)
- Integration notes for frontend, AI, and voice contributors: [`../docs/DEVELOPER_HANDOFF.md`](../docs/DEVELOPER_HANDOFF.md)
