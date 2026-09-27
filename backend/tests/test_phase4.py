import json
from collections import Counter
from pathlib import Path

from app.models import Expert, HCPQuestion
from app.services.matching import DISCLAIMER, SCORE_NOTE, rank_experts


def test_expert_seed_data_has_12_clearly_synthetic_profiles():
    profiles = json.loads((Path(__file__).resolve().parents[2] / "data" / "experts.json").read_text(encoding="utf-8"))
    assert len(profiles) == 12
    assert Counter(profile["specialty"] for profile in profiles) == {
        "Oncology": 4, "Cardiology": 4, "Endocrinology": 4,
    }
    assert all(profile["bio"].startswith("Synthetic demonstration profile") for profile in profiles)
    assert all("Fictional Demo Profile" in profile["title"] for profile in profiles)
    assert all(set(("conditions", "topics", "expertise", "availability")) <= profile.keys() for profile in profiles)


def test_list_experts_seeds_profiles_and_includes_disclaimer(client):
    response = client.get("/api/experts")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["experts"]) == 12
    assert payload["disclaimer"] == DISCLAIMER
    assert all(expert["is_demo"] is True for expert in payload["experts"])
    assert client.get("/api/experts").json() == payload


def test_expert_detail_includes_demo_disclaimer(client):
    expert = client.get("/api/experts").json()["experts"][0]
    response = client.get(f"/api/experts/{expert['id']}")
    assert response.status_code == 200
    assert response.json()["expert"]["is_demo"] is True
    assert response.json()["disclaimer"] == DISCLAIMER
    assert client.get("/api/experts/missing").status_code == 404


def test_golden_path_oncology_question_matches_maya_patel_first(client):
    question_text = "I have a patient with a complicated treatment history. What's changed recently in the relevant treatment landscape, and what evidence should I review?"
    question_response = client.post("/api/questions", json={"text": question_text})
    assert question_response.status_code == 201
    result = client.get(f"/api/experts/match/{question_response.json()['question_id']}")
    assert result.status_code == 200
    payload = result.json()
    assert payload["experts"][0]["name"] == "Dr. Maya Patel"
    assert payload["experts"][0]["is_demo"] is True
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["score_note"] == SCORE_NOTE
    for expert in payload["experts"]:
        assert expert["match_score"] == sum(expert["score_breakdown"].values())


def test_match_missing_question_returns_404(client):
    response = client.get("/api/experts/match/unknown-question")
    assert response.status_code == 404
    assert response.json() == {"detail": "Question not found"}


def test_available_expert_wins_availability_tie_deterministically():
    question = HCPQuestion(raw_text="synthetic text", question="Heart failure monitoring",
                           specialty="Cardiology", condition="Heart failure", topic="Monitoring",
                           intent="Evidence review", key_context=[], extraction_method="rules", confidence=.72)
    available = Expert(id="expert-b", name="Synthetic available", title="Cardiology Specialist (Fictional Demo Profile)",
                       specialty="Cardiology", conditions=["Heart failure"], topics=["Monitoring"],
                       expertise=["Heart failure", "Monitoring"], availability="available",
                       bio="Synthetic demo profile only.", is_demo=True)
    offline = Expert(id="expert-a", name="Synthetic offline", title="Cardiology Specialist (Fictional Demo Profile)",
                     specialty="Cardiology", conditions=["Heart failure"], topics=["Monitoring"],
                     expertise=["Heart failure", "Monitoring"], availability="offline",
                     bio="Synthetic demo profile only.", is_demo=True)
    ranked = rank_experts(question, [offline, available])
    assert ranked[0]["availability"] == "available"
    assert ranked[0]["match_score"] > ranked[1]["match_score"]


def test_seed_helper_can_be_called_more_than_once(client, test_engine):
    # The endpoint performs the same idempotent seeding helper on each call.
    client.get("/api/experts")
    client.get("/api/experts")
    assert len(client.get("/api/experts").json()["experts"]) == 12
