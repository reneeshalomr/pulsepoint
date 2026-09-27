from app.config import settings


def test_golden_path_returns_three_stable_synthetic_examples(client):
    first = client.get("/api/demo/golden-path")
    second = client.get("/api/demo/golden-path")
    assert first.status_code == 200
    assert first.json() == second.json()
    questions = first.json()["questions"]
    assert len(questions) == 3
    assert {item["specialty"] for item in questions} == {"Oncology", "Cardiology", "Endocrinology"}
    assert all(item["is_synthetic"] for item in questions)


def test_demo_reset_is_disabled_outside_demo_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    response = client.post("/api/demo/reset")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found", "code": "http_404"}


def test_demo_reset_wipes_live_records_and_reseeds(client):
    question = client.post("/api/questions", json={"text": "What evidence should I review about breast cancer?"}).json()
    huddle = client.post("/api/huddles", json={
        "question_id": question["question_id"], "expert_id": "demo-onc-001"}).json()["huddle"]
    assert client.post(f"/api/huddles/{huddle['id']}/simulate-response").status_code == 201

    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    assert response.json() == {"status": "reset", "questions": 0, "huddles": 0, "seeded_signals": 80}
    assert client.get(f"/api/questions/{question['question_id']}").status_code == 404
    assert client.get(f"/api/huddles/{huddle['id']}").status_code == 404
    analytics = client.get("/api/analytics/questions").json()
    assert analytics["total"] == 80
    assert analytics["includes_seeded_data"] is True


def test_validation_error_is_safe_and_has_standard_shape(client):
    response = client.post("/api/questions", json={"text": "patient@example.test " + "x" * 2001})
    assert response.status_code == 422
    assert response.json() == {"detail": "Request validation failed", "code": "validation_error"}
    assert "patient@example.test" not in response.text


def test_offline_golden_path_full_huddle_increases_analytics(client):
    before = client.get("/api/analytics/questions").json()["total"]
    example = client.get("/api/demo/golden-path").json()["questions"][0]
    question_response = client.post("/api/questions", json={"text": example["text"]})
    assert question_response.status_code == 201
    question = question_response.json()
    assert question["extraction_method"] == "demo_cache"

    evidence_response = client.get(f"/api/evidence/{question['question_id']}")
    assert evidence_response.status_code == 200
    assert evidence_response.json()["sources"]
    match_response = client.get(f"/api/experts/match/{question['question_id']}")
    assert match_response.status_code == 200
    assert match_response.json()["experts"][0]["is_demo"] is True

    huddle_response = client.post("/api/huddles", json={
        "question_id": question["question_id"],
        "expert_id": match_response.json()["experts"][0]["id"],
        "evidence_ids": [source["id"] for source in evidence_response.json()["sources"]],
    })
    assert huddle_response.status_code == 201
    huddle = huddle_response.json()["huddle"]
    simulated = client.post(f"/api/huddles/{huddle['id']}/simulate-response")
    assert simulated.status_code == 201
    assert simulated.json()["response"]["is_simulated"] is True
    synthesis = client.post(f"/api/huddles/{huddle['id']}/synthesize")
    assert synthesis.status_code == 200
    assert synthesis.json()["status"] == "synthesized"
    brief = synthesis.json()["brief"]
    assert brief["generated_by"] == "template"
    assert brief["uncertainty"]
    assert all(source["id"] in huddle["evidence_ids"] for source in brief["sources"])
    after = client.get("/api/analytics/questions").json()["total"]
    assert after == before + 1


def test_health_reports_database_and_configured_offline_provider(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["db"] == "ok"
    assert response.json()["llm_provider"] == "none"
