"""Demo expert seeding and transparent deterministic routing scores."""

import json
import re
from pathlib import Path

from sqlmodel import Session, select

from app.models import Expert, HCPQuestion

EXPERTS_PATH = Path(__file__).resolve().parents[3] / "data" / "experts.json"
DISCLAIMER = "Demo profile — fictional expert for prototype purposes."
SCORE_NOTE = "Routing relevance score, not a measure of clinical expertise or correctness."
AVAILABILITY_POINTS = {"available": 10, "busy": 4, "offline": 0}
AVAILABILITY_ORDER = {"available": 0, "busy": 1, "offline": 2}
STOPWORDS = set("a an and are as at be by for from has have how in is it of on or that the this to was were what when where which with should".split())


def load_expert_profiles() -> list[dict]:
    try:
        payload = json.loads(EXPERTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [profile for profile in payload if isinstance(profile, dict)]


def ensure_demo_experts(session: Session) -> None:
    """Insert missing synthetic profiles with stable ids; safe to call repeatedly."""
    for profile in load_expert_profiles():
        if session.get(Expert, profile["id"]) is None:
            session.add(Expert(**profile, is_demo=True))
    session.commit()


def _tokens(values: list[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(token for token in re.findall(r"[a-z0-9]+(?:[+/.-][a-z0-9]+)*", value.casefold())
                      if token not in STOPWORDS)
    return result


def _expertise_overlap(question: HCPQuestion, expert: Expert) -> int:
    query_tags = [question.question, question.specialty, question.condition, question.topic, *question.key_context]
    query_terms = _tokens(query_tags)
    expert_terms = _tokens(expert.expertise)
    union = query_terms | expert_terms
    if not union:
        return 0
    return round(10 * len(query_terms & expert_terms) / len(union))


def score_expert(question: HCPQuestion, expert: Expert) -> dict:
    breakdown = {
        "specialty": 35 if expert.specialty == question.specialty else 0,
        "condition": 25 if question.condition in expert.conditions else 0,
        "topic": 20 if question.topic in expert.topics else 0,
        "expertise": _expertise_overlap(question, expert),
        "availability": AVAILABILITY_POINTS.get(expert.availability, 0),
    }
    score = sum(breakdown.values())
    return {
        "id": expert.id,
        "name": expert.name,
        "title": expert.title,
        "specialty": expert.specialty,
        "expertise": expert.expertise,
        "match_score": score,
        "availability": expert.availability,
        "score_breakdown": breakdown,
        "is_demo": True,
    }


def rank_experts(question: HCPQuestion, experts: list[Expert], limit: int = 3) -> list[dict]:
    ranked = [score_expert(question, expert) for expert in experts]
    ranked.sort(key=lambda item: (-item["match_score"], AVAILABILITY_ORDER.get(item["availability"], 99), item["id"]))
    return ranked[:limit]


def match_question(session: Session, question_id: str) -> list[dict]:
    question = session.get(HCPQuestion, question_id)
    if question is None:
        raise LookupError("Question not found")
    ensure_demo_experts(session)
    experts = session.exec(select(Expert)).all()
    return rank_experts(question, experts, limit=3)
