from datetime import datetime, timedelta, timezone
import json
from sqlmodel import Session

from app.models import QuestionSignal
from scripts.seed import make_demo_signals


def test_demo_signal_generator_is_seeded_anonymous_and_skewed():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    first = make_demo_signals(now)
    second = make_demo_signals(now)
    assert first == second
    assert len(first) == 80
    assert all(set(item) == {"id", "specialty", "condition", "topic", "intent", "answered", "is_seeded", "timestamp"}
               for item in first)
    assert all(item["is_seeded"] for item in first)
    grouped = {}
    for item in first:
        if item["condition"] == "Breast cancer" and item["topic"] == "Treatment sequencing":
            grouped[(item["condition"], item["topic"])] = grouped.get((item["condition"], item["topic"]), 0) + 1
    assert grouped["Breast cancer", "Treatment sequencing"] > 0


def test_question_graph_includes_seeded_and_live_signals_without_identity(client, test_engine):
    seeded_response = client.get("/api/analytics/questions")
    assert seeded_response.status_code == 200
    seeded = seeded_response.json()
    assert seeded["total"] == 80
    assert seeded["includes_seeded_data"] is True
    assert seeded["by_condition"][0]["name"] == "Breast cancer"
    assert seeded["by_topic"][0]["name"] == "Treatment sequencing"
    assert len(seeded["timeseries"]) == 30
    assert all(set(row) == {"date", "count"} for row in seeded["timeseries"])
    assert all(row["count"] >= 0 for row in seeded["timeseries"])

    response = client.post("/api/questions", json={"text": "What evidence should I review about breast cancer treatment sequencing?"})
    assert response.status_code == 201
    after = client.get("/api/analytics/questions?specialty=Oncology").json()
    assert after["total"] > sum(row["count"] for row in seeded["by_specialty"] if row["name"] == "Oncology")
    assert all("id" not in row for collection in after.values() if isinstance(collection, list)
               for row in collection)
    serialized = json.dumps(after).casefold()
    assert "what evidence should i review" not in serialized
    assert '"raw_text"' not in serialized
    assert client.get("/api/analytics/questions?days=0").status_code == 422


def test_question_graph_uses_date_window_and_sorted_counts(client, test_engine):
    client.get("/api/analytics/questions")  # Seed the isolated test DB.
    now = datetime.now(timezone.utc)
    with Session(test_engine) as session:
        session.add(QuestionSignal(specialty="Oncology", condition="Breast cancer", topic="Clinical trials",
                                   intent="Evidence review", answered=False, timestamp=now))
        session.add(QuestionSignal(specialty="Oncology", condition="Breast cancer", topic="Clinical trials",
                                   intent="Evidence review", answered=False, timestamp=now - timedelta(days=40)))
        session.commit()
    result = client.get("/api/analytics/questions?days=7&specialty=Oncology").json()
    assert result["total"] == sum(item["count"] for item in result["by_topic"])
    assert [item["count"] for item in result["by_topic"]] == sorted(
        [item["count"] for item in result["by_topic"]], reverse=True)
    assert all(item["condition"] and item["topic"] and item["count"] > 0 for item in result["unanswered"])
