# PULSEPOINT — Backend Spec (Backend + RAG + Data)

You are building the BACKEND for PULSEPOINT, a HackGT 13 project (36-hour hackathon, 4-person team). I own the backend, retrieval, and data layer ONLY. Do NOT create or modify anything under `frontend/`. Work only in `backend/`, `data/`, and `docs/` (plus root README section for backend).

PULSEPOINT: an HCP asks a clinical question → we structure it → retrieve evidence → match a verified demo expert → expert responds (text/voice) → synthesize a "Clinical Huddle Brief" → the question becomes an anonymized signal for a Question Graph.

PRIORITIES (in order): RELIABILITY > SIMPLICITY > DEMO QUALITY > feature count. Every external dependency (LLM, network, embeddings) MUST have a deterministic offline fallback. The full demo must run with no API keys and no internet.

Work is done ONE PHASE PER CODEX TASK. At the end of each phase: run the tests, then put a milestone report in this exact format at the top of the PR description:

```
DONE: ...
API: ...
INPUT: ...
OUTPUT: ...
DEPENDENCIES: ...
NEXT: ...
```

---

## HARD SAFETY RULES (apply everywhere)

1. NEVER invent citations, titles, authors, dates, URLs, PMIDs, or NCT IDs. Evidence may only come from the committed corpus file, whose entries come from real public records (see Phase 3). If you cannot fetch real data, create entries with `"verified": false`, `"source_type": "Simulated (demo placeholder)"`, `"url": null`, and a title beginning with `[SIMULATED]`. Never make a simulated source look real.
2. Evidence snippets are VERBATIM text from the source record. The LLM never writes or edits snippets.
3. All expert profiles are fictional. Every expert has `"is_demo": true`, and every API response containing experts includes `"disclaimer": "Demo profile — fictional expert for prototype purposes."`
4. Simulated expert responses have `"is_simulated": true` and are labeled in the brief.
5. The system never diagnoses, prescribes, or claims certainty. Synthesis output separates EVIDENCE vs EXPERT OPINION vs AI SYNTHESIS, and always includes an UNCERTAINTY section.
6. PHI scrubbing: before storing question text, run a regex scrubber (names after "Mr./Mrs./Ms./Dr." inside patient context, dates of birth, MRN-like numbers, phone numbers, emails, SSN patterns). Replace with `[REDACTED]` and set `phi_detected: true`. QuestionSignals (analytics) NEVER store free text — only category fields + timestamp.
7. No secrets in code. Use `.env` with `.env.example`. Add `.env` and `*.db` to `.gitignore`.
8. Match score is a ROUTING score, never a correctness or credential score. Name the field `match_score` and include `"score_note": "Routing relevance score, not a measure of clinical expertise or correctness."`

---

## STACK

- Python 3.11+, FastAPI, Uvicorn, Pydantic v2
- SQLModel on SQLite (`backend/pulsepoint.db`)
- Retrieval: `rank_bm25` (primary). Optional embeddings behind `USE_EMBEDDINGS=false` flag — default OFF.
- LLM: provider-agnostic wrapper. Env: `LLM_PROVIDER=none|anthropic|openai` (default `none`), `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS=8`. Any error/timeout → fall back to rules. Never crash on LLM failure.
- `httpx` for outbound calls, `pytest` for tests.
- CORS: allow `http://localhost:3000` and `CORS_ORIGINS` env list (for the Vercel domain).

---

## REPO LAYOUT

```
pulsepoint/
  backend/
    app/
      main.py              # FastAPI app, CORS, routers, startup seeding
      config.py            # env settings (pydantic-settings)
      db.py                # engine, session, init_db
      models.py            # SQLModel tables
      schemas.py           # request/response Pydantic models
      taxonomy.py          # controlled vocab: specialties, conditions, topics, intents + keyword maps
      routers/
        questions.py
        evidence.py
        experts.py
        huddles.py
        analytics.py
        demo.py
        audio.py
      services/
        phi.py             # PHI scrubber
        llm.py             # provider wrapper + timeout + fallback signal
        extraction.py      # LLM extraction → validated against taxonomy → rules fallback
        retrieval.py       # chunking, BM25 index, metadata boosting, top-k
        matching.py        # transparent expert scoring
        synthesis.py       # LLM brief + deterministic template fallback
        analytics.py
    scripts/
      fetch_corpus.py      # pulls REAL records from PubMed + ClinicalTrials.gov → data/corpus.json
      seed.py              # loads experts, corpus, demo signals into SQLite
    tests/
    requirements.txt
    .env.example
    README.md
  data/
    corpus.json            # committed; runtime ONLY reads this (no live fetching at runtime)
    experts.json
    demo_signals.json
    demo_questions.json    # golden-path demo questions with expected structure
    fixtures/              # sample JSON responses for every endpoint, for the frontend teammate
  docs/
    API.md  DATA_MODEL.md  RAG.md  SAFETY.md  (backend sections of ARCHITECTURE.md, DEMO.md)
```

---

## PHASE 1 — Scaffold + models (target: 1–2 hrs)

Create the layout, `requirements.txt`, config, DB init, `GET /api/health` returning `{status, db, llm_provider, corpus_size, experts_count}`.

`taxonomy.py` controlled vocabulary (demo focus is 3 specialties so matching and retrieval stay sharp):

- Specialties: Oncology, Cardiology, Endocrinology
- Conditions: Oncology → Breast cancer, Lung cancer; Cardiology → Heart failure, Atrial fibrillation; Endocrinology → Type 2 diabetes, Obesity
- Topics: Treatment sequencing, Side-effect management, Clinical trials, Access/coverage, Guideline update, Drug interactions, Monitoring
- Intents: Clinical update, Evidence review, Case consult, Safety concern, Access question
- Include a keyword/synonym map for each value (e.g. "HER2", "CDK4/6", "tamoxifen" → Breast cancer; "HFrEF", "SGLT2", "ejection fraction" → Heart failure; "anticoagulation", "DOAC", "AFib" → Atrial fibrillation; "metformin", "A1c", "GLP-1" → Type 2 diabetes; "next line", "after progression", "sequence" → Treatment sequencing; "trial", "enrolling", "NCT" → Clinical trials; "prior auth", "coverage", "insurance" → Access/coverage; "what's new", "recently", "changed" → Clinical update). Unknown values map to `"Other"`.

SQLModel tables (keep simple; JSON columns for lists):

- `HCPQuestion`: id (uuid str), raw_text (scrubbed), question (normalized one-sentence), specialty, condition, topic, intent, key_context (list[str]), extraction_method ("llm"|"rules"|"demo_cache"), confidence (0–1), phi_detected (bool), created_at
- `EvidenceSource`: id, title, source_type, date, url (nullable), citation, publisher, specialty, condition, topics (list), verified (bool), full_text
- `EvidenceChunk`: id, source_id, chunk_index, text
- `Expert`: id, name, title, specialty, conditions (list), topics (list), expertise (list[str]), availability ("available"|"busy"|"offline"), bio, is_demo (always true)
- `Huddle`: id, question_id, expert_id, evidence_ids (list), status ("awaiting_expert"|"responded"|"synthesized"), brief (JSON nullable), created_at, updated_at
- `ExpertResponse`: id, huddle_id, expert_id, mode ("text"|"voice"), text, transcript (nullable), audio_url (nullable), duration_seconds (nullable), is_simulated (bool), created_at
- `QuestionSignal`: id, specialty, condition, topic, intent, answered (bool), is_seeded (bool), timestamp — NO free text

Tests: health endpoint works, tables create cleanly.

## PHASE 2 — Question API (target: 1 hr)

`POST /api/questions` — input `{ "text": "..." }` (reject empty or >2000 chars with 422).
Pipeline: PHI scrub → if text exactly/near-matches a `data/demo_questions.json` entry use its cached structure (`extraction_method: "demo_cache"`, keeps the live demo deterministic) → else LLM extraction with strict JSON-only prompt, validate every field against taxonomy (invalid → treat as failure) → else rules extractor (keyword scoring over taxonomy maps; specialty inferred from condition; default intent "Evidence review"). Then save question AND create a `QuestionSignal` (answered=false).

Output:
```json
{ "question_id": "...", "specialty": "Oncology", "condition": "Breast cancer",
  "topic": "Treatment sequencing", "intent": "Clinical update",
  "question": "What has changed recently in treatment sequencing for breast cancer?",
  "key_context": ["complicated treatment history"],
  "extraction_method": "rules", "confidence": 0.72, "phi_detected": false }
```

`GET /api/questions/{id}` returns the same shape; 404 with `{ "detail": "Question not found" }`.

Create `data/demo_questions.json` with 3 golden-path questions (one per specialty), including the doc's example: "I have a patient with a complicated treatment history. What's changed recently in the relevant treatment landscape, and what evidence should I review?" — map that one to Oncology / Breast cancer / Treatment sequencing / Clinical update (demo patient context: synthetic HR+/HER2- metastatic breast cancer; state this in `key_context`, all synthetic).

Tests: rules extractor on 10+ phrasings, taxonomy validation rejects bad LLM output, PHI scrubber catches phone/email/MRN/DOB, demo cache hit.

## PHASE 3 — Evidence corpus + retrieval (target: 2 hrs)

### 3a. `scripts/fetch_corpus.py` (run once, output committed)
For each (condition, topic) query pair in a config list (~4 queries per condition, 6 conditions):
- PubMed E-utilities: `esearch.fcgi?db=pubmed&term=<query>&retmax=5&sort=relevance` (add date filter for last ~5 years), then `efetch.fcgi?db=pubmed&id=...&retmode=xml`. Parse title, journal, pub date, PMID, abstract text. `url = https://pubmed.ncbi.nlm.nih.gov/<PMID>/`, `source_type = "PubMed abstract"`, citation = "Journal. Year. PMID: <PMID>".
- ClinicalTrials.gov API v2: `https://clinicaltrials.gov/api/v2/studies?query.cond=<condition>&query.term=<topic>&pageSize=3`. Use brief title, NCT ID, start/last-update date, brief summary. `url = https://clinicaltrials.gov/study/<NCTID>`, `source_type = "Clinical trial registry"`.
- Respect NCBI rate limits (≤3 req/s, add `tool` and `email` params from env). Skip records with no abstract/summary. Dedupe by PMID/NCT. Mark `verified: true` (it's the real record). Tag each record with the specialty/condition/topics of the query that found it.
- Write `data/corpus.json`. If the network is unavailable in your environment, write the script anyway, tell me to run it locally, and meanwhile create at most 6 clearly-labeled `[SIMULATED]` placeholders (verified=false, url=null) so the pipeline works. Do NOT write real-looking fake records.

### 3b. `services/retrieval.py`
- Chunking: split `full_text` into ~2–4 sentence windows (~80–120 words) with 1-sentence overlap.
- Build a BM25 index over chunks at startup (tokenize lowercase, strip stopwords, keep tokens like "her2", "cdk4/6", "sglt2").
- Query = question.question + condition + topic + expanded taxonomy synonyms.
- Score = BM25 × metadata boost (×1.5 same condition, ×1.2 topic in source.topics, ×0.5 different specialty). Aggregate to source level (best chunk wins), return top-k=5 with at most 1 chunk per source.
- If fewer than 2 results score above a threshold, fall back to same-condition sources sorted by date (still real), flag `retrieval_method: "fallback_condition_match"`.
- Optional embeddings path behind `USE_EMBEDDINGS` flag: hybrid = 0.5 BM25(norm) + 0.5 cosine. Off by default; tests must pass with it off.

`GET /api/evidence/{question_id}` →
```json
{ "question_id": "...", "retrieval_method": "bm25",
  "sources": [ { "id": "...", "title": "...", "type": "PubMed abstract", "date": "2024-05-01",
    "snippet": "<verbatim chunk>", "url": "https://pubmed.ncbi.nlm.nih.gov/.../",
    "citation": "...", "relevance": 0.83, "verified": true } ] }
```
Cache results per question_id so repeated calls are identical (deterministic demo).

Tests: every returned snippet is a substring of its source full_text; every verified source has a url; simulated sources have `verified: false`; golden-path question returns ≥3 sources of the right condition.

## PHASE 4 — Experts + matching (target: 1 hr)

`data/experts.json`: 12 fictional demo experts (4 per specialty) with varied conditions, topics, expertise tags, and availability (mix of available/busy/offline). Names must be clearly fictional-sounding generic names; titles like "Medical Oncologist (Demo Profile)". Include "Dr. Maya Patel" (Oncology: Breast cancer, Treatment sequencing, Clinical trials, available) and "Dr. Daniel Kim" (Cardiology: Atrial fibrillation, Heart failure) from the spec.

`services/matching.py` — transparent weighted score, 0–100:
- specialty match: 35
- condition match: 25
- topic match: 20
- expertise overlap (Jaccard of question keywords/key_context vs expertise tags, scaled): 10
- availability: available 10, busy 4, offline 0

`GET /api/experts/match/{question_id}` → top 3:
```json
{ "experts": [ { "id": "...", "name": "Dr. Maya Patel", "title": "...", "specialty": "Oncology",
   "expertise": ["Breast cancer", "Treatment sequencing", "Clinical trials"],
   "match_score": 94, "availability": "available",
   "score_breakdown": { "specialty": 35, "condition": 25, "topic": 20, "expertise": 4, "availability": 10 },
   "is_demo": true } ],
  "disclaimer": "Demo profile — fictional expert for prototype purposes.",
  "score_note": "Routing relevance score, not a measure of clinical expertise or correctness." }
```
Ties broken by availability then id (deterministic). Also `GET /api/experts` and `GET /api/experts/{id}`.

Tests: golden-path oncology question ranks Dr. Maya Patel #1; scores sum to breakdown; offline experts never outrank equally-matched available ones.

## PHASE 5 — Huddles (target: 1 hr)

- `POST /api/huddles` input `{ "question_id", "expert_id", "evidence_ids": [] }`. If `evidence_ids` empty, auto-fill with the cached evidence for that question. Validate all ids exist (404/422). Status → `awaiting_expert`.
- `GET /api/huddles/{id}` → full state: huddle + embedded question + evidence sources + expert + responses + brief.
- `GET /api/huddles?expert_id=...&status=...` → inbox for the expert view.
- `POST /api/huddles/{id}/response` input `{ "expert_id", "mode": "text"|"voice", "text", "transcript"?, "audio_url"?, "duration_seconds"? }`. Store `ExpertResponse`, status → `responded`, mark the question's QuestionSignal `answered=true`.
- `POST /api/huddles/{id}/simulate-response` → inserts a pre-written, generic, evidence-referencing expert reply for the golden-path questions (from `demo_questions.json`), `is_simulated: true`. For non-demo questions use a neutral template that only points back to the retrieved sources. This is the fallback if the live expert step fails.
- `POST /api/audio` multipart upload (webm/mp3/wav/m4a, ≤10 MB) → saves to `backend/static/audio/`, served at `/static/audio/<file>`, returns `{ "audio_url": "..." }`. Speech-to-text is the voice teammate's job; we just store `transcript` when they send it.

Status transitions must be validated (e.g. can't synthesize before a response exists → 409).

## PHASE 6 — Synthesis input + Huddle Brief (target: 1–2 hrs)

- `GET /api/huddles/{id}/synthesis-input` → a clean payload for the AI teammate: question, evidence (id, title, snippet, citation), expert response(s) with `is_simulated`, plus the safety rules.
- `POST /api/huddles/{id}/synthesize` → produce and store the brief. LLM path uses a strict JSON prompt that may ONLY use provided snippets and the expert response, must cite source ids inline like `[S1]`, and must not add outside facts. Validate: every cited id exists in the huddle evidence; otherwise discard and use fallback. Fallback = deterministic template built from the question, first sentence of each snippet (verbatim, quoted, cited), and the expert text.
- Also `PUT /api/huddles/{id}/brief` so the AI teammate can store a brief they generated elsewhere (same schema, same citation validation).

Brief schema:
```json
{ "question": "...",
  "evidence": [ { "statement": "...", "source_ids": ["..."], "label": "EVIDENCE" } ],
  "expert_perspective": { "summary": "...", "expert_name": "...", "is_simulated": false, "audio_url": null, "label": "EXPERT OPINION" },
  "key_takeaways": [ { "point": "...", "source_ids": [], "label": "AI SYNTHESIS" } ],
  "uncertainty": ["..."],
  "sources": [ { "id": "...", "citation": "...", "url": "...", "verified": true } ],
  "generated_by": "llm"|"template"|"external",
  "disclaimer": "Prototype decision-support summary. Not medical advice; does not replace clinical judgment. Expert profiles are fictional demo profiles." }
```
Status → `synthesized`. Uncertainty must always have ≥1 item (template default: limits of a small curated corpus + single expert view).

## PHASE 7 — Question Graph analytics (target: 1 hr)

- `data/demo_signals.json`: ~80 seeded anonymized signals across specialties/conditions/topics/intents over the last 30 days (`is_seeded: true`), skewed so Breast cancer + Treatment sequencing is the top bar. Generate them with a fixed random seed in `seed.py` rather than by hand.
- `GET /api/analytics/questions?days=30&specialty=` →
```json
{ "total": 83,
  "by_specialty": [ { "name": "Oncology", "count": 34 } ],
  "by_condition": [...], "by_topic": [...], "by_intent": [...],
  "unanswered": [ { "topic": "...", "condition": "...", "count": 5 } ],
  "emerging": [ { "topic": "...", "last_7d": 9, "prior_7d": 3, "growth": 2.0 } ],
  "timeseries": [ { "date": "2026-09-01", "count": 3 } ],
  "includes_seeded_data": true }
```
All lists sorted desc by count, Recharts-friendly (`name`/`count`). Live questions submitted during the demo must appear immediately.

## PHASE 8 — Demo tooling, fixtures, hardening

- `POST /api/demo/reset` (only when `DEMO_MODE=true`): wipe questions/huddles/responses/live signals, reseed. For rehearsals.
- `GET /api/demo/golden-path` → the 3 demo questions so the frontend can offer one-tap examples.
- Seeding runs automatically on startup if tables are empty.
- Global exception handler: never leak stack traces; return `{ "detail": "...", "code": "..." }`.
- Log timing per request; every endpoint except synthesize should respond in <300 ms offline.
- Write `data/fixtures/*.json`: one real sample response per endpoint (generated by actually calling the API in a script), so the frontend teammate can mock against them.
- End-to-end test: submit golden-path question → evidence → match → create huddle → simulated response → synthesize → analytics count increased. Must pass with `LLM_PROVIDER=none` and no network.

## PHASE 9 — Docs

- `backend/README.md`: setup (venv, `pip install -r requirements.txt`, `cp .env.example .env`, `python -m scripts.fetch_corpus`, `python -m scripts.seed`, `uvicorn app.main:app --reload --port 8000`), running tests, env vars, deploy notes for Render/Railway (start command, `PORT` env, persistent disk or reseed-on-boot for SQLite).
- `docs/API.md`: every endpoint with method, path, request, response, errors, and curl example. Note that `/docs` (Swagger) is live.
- `docs/DATA_MODEL.md`: tables + relationships + taxonomy.
- `docs/RAG.md`: corpus sources, fetch process, chunking, BM25 + boosts, fallback, how to add documents, the no-fabrication rule.
- `docs/SAFETY.md` (backend section): PHI scrubbing, demo labels, citation validation, simulated-response labeling.
- Final milestone report in the DONE/API/INPUT/OUTPUT/DEPENDENCIES/NEXT format, including a short "Integration notes for frontend / AI / voice teammates" list.

---

Only implement the phase you were asked for. If a rule here blocks you, say so in the PR description instead of breaking the rule.
