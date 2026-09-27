# Backend Data Model

The service uses SQLModel/SQLAlchemy with SQLite. Tables are created at startup by `SQLModel.metadata.create_all`; development database defaults to `backend/pulsepoint.db` when launched from `backend/`. Lists and the huddle brief are stored as JSON columns for this prototype.

## Tables

| Table | Fields | Purpose / references |
| --- | --- | --- |
| `hcpquestion` (`HCPQuestion`) | `id` (UUID string PK), scrubbed `raw_text`, normalized one-sentence `question`, `specialty`, `condition`, `topic`, `intent`, `key_context` (JSON string list), `extraction_method`, `confidence`, `phi_detected`, `created_at` | Stored structured question. Raw text is persisted only after PHI scrubbing. No author, clinician ID, or account field exists. |
| `evidencesource` (`EvidenceSource`) | `id` (UUID PK), optional `external_id`, `title`, `source_type`, optional `date`/`url`, `citation`, `publisher`, `specialty`, `condition`, `topics` (JSON string list), `verified`, `full_text` | Canonical source records seeded from `data/corpus.json` or imported from that same file. `external_id` indexes the public source identity. |
| `evidencechunk` (`EvidenceChunk`) | `id` (UUID PK), `source_id` (FK to `evidencesource.id`), `chunk_index`, `text` | Search/synthesis text chunks. Each chunk is copied verbatim from its source's `full_text`. |
| `expert` (`Expert`) | `id` (stable profile ID PK), `name`, `title`, `specialty`, `conditions`, `topics`, `expertise` (JSON string lists), `availability`, `bio`, `is_demo` | Seeded synthetic routing profiles from `data/experts.json`. Demo profiles are never represented as real physicians. |
| `huddle` (`Huddle`) | `id` (UUID PK), `question_id` (FK to `hcpquestion.id`), `expert_id` (FK to `expert.id`), `evidence_ids` (JSON string list of source IDs), `status`, optional `brief` (JSON), `created_at`, `updated_at` | Huddle workflow state: `awaiting_expert` → `responded` → `synthesized`. Evidence is constrained by the API to source identities in the committed corpus or stored source table. |
| `expertresponse` (`ExpertResponse`) | `id` (UUID PK), `huddle_id` (FK to `huddle.id`), `expert_id` (FK to `expert.id`), `mode`, `text`, optional `transcript`, `audio_url`, `duration_seconds`, `is_simulated`, `created_at` | Response stored for the huddle. Synthetic responses always have `is_simulated=true`; voice files are local static assets unless storage is replaced. |
| `questionsignal` (`QuestionSignal`) | `id` (UUID PK), `specialty`, `condition`, `topic`, `intent`, `answered`, `is_seeded`, `timestamp` | Analytics-only categories. **Never add question text, question ID, HCP identity, or expert identity here.** A signal is created alongside a question; response submission marks a matching live unanswered signal answered. |

## Relationships

```text
HCPQuestion 1 ── * Huddle * ── 1 Expert
                  │
                  └── * ExpertResponse * ── 1 Expert

EvidenceSource 1 ── * EvidenceChunk
Huddle.evidence_ids ── JSON list of attached EvidenceSource identifiers

HCPQuestion ── creates category-only QuestionSignal (no question ID stored)
```

`Huddle.evidence_ids` is a JSON list rather than a relational join table. `QuestionSignal` intentionally has no foreign key to a question so analytics cannot directly re-identify a stored question.

## Taxonomy

Canonical values are defined in `backend/app/taxonomy.py` and used by extraction, matching, retrieval, and analytics.

| Specialty | Conditions |
| --- | --- |
| Oncology | Breast cancer; Lung cancer |
| Cardiology | Heart failure; Atrial fibrillation |
| Endocrinology | Type 2 diabetes; Obesity |

Topics: Treatment sequencing, Side-effect management, Clinical trials, Access/coverage, Guideline update, Drug interactions, Monitoring.

Intents: Clinical update, Evidence review, Case consult, Safety concern, Access question.

Unknown structured values use `Other` where the extraction schema permits it. The keyword/synonym map is a deterministic rule fallback, not a medical ontology.

## Seed data and lifecycle

- `data/demo_questions.json`: three synthetic golden-path inputs and expected structure.
- `data/demo_signals.json`: 80 category-only demo rows created using fixed random seed 713; topic/condition weights make Breast cancer + Treatment sequencing the leading combination.
- `data/experts.json`: synthetic routing profiles.
- `data/corpus.json`: source metadata and text; see [RAG.md](RAG.md) for provenance and offline rules.
- Startup and `python -m scripts.seed` idempotently ensure experts, corpus sources/chunks, and demo signals. `POST /api/demo/reset` clears questions/huddles/responses/live signals and preserves these baseline records.
