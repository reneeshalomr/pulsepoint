# Backend Safety Notes

PULSEPOINT is a HackGT prototype for organizing clinical questions and discussion. It is not a diagnostic tool, treatment recommender, medical advice, EMR, or advertising platform. The backend must not diagnose, prescribe, claim certainty, or present synthetic content as real evidence or real clinicians.

## PHI and question data

`POST /api/questions` runs the input through the regex scrubber before extraction or persistence. Recognized patterns include honorific plus likely name, date of birth, MRN-like token, US SSN, phone number, and email. Matching text is replaced with `[REDACTED]` and `phi_detected` is set. Question GET responses omit `raw_text`; validation errors deliberately return only a generic error and do not echo submitted values.

This is a prototype regex scrubber, not a certified de-identification process. It can miss identifiers and can redact innocent text. Do not submit unnecessary patient details or rely on this system as the only PHI safeguard. Keep persisted SQLite files and backups protected.

## Analytics and identity minimization

`QuestionSignal` stores only specialty, condition, topic, intent, answered state, seeded flag, and timestamp. It has no question ID, free text, HCP identity, or expert identity. The Question Graph endpoint returns aggregates (counts and date buckets), not signal records. Do not add raw text, IDs, names, specialties unique to individual users, or other identifying fields to analytics signals or aggregate output.

Seeded Question Graph data is synthetic and generated from a fixed random seed. It is labeled internally as seeded; aggregate output reports whether seeded data is included. Demo reset deletes live signals along with questions and huddles, then restores the seeded baseline.

## Evidence and citation integrity

- Runtime retrieval reads only the committed `data/corpus.json` and persisted copies of its source records; it makes no live evidence request.
- Source snippets are verbatim substrings of `full_text`. LLM output cannot create or modify evidence snippets.
- Each brief's evidence and takeaways are checked against the huddle's attached source IDs and source text. Citation IDs and `citation`/`url`/`verified` metadata must match attached corpus records. Unvalidated LLM synthesis is discarded in favor of the deterministic template.
- Never invent an identifier, citation, title, author, date, URL, or clinical claim. Simulated corpus placeholders use `[SIMULATED]`, `verified: false`, and `url: null`; they are not evidence and must remain visibly labeled.
- Every brief includes uncertainty and a decision-support disclaimer. Review source records and context independently.

## Demo experts and responses

All seeded profiles are fictional and use `is_demo: true`; API responses containing experts include `Demo profile — fictional expert for prototype purposes.` Do not replace synthetic profiles with real people or imply verification/credentials. Simulated responses are stored with `is_simulated: true`, state that they are synthetic, and add no clinical evidence. The brief retains the simulated marker and labels expert perspective separately from evidence and AI synthesis.

## Models and failures

`LLM_PROVIDER=none` is the supported no-key offline mode. Optional LLM calls have a timeout and fall back to deterministic rules/templates. Provider output is treated as untrusted and checked before persistence. Generic 500 responses include a stable error code but no stack trace. Request validation output does not echo potentially sensitive input. Request logs contain method/path/status/timing only, never request bodies.

`POST /api/demo/reset` is enabled only when `DEMO_MODE=true`; it is for prototype rehearsal data, not general data deletion. Set `DEMO_MODE=false` in any deployment where that operation should be unavailable.
