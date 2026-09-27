import pytest
from sqlmodel import Session, select

from app.models import ExpertResponse, Huddle, QuestionSignal
from app.routers.audio import AUDIO_DIR
from app.services.matching import DISCLAIMER

GOLDEN_QUESTION = "I have a patient with a complicated treatment history. What's changed recently in the relevant treatment landscape, and what evidence should I review?"


def create_question(client, text=GOLDEN_QUESTION):
    response = client.post("/api/questions", json={"text": text})
    assert response.status_code == 201
    return response.json()


def create_huddle(client, test_engine, question=None, expert_id="demo-onc-001", evidence_ids=None):
    question = question or create_question(client)
    payload = {"question_id": question["question_id"], "expert_id": expert_id}
    if evidence_ids is not None:
        payload["evidence_ids"] = evidence_ids
    response = client.post("/api/huddles", json=payload)
    return question, response


def test_create_huddle_autofills_evidence_and_returns_full_detail(client, test_engine):
    question, response = create_huddle(client, test_engine)
    assert response.status_code == 201
    payload = response.json()
    assert payload["huddle"]["status"] == "awaiting_expert"
    assert payload["huddle"]["question_id"] == question["question_id"]
    assert payload["huddle"]["evidence_ids"]
    assert payload["expert"]["is_demo"] is True
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["question"]["id"] == question["question_id"]
    detail = client.get(f"/api/huddles/{payload['huddle']['id']}")
    assert detail.status_code == 200
    assert detail.json()["huddle"] == payload["huddle"]
    assert detail.json()["evidence"]


def test_create_huddle_validates_question_expert_and_evidence(client):
    assert client.post("/api/huddles", json={"question_id": "missing", "expert_id": "demo-onc-001"}).status_code == 404
    question = create_question(client)
    assert client.post("/api/huddles", json={"question_id": question["question_id"], "expert_id": "missing"}).status_code == 404
    missing_evidence = client.post("/api/huddles", json={
        "question_id": question["question_id"], "expert_id": "demo-onc-001", "evidence_ids": ["not-a-source"]})
    assert missing_evidence.status_code == 404
    assert missing_evidence.json() == {"detail": "Evidence source not found", "code": "http_404"}


def test_huddle_inbox_filters_by_expert_and_status(client):
    _, created = create_huddle(client, None)
    huddle_id = created.json()["huddle"]["id"]
    response = client.get("/api/huddles", params={"expert_id": "demo-onc-001", "status": "awaiting_expert"})
    assert response.status_code == 200
    assert [item["huddle"]["id"] for item in response.json()["huddles"]] == [huddle_id]
    assert response.json()["disclaimer"] == DISCLAIMER
    assert client.get("/api/huddles", params={"status": "bogus"}).status_code == 422


def test_manual_text_response_updates_state_and_answer_signal(client, test_engine):
    question, created = create_huddle(client, test_engine)
    huddle_id = created.json()["huddle"]["id"]
    response = client.post(f"/api/huddles/{huddle_id}/response", json={
        "expert_id": "demo-onc-001", "mode": "text", "text": "Synthetic demo response for review."})
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "responded"
    assert payload["response"]["is_simulated"] is False
    assert payload["expert_disclaimer"] == DISCLAIMER
    with Session(test_engine) as session:
        huddle = session.get(Huddle, huddle_id)
        assert huddle.status == "responded"
        signal = session.exec(select(QuestionSignal).where(QuestionSignal.specialty == "Oncology")).one()
        assert signal.answered is True
        assert session.exec(select(ExpertResponse).where(ExpertResponse.huddle_id == huddle_id)).one().text == "Synthetic demo response for review."
    assert client.get(f"/api/huddles/{huddle_id}").json()["question"]["id"] == question["question_id"]
    assert client.post(f"/api/huddles/{huddle_id}/response", json={
        "expert_id": "demo-onc-001", "mode": "text", "text": "A second response."}).status_code == 409


def test_response_rejects_wrong_expert_or_invalid_payload(client):
    _, created = create_huddle(client, None)
    huddle_id = created.json()["huddle"]["id"]
    wrong_expert = client.post(f"/api/huddles/{huddle_id}/response", json={
        "expert_id": "demo-card-001", "mode": "text", "text": "Synthetic response."})
    assert wrong_expert.status_code == 422
    assert client.post(f"/api/huddles/{huddle_id}/response", json={
        "expert_id": "demo-onc-001", "mode": "unknown", "text": "Synthetic response."}).status_code == 422
    assert client.post(f"/api/huddles/{huddle_id}/response", json={
        "expert_id": "demo-onc-001", "mode": "text", "text": "   "}).status_code == 422
    assert client.get(f"/api/huddles/{huddle_id}").json()["huddle"]["status"] == "awaiting_expert"


def test_voice_response_stores_transcript_and_audio_metadata(client, test_engine):
    _, created = create_huddle(client, test_engine)
    huddle_id = created.json()["huddle"]["id"]
    response = client.post(f"/api/huddles/{huddle_id}/response", json={
        "expert_id": "demo-onc-001", "mode": "voice", "text": "Voice response metadata.",
        "transcript": "Synthetic transcript text.", "audio_url": "/static/audio/demo.wav", "duration_seconds": 4.2})
    assert response.status_code == 201
    stored = response.json()["response"]
    assert stored["mode"] == "voice"
    assert stored["transcript"] == "Synthetic transcript text."
    assert stored["audio_url"] == "/static/audio/demo.wav"
    assert stored["duration_seconds"] == 4.2


def test_simulated_response_is_labeled_and_references_only_attached_sources(client):
    _, created = create_huddle(client, None)
    huddle = created.json()["huddle"]
    response = client.post(f"/api/huddles/{huddle['id']}/simulate-response")
    assert response.status_code == 201
    simulated = response.json()["response"]
    assert simulated["is_simulated"] is True
    assert "fictional demo profile" in simulated["text"]
    assert "makes no clinical claims" in simulated["text"]
    for source_id in huddle["evidence_ids"]:
        assert f"[{source_id}]" in simulated["text"]
    assert client.get(f"/api/huddles/{huddle['id']}").json()["huddle"]["status"] == "responded"


def test_non_golden_simulated_response_is_neutral(client):
    question = create_question(client, "Please review HER2 breast cancer trial evidence.")
    _, created = create_huddle(client, None, question=question)
    huddle_id = created.json()["huddle"]["id"]
    response = client.post(f"/api/huddles/{huddle_id}/simulate-response")
    assert response.status_code == 201
    assert response.json()["response"]["is_simulated"] is True
    assert "adds no clinical evidence" in response.json()["response"]["text"]


def test_huddle_and_response_missing_ids_return_404(client):
    assert client.get("/api/huddles/missing").status_code == 404
    assert client.post("/api/huddles/missing/response", json={
        "expert_id": "demo-onc-001", "mode": "text", "text": "Synthetic response."}).status_code == 404
    assert client.post("/api/huddles/missing/simulate-response").status_code == 404


def test_audio_upload_stores_supported_file_and_serves_url(client):
    response = client.post("/api/audio", files={"file": ("demo.wav", b"RIFFsynthetic-demo-audio", "audio/wav")})
    assert response.status_code == 200
    result = response.json()
    assert result["audio_url"].startswith("/static/audio/")
    assert result["content_type"] == "audio/wav"
    assert result["size_bytes"] == len(b"RIFFsynthetic-demo-audio")
    filename = result["audio_url"].rsplit("/", 1)[-1]
    try:
        served = client.get(result["audio_url"])
        assert served.status_code == 200
        assert served.content == b"RIFFsynthetic-demo-audio"
    finally:
        (AUDIO_DIR / filename).unlink(missing_ok=True)


@pytest.mark.parametrize("filename,content_type", [
    ("clip.exe", "application/octet-stream"),
    ("clip.wav", "audio/mpeg"),
])
def test_audio_upload_rejects_unsupported_type_or_mime(client, filename, content_type):
    response = client.post("/api/audio", files={"file": (filename, b"audio", content_type)})
    assert response.status_code == 415


def test_audio_upload_rejects_empty_and_oversized_files(client):
    empty = client.post("/api/audio", files={"file": ("empty.wav", b"", "audio/wav")})
    assert empty.status_code == 422
    oversized = client.post("/api/audio", files={"file": ("large.wav", b"0" * (10 * 1024 * 1024 + 1), "audio/wav")})
    assert oversized.status_code == 413
