# Developer Handoff: Frontend, AI, and Voice

The backend is a local-first FastAPI service. Run from `backend/` with `LLM_PROVIDER=none` and `DEMO_MODE=true`; see [backend setup](../backend/README.md). Swagger at `/docs` and [API.md](API.md) describe the current contracts. Recorded endpoint responses are in [`data/fixtures/`](../data/fixtures/) and can be refreshed by running `python -m scripts.generate_fixtures` from `backend/`.

## Frontend integration

Recommended offline flow:

1. Load examples from `GET /api/demo/golden-path`; submit a selected example's `text` to `POST /api/questions`.
2. Use its `question_id` with `GET /api/evidence/{question_id}` and `GET /api/experts/match/{question_id}`. Show source `verified` state and the expert disclaimer/score note with matches.
3. Create a huddle with `POST /api/huddles`, passing selected expert ID and optionally returned evidence IDs. Status begins `awaiting_expert`.
4. For a demo huddle use `POST /api/huddles/{id}/simulate-response`; then `POST /api/huddles/{id}/synthesize`. Refresh `GET /api/huddles/{id}` for stored state/brief.
5. Show section labels exactly as returned (`EVIDENCE`, `EXPERT OPINION`, `AI SYNTHESIS`), uncertainty, source citations, simulated response/profile labels, and the brief disclaimer.
6. Use `GET /api/analytics/questions` for aggregate chart data. Lists are count-sorted except chronological `timeseries`; none contain question text or IDs.

The `match_score` is a routing relevance score only. It is not an expertise or correctness score. Huddle state changes are validated; surface 409 conflicts as a state refresh/retry decision rather than silently repeating a response.

## AI synthesis integration

`GET /api/huddles/{id}/synthesis-input` returns the sanitized question, exact attached evidence snippets and metadata, expert response(s), safety rules, and expert disclaimer. If the AI teammate builds a brief outside this process, submit it with `PUT /api/huddles/{id}/brief`.

The external brief contract requires the fields and section labels listed in [API.md](API.md). Validation is intentionally strict:

- `question` and the exact required prototype disclaimer must match the huddle.
- Every evidence statement must quote a verbatim substring from attached source `full_text`, identify attached `source_ids`, and include those source IDs inline in square brackets.
- Every evidence source object must match attached source `id`, citation, URL, and verified state exactly.
- Expert perspective must quote stored expert response text, use the assigned synthetic expert name, preserve the response's `is_simulated` state, and use the stored audio URL if present.
- Takeaways must be verbatim attached evidence or expert-response text, or the allowed non-clinical template statement; cited IDs must be attached and carry matching source metadata.
- Uncertainty is required and uses the supported source-limit statements. Never add a diagnosis, prescription, unsupported clinical fact, new citation, or certainty claim.

If LLM mode is enabled, the backend still validates all generated content and falls back to its deterministic template when output is malformed or unsupported. `LLM_PROVIDER=none` avoids external model calls entirely.

## Voice integration

The backend stores voice assets and metadata; it does not perform speech-to-text. Upload supported webm/mp3/wav/m4a audio (maximum 10 MB) to `POST /api/audio`, then include returned `audio_url`, `mode: "voice"`, duration, and any transcript in the huddle response request. Audio is saved under `backend/static/audio/` and served under `/static/audio/`. Local files disappear with an ephemeral deployment unless the directory is on persistent storage. The audio endpoint is a prototype storage interface, not a managed or access-controlled media service.

## Operations and handoff

- Startup creates tables and seeds the expert profiles, committed evidence/chunks, and demo analytics signals if absent.
- `POST /api/demo/reset` clears questions/huddles/responses/live signals only while `DEMO_MODE=true`; it preserves baseline evidence, profiles, and audio.
- Use `GET /api/health` for database readiness and data/provider counts. Errors follow `{"detail":"...","code":"..."}` and do not expose stack traces or rejected request values.
- Use persistent disk and a single SQLite-backed instance if demo records must survive deployment restarts. See Render/Railway notes in [backend README](../backend/README.md).
- Run `pytest -q` from `backend/` before handoff. The end-to-end test is offline and exercises question → evidence → match → huddle → simulated response → brief → analytics.
