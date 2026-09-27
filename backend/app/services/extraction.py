"""Question cache, taxonomy validation, and deterministic keyword fallback."""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from app.services.llm import extract_with_llm
from app.taxonomy import (
    CONDITIONS_BY_SPECIALTY, CONDITIONS_WITH_OTHER, INTENTS_WITH_OTHER, KEYWORDS,
    OTHER, SPECIALTIES_WITH_OTHER, TOPICS_WITH_OTHER,
)

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "demo_questions.json"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_question(text: str) -> str:
    text = _clean_text(text)
    if not text.endswith((".", "?", "!")):
        text += "?"
    return text


def validate_extraction(payload: dict) -> dict | None:
    """Validate every extracted field; malformed/unknown categories fail closed."""
    required = {"specialty", "condition", "topic", "intent", "question", "key_context", "confidence"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        return None
    if payload["specialty"] not in SPECIALTIES_WITH_OTHER:
        return None
    if payload["condition"] not in CONDITIONS_WITH_OTHER:
        return None
    if payload["topic"] not in TOPICS_WITH_OTHER or payload["intent"] not in INTENTS_WITH_OTHER:
        return None
    if not isinstance(payload["question"], str) or not payload["question"].strip():
        return None
    if not isinstance(payload["key_context"], list) or not all(isinstance(item, str) for item in payload["key_context"]):
        return None
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        return None
    if not 0 <= confidence <= 1:
        return None
    if payload["condition"] != OTHER:
        inferred = next((specialty for specialty, conditions in CONDITIONS_BY_SPECIALTY.items()
                         if payload["condition"] in conditions), None)
        if inferred != payload["specialty"]:
            return None
    return {**payload, "question": _normalize_question(payload["question"]), "confidence": confidence,
            "key_context": [_clean_text(item) for item in payload["key_context"] if item.strip()]}


def _load_demo_questions() -> list[dict]:
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def match_demo_question(text: str, entries: list[dict] | None = None) -> dict | None:
    candidate = _clean_text(text).casefold()
    best: tuple[float, dict] | None = None
    for entry in entries if entries is not None else _load_demo_questions():
        source = entry.get("text", "")
        normalized_source = _clean_text(source).casefold()
        ratio = SequenceMatcher(None, candidate, normalized_source).ratio()
        # Exact and small punctuation/spacing variations qualify; avoid matching
        # generic short fragments to the golden path examples.
        if candidate == normalized_source:
            ratio = 1.0
        if ratio >= 0.86 and (best is None or ratio > best[0]):
            best = (ratio, entry)
    if best is None:
        return None
    validated = validate_extraction(best[1].get("structure", {}))
    if validated is None:
        return None
    return {**validated, "extraction_method": "demo_cache", "confidence": 1.0}


def _best_value(text: str, category: str, allowed: list[str]) -> str:
    folded = text.casefold()
    counts = {value: sum(1 for term in KEYWORDS[category].get(value, []) if term.casefold() in folded)
              for value in allowed if value != OTHER}
    specificity = {value: max((len(term) for term in KEYWORDS[category].get(value, [])
                               if term.casefold() in folded), default=0) for value in counts}
    # More matching terms wins; longer, more specific phrases break ties.
    winner = max(counts, key=lambda value: (counts[value], specificity[value])) if counts else OTHER
    return winner if counts.get(winner, 0) else OTHER


def rules_extract(text: str) -> dict:
    condition = _best_value(text, "conditions", CONDITIONS_WITH_OTHER)
    specialty = next((specialty for specialty, conditions in CONDITIONS_BY_SPECIALTY.items()
                      if condition in conditions), OTHER)
    if specialty == OTHER:
        specialty = _best_value(text, "specialties", SPECIALTIES_WITH_OTHER)
    topic = _best_value(text, "topics", TOPICS_WITH_OTHER)
    intent = _best_value(text, "intents", INTENTS_WITH_OTHER)
    if intent == OTHER:
        intent = "Evidence review"
    return {"specialty": specialty, "condition": condition, "topic": topic, "intent": intent,
            "question": _normalize_question(text), "key_context": [], "confidence": 0.72,
            "extraction_method": "rules"}


def extract_question(text: str) -> dict:
    cached = match_demo_question(text)
    if cached:
        return cached
    llm_payload = extract_with_llm(text)
    validated = validate_extraction(llm_payload) if llm_payload else None
    if validated:
        return {**validated, "extraction_method": "llm"}
    return rules_extract(text)
