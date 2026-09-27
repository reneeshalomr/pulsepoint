"""Call the API against a temporary SQLite DB and refresh frontend JSON examples."""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.audio import AUDIO_DIR  # noqa: E402
from app.services.retrieval import load_corpus  # noqa: E402


def main() -> None:
    fixture_dir = ROOT / "data" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    db_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(db_engine)

    def override_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    examples = {}
    with TestClient(app) as client:
        examples["health"] = client.get("/api/health").json()
        examples["demo_golden_path"] = client.get("/api/demo/golden-path").json()

        example_text = examples["demo_golden_path"]["questions"][0]["text"]
        question = client.post("/api/questions", json={"text": example_text}).json()
        question_id = question["question_id"]
        examples["questions_create"] = question
        examples["questions_get"] = client.get(f"/api/questions/{question_id}").json()
        examples["evidence_for_question"] = client.get(f"/api/evidence/{question_id}").json()
        examples["evidence_search"] = client.get("/api/evidence/search", params={"q": "breast cancer"}).json()

        corpus = load_corpus()
        if corpus:
            examples["evidence_import"] = client.post("/api/evidence", json={
                "external_id": corpus[0]["external_id"]}).json()
        examples["experts_list"] = client.get("/api/experts").json()
        match = client.get(f"/api/experts/match/{question_id}").json()
        examples["experts_match"] = match
        expert_id = match["experts"][0]["id"]
        examples["experts_get"] = client.get(f"/api/experts/{expert_id}").json()

        evidence_ids = [source["id"] for source in examples["evidence_for_question"]["sources"]]
        huddle = client.post("/api/huddles", json={"question_id": question_id,
            "expert_id": expert_id, "evidence_ids": evidence_ids}).json()
        huddle_id = huddle["huddle"]["id"]
        examples["huddles_create"] = huddle
        examples["huddles_get"] = client.get(f"/api/huddles/{huddle_id}").json()
        examples["huddles_list"] = client.get("/api/huddles", params={"expert_id": expert_id}).json()
        examples["huddle_synthesis_input"] = client.get(f"/api/huddles/{huddle_id}/synthesis-input").json()
        examples["expert_response"] = client.post(f"/api/huddles/{huddle_id}/response", json={
            "expert_id": expert_id, "mode": "text", "text": "Synthetic fixture response from a fictional demo profile."}).json()
        synthesis = client.post(f"/api/huddles/{huddle_id}/synthesize")
        examples["huddle_synthesize"] = synthesis.json()
        examples["huddle_brief"] = client.put(f"/api/huddles/{huddle_id}/brief",
                                               json=synthesis.json()["brief"]).json()

        second_huddle = client.post("/api/huddles", json={"question_id": question_id,
            "expert_id": expert_id, "evidence_ids": evidence_ids}).json()["huddle"]["id"]
        examples["simulate_response"] = client.post(f"/api/huddles/{second_huddle}/simulate-response").json()
        examples["analytics_questions"] = client.get("/api/analytics/questions").json()

        audio = client.post("/api/audio", files={"file": ("fixture.wav", b"RIFFfixture-audio", "audio/wav")})
        examples["audio_upload"] = audio.json()
        audio_path = examples["audio_upload"]["audio_url"]
        try:
            served = client.get(audio_path)
            examples["audio_serve"] = {"status_code": served.status_code,
                                        "content_type": served.headers.get("content-type"),
                                        "size_bytes": len(served.content)}
        finally:
            (AUDIO_DIR / audio_path.rsplit("/", 1)[-1]).unlink(missing_ok=True)
        examples["demo_reset"] = client.post("/api/demo/reset").json()

    app.dependency_overrides.clear()
    for name, example in examples.items():
        (fixture_dir / f"{name}.json").write_text(json.dumps(example, indent=2) + "\n", encoding="utf-8")
    SQLModel.metadata.drop_all(db_engine)
    db_engine.dispose()
    print(f"Wrote {len(examples)} API response fixtures to {fixture_dir}")


if __name__ == "__main__":
    main()
