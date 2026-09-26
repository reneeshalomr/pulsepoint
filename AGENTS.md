# AGENTS.md — PULSEPOINT (HackGT 13)

PULSEPOINT is an HCP clinical-question huddle platform: question → structure → evidence → expert match → expert response → Clinical Huddle Brief → anonymized Question Graph signal. It is a hackathon prototype, NOT a diagnostic tool, chatbot, EMR, or ad platform.

## Scope for backend tasks
- The full backend spec is `docs/BACKEND_SPEC.md`. Always read it first.
- Only touch `backend/`, `data/`, and `docs/`. NEVER modify `frontend/` or `ai/` (other teammates own them).
- Implement ONLY the phase named in the task. Do not start later phases.

## Non-negotiable rules
1. Never invent citations, titles, authors, dates, URLs, PMIDs, or NCT IDs. Evidence comes only from `data/corpus.json` (real PubMed / ClinicalTrials.gov records). Simulated placeholders must be `verified: false`, `url: null`, title prefixed `[SIMULATED]`.
2. Evidence snippets are verbatim source text; an LLM never writes or edits them.
3. All experts are fictional demo profiles (`is_demo: true`) and responses say so.
4. Simulated expert responses carry `is_simulated: true`.
5. Scrub PHI before storing question text. Analytics signals store categories only, never free text.
6. No secrets in code. Use `.env` (gitignored) and keep `.env.example` current.
7. Everything must work offline with `LLM_PROVIDER=none` and no network. Every external call has a deterministic fallback and a timeout.
8. Keep it simple: reliability and demo stability over features. No auth, no microservices, no heavy ML.

## Commands
- Install: `cd backend && pip install -r requirements.txt`
- Run: `cd backend && uvicorn app.main:app --reload --port 8000`
- Test: `cd backend && pytest -q`  (must pass before finishing any task)

## PR description format
Start every PR description with:
DONE: / API: / INPUT: / OUTPUT: / DEPENDENCIES: / NEXT:
