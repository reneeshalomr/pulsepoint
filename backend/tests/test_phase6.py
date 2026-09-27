import re

from app.services import synthesis
from app.services.synthesis import BRIEF_DISCLAIMER
from app.models import Huddle
from sqlmodel import Session

GOLDEN_QUESTION = "I have a patient with a complicated treatment history. What's changed recently in the relevant treatment landscape, and what evidence should I review?"


def create_question(client):
    response = client.post("/api/questions", json={"text": GOLDEN_QUESTION})
    assert response.status_code == 201
    return response.json()


def create_huddle(client, question):
    response = client.post("/api/huddles", json={"question_id": question["question_id"], "expert_id": "demo-onc-001"})
    assert response.status_code == 201
    return response


def create_responded_huddle(client, test_engine):
    question = create_question(client)
    created = create_huddle(client, question)
    huddle_id = created.json()["huddle"]["id"]
    response = client.post(f"/api/huddles/{huddle_id}/simulate-response")
    assert response.status_code == 201
    return question, huddle_id, response.json()["response"]


def test_synthesis_input_has_clean_context_and_verbatim_attached_evidence(client, test_engine):
    _, huddle_id, _ = create_responded_huddle(client, test_engine)
    result = client.get(f"/api/huddles/{huddle_id}/synthesis-input")
    assert result.status_code == 200
    payload = result.json()
    assert payload["question"]["question_id"]
    assert "raw_text" not in payload["question"]
    assert payload["evidence"]
    assert payload["expert_responses"][0]["is_simulated"] is True
    assert payload["safety_rules"]
    for source in payload["evidence"]:
        assert source["id"]
        assert source["snippet"]
        assert "citation" in source


def test_synthesis_requires_expert_response_and_unknown_huddle_is_404(client, test_engine):
    question = create_question(client)
    created = create_huddle(client, question)
    huddle_id = created.json()["huddle"]["id"]
    response = client.post(f"/api/huddles/{huddle_id}/synthesize")
    assert response.status_code == 409
    assert client.get("/api/huddles/unknown/synthesis-input").status_code == 404
    assert client.post("/api/huddles/unknown/synthesize").status_code == 404
    _, responded_huddle_id, _ = create_responded_huddle(client, test_engine)
    valid_brief = client.post(f"/api/huddles/{responded_huddle_id}/synthesize").json()["brief"]
    assert client.put("/api/huddles/unknown/brief", json=valid_brief).status_code == 404


def test_synthesis_rejects_responded_status_without_a_stored_response(client, test_engine):
    question = create_question(client)
    created = create_huddle(client, question)
    huddle_id = created.json()["huddle"]["id"]
    with Session(test_engine) as session:
        huddle = session.get(Huddle, huddle_id)
        huddle.status = "responded"
        session.add(huddle)
        session.commit()
    result = client.post(f"/api/huddles/{huddle_id}/synthesize")
    assert result.status_code == 409


def test_none_provider_generates_verbatim_template_with_required_sections(client, test_engine):
    _, huddle_id, response = create_responded_huddle(client, test_engine)
    input_payload = client.get(f"/api/huddles/{huddle_id}/synthesis-input").json()
    result = client.post(f"/api/huddles/{huddle_id}/synthesize")
    assert result.status_code == 200
    payload = result.json()
    brief = payload["brief"]
    assert payload["status"] == "synthesized"
    assert brief["generated_by"] == "template"
    assert brief["question"] == input_payload["question"]["question"]
    assert brief["evidence"]
    assert brief["evidence"][0]["label"] == "EVIDENCE"
    for evidence in brief["evidence"]:
        source_id = evidence["source_ids"][0]
        source = next(source for source in input_payload["evidence"] if source["id"] == source_id)
        sentence = re.split(r"(?<=[.!?])\s+", source["snippet"].strip(), maxsplit=1)[0]
        assert evidence["statement"] == f'"{sentence}" [{source_id}]'
    assert brief["expert_perspective"]["label"] == "EXPERT OPINION"
    assert brief["expert_perspective"]["summary"] == response["text"]
    assert brief["expert_perspective"]["is_simulated"] is True
    assert brief["key_takeaways"][0]["label"] == "AI SYNTHESIS"
    assert "clinical conclusions" in brief["key_takeaways"][0]["point"]
    assert brief["uncertainty"]
    assert brief["sources"]
    assert brief["disclaimer"] == BRIEF_DISCLAIMER
    assert client.get(f"/api/huddles/{huddle_id}").json()["huddle"]["status"] == "synthesized"
    # Repeat requests return the stored result rather than regenerating a new brief.
    assert client.post(f"/api/huddles/{huddle_id}/synthesize").json() == payload


def test_unknown_llm_citation_or_claim_is_discarded_for_template_fallback(client, test_engine, monkeypatch):
    _, huddle_id, _ = create_responded_huddle(client, test_engine)
    monkeypatch.setattr(synthesis, "synthesize_with_llm", lambda _: {
        "evidence": [{"statement": "This treatment cures cancer.", "source_ids": ["PMID:INVENTED"], "label": "EVIDENCE"}],
        "expert_summary": "Invented expert summary.",
        "key_takeaways": [{"point": "A made-up clinical conclusion.", "source_ids": [], "label": "AI SYNTHESIS"}],
        "uncertainty": [],
    })
    response = client.post(f"/api/huddles/{huddle_id}/synthesize")
    assert response.status_code == 200
    assert response.json()["brief"]["generated_by"] == "template"
    assert "cures cancer" not in str(response.json()["brief"])


def test_grounded_llm_draft_can_be_used_with_source_ids_added_by_backend(client, test_engine, monkeypatch):
    _, huddle_id, _ = create_responded_huddle(client, test_engine)
    payload = client.get(f"/api/huddles/{huddle_id}/synthesis-input").json()
    item = payload["evidence"][0]
    expert_response = payload["expert_responses"][0]["text"]
    draft = {
        "evidence": [{"statement": item["snippet"], "source_ids": [item["id"]], "label": "EVIDENCE"}],
        "expert_summary": expert_response,
        "key_takeaways": [{"point": item["snippet"], "source_ids": [item["id"]], "label": "AI SYNTHESIS"}],
        "uncertainty": [],
    }
    monkeypatch.setattr(synthesis, "synthesize_with_llm", lambda _: draft)
    response = client.post(f"/api/huddles/{huddle_id}/synthesize")
    assert response.status_code == 200
    brief = response.json()["brief"]
    assert brief["generated_by"] == "llm"
    assert f'[{item["id"]}]' in brief["evidence"][0]["statement"]
    assert brief["sources"][0]["id"] == item["id"]


def test_external_brief_is_validated_and_stored_then_citation_mismatch_rejected(client, test_engine):
    _, huddle_id, _ = create_responded_huddle(client, test_engine)
    generated = client.post(f"/api/huddles/{huddle_id}/synthesize").json()["brief"]
    generated["generated_by"] = "external"
    stored = client.put(f"/api/huddles/{huddle_id}/brief", json=generated)
    assert stored.status_code == 200
    assert stored.json()["brief"]["generated_by"] == "external"

    invalid = dict(generated)
    invalid["evidence"] = [dict(generated["evidence"][0], statement="This unsupported claim changes outcomes [unknown-source]")]
    rejected = client.put(f"/api/huddles/{huddle_id}/brief", json=invalid)
    assert rejected.status_code == 422


def test_external_brief_rejects_altered_citation_metadata_and_empty_uncertainty(client, test_engine):
    _, huddle_id, _ = create_responded_huddle(client, test_engine)
    brief = client.post(f"/api/huddles/{huddle_id}/synthesize").json()["brief"]
    brief["sources"][0]["citation"] = "Invented citation"
    assert client.put(f"/api/huddles/{huddle_id}/brief", json=brief).status_code == 422
    brief = client.post(f"/api/huddles/{huddle_id}/synthesize").json()["brief"]
    brief["uncertainty"] = []
    assert client.put(f"/api/huddles/{huddle_id}/brief", json=brief).status_code == 422
