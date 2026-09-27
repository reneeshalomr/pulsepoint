from sqlmodel import SQLModel

from app.db import init_db
from app.models import EvidenceChunk, EvidenceSource, Expert, ExpertResponse, HCPQuestion, Huddle, QuestionSignal


def test_health_returns_expected_fields(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["db"] == "ok"
    assert payload["llm_provider"] == "none"
    assert payload["corpus_size"] == 0
    assert payload["experts_count"] == 0


def test_init_db_creates_all_phase_one_tables(test_engine):
    init_db(test_engine)
    expected = {"hcpquestion", "evidencesource", "evidencechunk", "expert", "huddle", "expertresponse", "questionsignal"}
    assert expected <= set(SQLModel.metadata.tables)
