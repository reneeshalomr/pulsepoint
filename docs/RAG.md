# Evidence Corpus and Retrieval

Runtime retrieval uses the committed `data/corpus.json`; API requests do not call PubMed or ClinicalTrials.gov. This makes offline runs reproducible and keeps source provenance reviewable. The fetcher is an explicit maintenance command, not part of application startup.

## Corpus records

Each JSON record contains an `external_id`, `title`, `source_type`, optional `date` and `url`, `citation`, `publisher`, `specialty`, `condition`, `topics`, `verified`, and `full_text`. PubMed records use PMID identities and ClinicalTrials.gov records use NCT identities. Source text is copied from the public abstract/summary.

Real records fetched from source APIs may be marked `verified: true` and must retain source-provided metadata and a working source URL. Never construct a plausible citation, title, author, date, URL, PMID, or NCT number. A demo placeholder must remain visibly simulated: title starts `[SIMULATED]`, `verified` is false, `url` is null, and `source_type` identifies it as simulated. Placeholder text is not clinical evidence.

## Fetch / refresh

From `backend/`:

```bash
python -m scripts.fetch_corpus
python -m scripts.seed
```

`scripts/fetch_corpus.py` searches PubMed E-utilities and the ClinicalTrials.gov API v2 across the configured condition/topic pairs. PubMed searches use a recent-publication window, then fetch abstracts. Trial records use public brief summaries. The fetcher:

- uses HTTP timeouts of 10 seconds and retries transient HTTP/transport/time-out errors up to three times;
- stays below the NCBI request rate limit and accepts optional `NCBI_TOOL` and `NCBI_EMAIL` environment values;
- skips records without usable abstract/summary text;
- deduplicates by PMID/NCT identity and tags a record with the specialty, condition, and topic that found it;
- caps output at 50 PubMed and 50 trial records.

If the public APIs are unreachable or return no usable records, the script preserves a valid existing committed corpus. It does not create realistic-looking fake results. Inspect the resulting diff and verify source links/metadata before committing corpus changes. Then run `python -m scripts.seed` (or restart the app, whose startup seeds the corpus) to load new source rows and verbatim text chunks into the local database. When a refreshed corpus contains verified PubMed or ClinicalTrials.gov records, seeding removes only obsolete `[SIMULATED]` placeholder rows and their chunks; unrelated/imported source rows are preserved. Restart the app after refreshing so the process-local corpus/retrieval caches are cleared. Runtime retrieval also reads the committed file directly.

## Chunking and ranking

Text is split on sentence boundaries into windows of up to four sentences, targeting around 80 words before ending a window and keeping one sentence of overlap. Short sources can remain a single chunk. Chunks are substrings of `full_text`; they are not generated or edited by an LLM.

The default ranker is `rank_bm25` (BM25Okapi). It lowercases and tokenizes text while retaining clinically meaningful tokens such as `HER2`, `CDK4/6`, and `SGLT2`. A question query combines the normalized question with its condition/topic/specialty and taxonomy synonyms. Matching condition and topic metadata boost scores; a mismatched specialty is down-weighted. Results are aggregated to one best chunk per source and ties use stable source identities. The standard result count is five and the API accepts 1–12.

When too few records score above the relevance threshold, retrieval returns same-condition records in stable date/identity order and reports `fallback_condition_match`. Otherwise the method is `bm25`. Similarity scores are routing aids, not clinical certainty. `USE_EMBEDDINGS` defaults to false; the current retrieval path is deterministic BM25 and has no required embedding service.

## Add or correct a source

1. Obtain the source record from PubMed or ClinicalTrials.gov (or retain the source's existing committed metadata).
2. Preserve its real public identifier, title, source URL, date, citation text, and exact source abstract/summary. Do not paraphrase `full_text` to fit a topic.
3. Add/update the corpus entry and taxonomy tags, retaining or setting `verified` only according to actual provenance. Use the explicit simulated-placeholder convention for non-evidence demo entries.
4. Run `python -m scripts.seed` and `pytest -q` from `backend/`; check returned snippets are source-text substrings and verified entries have URLs.
5. Commit corpus edits with their source provenance. The application will not fetch or fabricate records at runtime.
