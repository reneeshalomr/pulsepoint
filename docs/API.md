# PULSEPOINT Backend API

Base URL for local development: `http://127.0.0.1:8000`. Interactive Swagger documentation is served at [`/docs`](http://127.0.0.1:8000/docs); OpenAPI JSON is at `/openapi.json` and ReDoc at `/redoc`.

Errors use the form `{"detail":"...","code":"..."}`. Request validation returns HTTP 422 with a generic message so rejected request values (which may contain PHI) are not echoed. Missing resources return HTTP 404; invalid state transitions return HTTP 409. The API does not expose stack traces.

## Health

### `GET /api/health`

Checks SQLite and reports the configured provider and local data counts.

**Response 200**

```json
{"status":"ok","db":"ok","llm_provider":"none","corpus_size":5,"experts_count":12}
```

`corpus_size` is read from `data/corpus.json`; `experts_count` reflects the database. A database failure is returned as a generic 500 error.

```bash
curl http://127.0.0.1:8000/api/health
```

## Questions

### `POST /api/questions`

Scrubs PHI, uses the demo cache when a supplied example matches, otherwise attempts configured extraction and falls back to taxonomy keyword rules. Creates an anonymized category-only analytics signal at the same time.

**Request**

```json
{"text":"For a patient with type 2 diabetes, what has changed recently in evidence for GLP-1 treatment?"}
```

Text must contain 1–2000 non-whitespace characters. **Response 201** returns `question_id`, `specialty`, `condition`, `topic`, `intent`, normalized `question`, `key_context`, `extraction_method`, `confidence`, and `phi_detected`.

```bash
curl -X POST http://127.0.0.1:8000/api/questions \
  -H 'Content-Type: application/json' \
  -d '{"text":"For a patient with type 2 diabetes, what has changed recently in evidence for GLP-1 treatment?"}'
```

### `GET /api/questions/{question_id}`

Returns the same question structure as creation. **404** if missing.

```bash
curl http://127.0.0.1:8000/api/questions/QUESTION_ID
```

## Evidence

### `GET /api/evidence/{question_id}`

Returns deterministic top-five evidence results for a question, including the retrieval method. Each result has `id`, `title`, `type`, `date`, verbatim `snippet`, `url`, `citation`, `relevance`, and `verified`, plus source metadata. **404** if the question is missing.

```bash
curl http://127.0.0.1:8000/api/evidence/QUESTION_ID
```

### `GET /api/evidence/search`

Searches the local corpus and persisted evidence records. Query parameters: `q` (or alias `query`), optional `condition`, `topic`, `specialty`, and `limit` (1–12, default 5). Response includes the effective `query`, `retrieval_method`, `count`, `limit`, and `sources`.

```bash
curl 'http://127.0.0.1:8000/api/evidence/search?q=breast%20cancer&condition=Breast%20cancer&limit=5'
```

### `POST /api/evidence`

Imports a record by identity from the committed `data/corpus.json`; arbitrary source metadata cannot be supplied. **Request:** `{"external_id":"PMID:..."}` or a corpus-provided ClinicalTrials.gov identifier. **Response 201** contains the persisted source fields and full text. **404** if the ID is not in the corpus.

```bash
curl -X POST http://127.0.0.1:8000/api/evidence \
  -H 'Content-Type: application/json' -d '{"external_id":"CORPUS_EXTERNAL_ID"}'
```

## Experts

Every expert response includes the disclaimer `Demo profile — fictional expert for prototype purposes.` All seeded profiles are synthetic.

### `GET /api/experts`

Lists seeded profiles. Optional `specialty` filter. Response: `{"experts":[...],"disclaimer":"..."}`. Each expert includes `id`, `name`, `title`, `specialty`, `conditions`, `topics`, `expertise`, `availability`, `bio`, and `is_demo`.

```bash
curl 'http://127.0.0.1:8000/api/experts?specialty=Oncology'
```

### `GET /api/experts/{expert_id}`

Returns `{"expert":{...},"disclaimer":"..."}`. **404** if not found.

```bash
curl http://127.0.0.1:8000/api/experts/demo-onc-001
```

### `GET /api/experts/match/{question_id}`

Returns the top three experts with a 0–100 `match_score`, `score_breakdown`, availability, and `is_demo`, along with `disclaimer` and the routing-only `score_note`. Scores represent routing relevance, not clinical expertise or correctness. **404** if the question is missing.

```bash
curl http://127.0.0.1:8000/api/experts/match/QUESTION_ID
```

## Huddles and briefs

### `POST /api/huddles`

Creates an `awaiting_expert` huddle. Evidence IDs may be omitted or empty to retrieve and attach the question's default results.

**Request:** `{"question_id":"...","expert_id":"demo-onc-001","evidence_ids":[]}`

**Response 201** contains `huddle`, embedded `question`, attached `evidence`, synthetic `expert`, empty `responses`, `brief: null`, and expert `disclaimer`. **404** if the question, expert, or an explicit evidence ID does not exist; **422** for invalid payloads.

```bash
curl -X POST http://127.0.0.1:8000/api/huddles \
  -H 'Content-Type: application/json' \
  -d '{"question_id":"QUESTION_ID","expert_id":"demo-onc-001","evidence_ids":[]}'
```

### `GET /api/huddles`

Lists huddles, optionally filtered by `expert_id` and/or `status` (`awaiting_expert`, `responded`, `synthesized`). Response contains `huddles` and the expert disclaimer. **422** for an unknown status.

```bash
curl 'http://127.0.0.1:8000/api/huddles?expert_id=demo-onc-001&status=awaiting_expert'
```

### `GET /api/huddles/{huddle_id}`

Returns full huddle state: huddle row, embedded question, evidence, expert, responses, brief, and disclaimer. **404** if missing.

```bash
curl http://127.0.0.1:8000/api/huddles/HUDDLE_ID
```

### `POST /api/huddles/{huddle_id}/response`

Stores a response from the huddle's assigned demo expert and advances status to `responded`. **Request:**

```json
{"expert_id":"demo-onc-001","mode":"text","text":"Response text","transcript":null,"audio_url":null,"duration_seconds":null}
```

`mode` is `text` or `voice`; voice metadata is optional. **Response 201** returns `huddle_id`, `status`, stored `response`, and expert disclaimers. **404** if the huddle/expert is missing, **409** if no longer awaiting a response, **422** if the expert does not match or fields are invalid.

```bash
curl -X POST http://127.0.0.1:8000/api/huddles/HUDDLE_ID/response \
  -H 'Content-Type: application/json' \
  -d '{"expert_id":"demo-onc-001","mode":"text","text":"Response text"}'
```

### `POST /api/huddles/{huddle_id}/simulate-response`

Stores a clearly labeled synthetic response and advances status to `responded`. It does not add clinical evidence. **Response 201** contains the stored response and disclaimers. **404** if the huddle/question is missing, **409** if the huddle is not awaiting a response.

```bash
curl -X POST http://127.0.0.1:8000/api/huddles/HUDDLE_ID/simulate-response
```

### `GET /api/huddles/{huddle_id}/synthesis-input`

Returns the sanitized structured question, attached evidence IDs/titles/snippets/citations, expert profile and stored response(s), safety rules, and disclaimer. **404** if the huddle is missing.

```bash
curl http://127.0.0.1:8000/api/huddles/HUDDLE_ID/synthesis-input
```

### `POST /api/huddles/{huddle_id}/synthesize`

Generates and stores the source-checked Clinical Huddle Brief. Uses the configured LLM if available and grounded; otherwise uses the deterministic template. The brief separates `EVIDENCE`, `EXPERT OPINION`, `AI SYNTHESIS`, uncertainty, and source metadata. Repeated calls after synthesis return the stored brief. **409** until an expert response exists; **404** if missing.

```bash
curl -X POST http://127.0.0.1:8000/api/huddles/HUDDLE_ID/synthesize
```

### `PUT /api/huddles/{huddle_id}/brief`

Stores a brief generated externally using the same schema and source/response validation. Required top-level fields: `question`, `evidence`, `expert_perspective`, `key_takeaways`, nonempty `uncertainty`, `sources`, `generated_by` (`llm`, `template`, or `external`), and the required disclaimer. Evidence and takeaway items contain text/point, `source_ids`, and their fixed section label. Expert perspective contains verbatim response summary, expert name, `is_simulated`, optional `audio_url`, and `EXPERT OPINION` label. Source entries contain exact attached `id`, `citation`, nullable `url`, and `verified`.

**Response 200** returns huddle ID, synthesized status, and stored brief. **409** until a response exists; **422** for schema, citation, source metadata, or response-grounding failures; **404** if missing.

```bash
curl -X PUT http://127.0.0.1:8000/api/huddles/HUDDLE_ID/brief \
  -H 'Content-Type: application/json' --data-binary @brief.json
```

## Audio

### `POST /api/audio`

Multipart upload with form field `file`. Accepts webm, mp3, wav, or m4a up to 10 MB, saves to local `backend/static/audio/`, and returns `audio_url`, `content_type`, and `size_bytes`. Unsupported extension/MIME returns **415**; empty file **422**; oversize file **413**.

```bash
curl -X POST http://127.0.0.1:8000/api/audio -F 'file=@response.wav;type=audio/wav'
```

### `GET /static/audio/{filename}`

Serves a previously uploaded audio file. Files are local to the service instance; use persistent storage if they must survive restart.

```bash
curl http://127.0.0.1:8000/static/audio/FILENAME.wav --output response.wav
```

## Question Graph analytics

### `GET /api/analytics/questions`

Query parameters: `days` (1–365, default 30) and optional `specialty`. Returns `total`, descending `by_specialty`, `by_condition`, `by_topic`, `by_intent` count lists, descending `unanswered` topic/condition clusters, rising `emerging` topics (`last_7d`, `prior_7d`, fractional `growth`), chronological daily `timeseries`, and `includes_seeded_data`. It contains no question text, signal IDs, or HCP identity.

```bash
curl 'http://127.0.0.1:8000/api/analytics/questions?days=30&specialty=Oncology'
```

## Demo tooling

### `GET /api/demo/golden-path`

Returns the three synthetic example questions from `data/demo_questions.json`, including expected taxonomy structure and synthetic context. No question is written until submitted to `POST /api/questions`.

```bash
curl http://127.0.0.1:8000/api/demo/golden-path
```

### `POST /api/demo/reset`

Only enabled when `DEMO_MODE=true`; otherwise returns **404**. Removes questions, huddles, responses, and live analytics signals, then ensures demo profiles/signals are seeded. It retains evidence, experts, and audio files. **Response 200:** `{"status":"reset","questions":0,"huddles":0,"seeded_signals":80}`.

```bash
curl -X POST http://127.0.0.1:8000/api/demo/reset
```
