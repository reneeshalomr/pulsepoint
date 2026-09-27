import pytest
from sqlmodel import Session, select

from app.models import HCPQuestion, QuestionSignal
from app.services.extraction import match_demo_question, rules_extract, validate_extraction
from app.services.phi import scrub_phi


@pytest.mark.parametrize("text,condition,topic,intent", [
    ("HER2 breast cancer after progression, what's next?", "Breast cancer", "Treatment sequencing", "Evidence review"),
    ("Review CDK4/6 evidence for the next line in breast cancer", "Breast cancer", "Treatment sequencing", "Evidence review"),
    ("Tamoxifen side effect risk in breast cancer", "Breast cancer", "Side-effect management", "Safety concern"),
    ("Lung cancer clinical trial enrolling with NCT identifier", "Lung cancer", "Clinical trials", "Evidence review"),
    ("NSCLC EGFR drug interaction monitoring", "Lung cancer", "Drug interactions", "Evidence review"),
    ("HFrEF and ejection fraction monitoring with SGLT2", "Heart failure", "Monitoring", "Evidence review"),
    ("AFib: compare DOAC anticoagulation safety and drug interactions", "Atrial fibrillation", "Drug interactions", "Safety concern"),
    ("A1c metformin type 2 diabetes prior auth coverage", "Type 2 diabetes", "Access/coverage", "Access question"),
    ("GLP-1 guideline update for type 2 diabetes", "Type 2 diabetes", "Guideline update", "Clinical update"),
    ("Obesity weight management follow-up monitoring evidence", "Obesity", "Monitoring", "Evidence review"),
])
def test_rules_extractor_recognizes_taxonomy_phrasings(text, condition, topic, intent):
    result = rules_extract(text)
    assert result["condition"] == condition
    assert result["topic"] == topic
    assert result["intent"] == intent


def test_llm_taxonomy_validation_rejects_bad_values():
    payload = {"specialty": "Oncology", "condition": "Made-up cancer", "topic": "Monitoring",
               "intent": "Evidence review", "question": "Review this?", "key_context": [], "confidence": .8}
    assert validate_extraction(payload) is None
    payload["condition"] = "Breast cancer"
    payload["specialty"] = "Cardiology"
    assert validate_extraction(payload) is None


@pytest.mark.parametrize("text", [
    "Call patient at 404-555-1212", "Email patient@example.org", "MRN: 12345678",
    "DOB: 01/02/1980", "SSN 123-45-6789",
])
def test_phi_scrubber_redacts_identifiers(text):
    cleaned, detected = scrub_phi(text)
    assert detected
    assert "[REDACTED]" in cleaned
    assert cleaned != text


def test_phi_scrubber_redacts_honorific_name():
    cleaned, detected = scrub_phi("Patient Mr. Sampleperson has a question")
    assert detected
    assert "Sampleperson" not in cleaned


def test_demo_cache_hits_golden_question():
    entry = {"text": "A question about breast cancer treatment sequencing recently?", "structure": {
        "specialty": "Oncology", "condition": "Breast cancer", "topic": "Treatment sequencing",
        "intent": "Clinical update", "question": "What changed recently?", "key_context": ["synthetic case"],
        "confidence": 1.0}}
    result = match_demo_question("A question about breast cancer treatment sequencing recently!", [entry])
    assert result is not None
    assert result["extraction_method"] == "demo_cache"
    assert result["condition"] == "Breast cancer"


def test_post_get_question_scrubs_and_creates_category_only_signal(client, test_engine):
    response = client.post("/api/questions", json={"text": "Patient Mr. Sampleperson asks about HER2 breast cancer and next line treatment."})
    assert response.status_code == 201
    created = response.json()
    assert created["phi_detected"] is True
    assert created["condition"] == "Breast cancer"
    assert created["extraction_method"] == "rules"
    assert client.get(f"/api/questions/{created['question_id']}").json() == created
    with Session(test_engine) as session:
        question = session.get(HCPQuestion, created["question_id"])
        signal = session.exec(select(QuestionSignal)).one()
        assert "Sampleperson" not in question.raw_text
        assert signal.answered is False
        assert signal.is_seeded is False
        assert not hasattr(signal, "text")


@pytest.mark.parametrize("text", ["", "   ", "x" * 2001])
def test_post_rejects_empty_or_overlong_question(client, text):
    response = client.post("/api/questions", json={"text": text})
    assert response.status_code == 422


def test_get_missing_question_returns_specified_404(client):
    response = client.get("/api/questions/missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Question not found"}
