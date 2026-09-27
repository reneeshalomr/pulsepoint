import json

import httpx
import pytest
from sqlmodel import Session, select

from app.models import EvidenceChunk, EvidenceSource
from app.services import retrieval
from scripts import fetch_corpus, seed


def test_checked_in_corpus_has_source_provenance_or_labeled_offline_fallback():
    records = json.loads(retrieval.CORPUS_PATH.read_text(encoding="utf-8"))
    assert records
    required = {"external_id", "title", "source_type", "date", "url", "citation", "publisher",
                "specialty", "condition", "topics", "verified", "full_text"}
    identities = set()
    real_records = []
    for record in records:
        assert required <= record.keys()
        assert record["external_id"] not in identities
        identities.add(record["external_id"])
        if record["source_type"].startswith("Simulated"):
            assert record["verified"] is False
            assert record["url"] is None
            assert record["title"].startswith("[SIMULATED]")
        if record["verified"]:
            assert record["external_id"]
            assert record["title"] and record["citation"] and record["publisher"]
            assert record["full_text"]
            if record["source_type"] == "PubMed abstract":
                assert record["external_id"].startswith("PMID:")
                assert record["url"] == f"https://pubmed.ncbi.nlm.nih.gov/{record['external_id'].removeprefix('PMID:')}/"
            elif record["source_type"] == "Clinical trial registry":
                assert record["external_id"].startswith("NCT")
                assert record["url"] == f"https://clinicaltrials.gov/study/{record['external_id']}"
            else:
                pytest.fail(f"Unrecognized verified source type: {record['source_type']}")
            real_records.append(record)
    if real_records:
        assert not any(record["source_type"].startswith("Simulated") for record in records)


def test_tokenizer_preserves_clinical_tokens():
    tokens = retrieval.tokenize("HER2 CDK4/6 SGLT2 and routine care")
    assert "her2" in tokens
    assert "cdk4/6" in tokens
    assert "sglt2" in tokens
    assert "and" not in tokens


def test_chunk_windows_overlap_by_one_sentence():
    sentences = [f"Sentence {i} contains several words for searching." for i in range(7)]
    chunks = retrieval.split_chunks(" ".join(sentences))
    assert len(chunks) >= 2
    assert any(sentence in chunks[0] and sentence in chunks[1] for sentence in sentences)


def test_search_returns_source_backed_records_with_verbatim_snippets():
    results = retrieval.search_sources(None, "new treatment sequencing evidence",
                                       condition="Breast cancer", topic="Treatment sequencing",
                                       specialty="Oncology", limit=5)
    assert results
    assert all(item["condition"] == "Breast cancer" for item in results)
    corpus_by_id = {item["external_id"]: item for item in retrieval.load_corpus()}
    for item in results:
        source = corpus_by_id[item["id"]]
        assert item["snippet"] in source["full_text"]
        if item["verified"]:
            assert item["url"]
            assert item["external_id"] == item["id"]
        else:
            assert source["source_type"].startswith("Simulated")
            assert source["title"].startswith("[SIMULATED]")
            assert item["url"] is None


def test_bm25_ties_break_by_external_id(monkeypatch):
    source_base = {"title": "Title", "source_type": "PubMed abstract", "date": "2024-01-01",
                   "url": "https://example.org/real-record", "citation": "Source citation",
                   "publisher": "Journal", "specialty": "Oncology", "condition": "Breast cancer",
                   "topics": ["Monitoring"], "verified": True, "full_text": "unique alpha token"}
    records = tuple({**source_base, "external_id": identifier} for identifier in ["PMID:Z", "PMID:A", "PMID:M"])
    monkeypatch.setattr(retrieval, "load_corpus", lambda: records)
    results = retrieval.search_sources(None, "alpha token", limit=3)
    assert [item["id"] for item in results] == ["PMID:A", "PMID:M", "PMID:Z"]


def test_evidence_search_endpoint_defaults_to_five_and_enforces_maximum(client):
    response = client.get("/api/evidence/search", params={"condition": "Breast cancer"})
    assert response.status_code == 200
    assert response.json()["limit"] == 5
    assert response.json()["count"] >= 3
    assert response.json()["retrieval_method"] in {"bm25", "fallback_condition_match"}
    too_many = client.get("/api/evidence/search", params={"limit": 13})
    assert too_many.status_code == 422
    limited = client.get("/api/evidence/search", params={"condition": "Breast cancer", "limit": 12})
    assert limited.status_code == 200
    assert limited.json()["count"] <= 12


def test_post_evidence_imports_only_corpus_backed_metadata(client, test_engine):
    source = retrieval.load_corpus()[0]
    source_id = source["external_id"]
    response = client.post("/api/evidence", json={"external_id": source_id})
    assert response.status_code == 201
    result = response.json()
    assert result["external_id"] == source_id
    assert result["verified"] is source["verified"]
    assert result["url"] == source["url"]
    assert result["citation"] == source["citation"]
    with Session(test_engine) as session:
        stored = session.exec(select(EvidenceSource).where(EvidenceSource.external_id == source_id)).one()
        assert stored.title == source["title"]
    assert client.post("/api/evidence", json={"external_id": "PMID:invented"}).status_code == 404


def test_reseeding_removes_only_replaced_simulated_source_and_its_chunks(test_engine, monkeypatch):
    records = [dict(retrieval.load_corpus()[0])]
    monkeypatch.setattr(seed, "load_corpus", lambda: records)
    with Session(test_engine) as session:
        stale = EvidenceSource(
            external_id="SIMULATED:REPLACED", title="[SIMULATED] Old placeholder",
            source_type="Simulated (demo placeholder)", date=None, url=None,
            citation="[SIMULATED] Placeholder", publisher="PULSEPOINT demo placeholder",
            specialty="Oncology", condition="Breast cancer", topics=["Treatment sequencing"],
            verified=False, full_text="Not evidence.",
        )
        legitimate = EvidenceSource(
            external_id="IMPORTED:KEEP", title="Legitimate imported source",
            source_type="Imported source", citation="Existing citation", publisher="Existing publisher",
            specialty="Oncology", condition="Breast cancer", topics=[], verified=False,
            full_text="Existing source text.",
        )
        session.add(stale)
        session.add(legitimate)
        session.commit()
        session.add(EvidenceChunk(source_id=stale.id, chunk_index=0, text="Not evidence."))
        session.commit()

        seed.ensure_corpus_sources(session)

        remaining_ids = set(session.exec(select(EvidenceSource.external_id)).all())
        assert "SIMULATED:REPLACED" not in remaining_ids
        assert "IMPORTED:KEEP" in remaining_ids
        assert records[0]["external_id"] in remaining_ids
        assert session.exec(select(EvidenceChunk).where(EvidenceChunk.source_id == stale.id)).all() == []


def test_corpus_fetcher_retries_transient_errors(monkeypatch):
    attempts = {"count": 0}

    def handler(request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(fetch_corpus.time, "sleep", lambda _: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = fetch_corpus._get(client, "https://example.test", {})
    assert response.json() == {"ok": True}
    assert attempts["count"] == 2


def test_corpus_fetcher_deduplicates_and_caps_each_source(monkeypatch):
    monkeypatch.setattr(fetch_corpus, "QUERY_PAIRS", [("Oncology", "Breast cancer", "monitoring")])
    pubmed = [{"external_id": f"PMID:{i}", "source_type": "PubMed abstract"} for i in range(55)]
    trials = [{"external_id": f"NCT{i:08d}", "source_type": "Clinical trial registry"} for i in range(55)]
    monkeypatch.setattr(fetch_corpus, "fetch_pubmed", lambda *args: pubmed + pubmed[:2])
    monkeypatch.setattr(fetch_corpus, "fetch_clinical_trials", lambda *args: trials + trials[:2])
    records = fetch_corpus.fetch_corpus(client=object())
    assert len(records) == 100
    assert sum(record["source_type"] == "PubMed abstract" for record in records) == 50
    assert sum(record["source_type"] == "Clinical trial registry" for record in records) == 50
    assert len({record["external_id"] for record in records}) == len(records)


def test_pubmed_and_trials_parsers_include_required_real_metadata():
    pubmed_xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123456</PMID><Article>
      <ArticleTitle>Recorded source title</ArticleTitle><Journal><Title>Recorded Journal</Title></Journal>
      <JournalIssue><PubDate><Year>2024</Year><Month>Feb</Month></PubDate></JournalIssue>
      <Abstract><AbstractText>Verbatim abstract text.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""
    trial_json = {"studies": [{"protocolSection": {
        "identificationModule": {"nctId": "NCT01234567", "briefTitle": "Recorded trial title"},
        "statusModule": {"studyFirstSubmitDate": "2024-02-03"},
        "descriptionModule": {"briefSummary": "Recorded study summary."},
    }}]}

    def handler(request):
        if "esearch" in request.url.path:
            return httpx.Response(200, json={"esearchresult": {"idlist": ["123456"]}}, request=request)
        if "efetch" in request.url.path:
            return httpx.Response(200, text=pubmed_xml, request=request)
        return httpx.Response(200, json=trial_json, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pubmed = fetch_corpus.fetch_pubmed(client, "Oncology", "Breast cancer", "clinical trials")
        trial = fetch_corpus.fetch_clinical_trials(client, "Oncology", "Breast cancer", "clinical trials")
    assert pubmed[0]["external_id"] == "PMID:123456"
    assert pubmed[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/123456/"
    assert pubmed[0]["full_text"] == "Verbatim abstract text."
    assert trial[0]["external_id"] == "NCT01234567"
    assert trial[0]["url"] == "https://clinicaltrials.gov/study/NCT01234567"
    assert trial[0]["full_text"] == "Recorded study summary."


def test_fetcher_writes_deterministic_empty_fallback(tmp_path):
    output = tmp_path / "corpus.json"
    fetch_corpus.write_corpus([], output)
    assert output.read_text(encoding="utf-8") == "[]\n"
