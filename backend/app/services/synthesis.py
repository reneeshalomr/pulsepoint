"""Citation-checked huddle brief generation with a verbatim deterministic fallback."""

import re

from sqlmodel import Session, select

from app.models import Expert, ExpertResponse, HCPQuestion, Huddle
from app.services.matching import DISCLAIMER
from app.schemas import ClinicalHuddleBrief, SynthesisDraft
from app.services.llm import synthesize_with_llm
from app.services.retrieval import all_sources, search_sources, split_chunks

BRIEF_DISCLAIMER = (
    "Prototype decision-support summary. Not medical advice; does not replace clinical judgment. "
    "Expert profiles are fictional demo profiles."
)
UNCERTAINTY_DEFAULTS = [
    "The curated corpus may be incomplete.",
    "This brief reflects only the attached source text and expert response(s); it is not a comprehensive review.",
]
SAFETY_RULES = [
    "Do not diagnose, prescribe, or claim certainty.",
    "Use only the supplied evidence snippets and expert response text.",
    "Keep EVIDENCE, EXPERT OPINION, and AI SYNTHESIS separate.",
    "Evidence snippets are verbatim source text and must not be rewritten.",
    "Every cited source id must belong to the huddle's attached evidence.",
    "Always include an UNCERTAINTY section.",
]
_INLINE_CITATION = re.compile(r"\[([^\[\]]+)\]")


def _identity(source: dict) -> set[str]:
    return {str(value) for value in (source.get("external_id"), source.get("id")) if value}


def synthesis_input(session: Session, huddle: Huddle) -> dict:
    question = session.get(HCPQuestion, huddle.question_id)
    expert = session.get(Expert, huddle.expert_id)
    responses = session.exec(select(ExpertResponse).where(ExpertResponse.huddle_id == huddle.id)
                             .order_by(ExpertResponse.created_at, ExpertResponse.id)).all()
    all_source_rows = all_sources(session)
    source_by_id = {identity: source for source in all_source_rows for identity in _identity(source)}
    best_snippet = {}
    if question:
        retrieved = search_sources(session, question.question, condition=question.condition,
                                   topic=question.topic, specialty=question.specialty, limit=12)
        best_snippet = {str(source["id"]): source["snippet"] for source in retrieved}
    evidence = []
    for source_id in huddle.evidence_ids:
        source = source_by_id.get(str(source_id))
        if not source:
            continue
        snippet = best_snippet.get(str(source_id))
        if snippet is None:
            chunks = split_chunks(source.get("full_text", ""))
            snippet = chunks[0] if chunks else ""
        evidence.append({"id": str(source_id), "title": source.get("title"), "snippet": snippet,
                         "citation": source.get("citation"), "url": source.get("url"),
                         "verified": bool(source.get("verified"))})
    return {
        "huddle_id": huddle.id,
        "question": ({"question_id": question.id, "question": question.question,
                      "specialty": question.specialty, "condition": question.condition,
                      "topic": question.topic, "intent": question.intent,
                      "key_context": question.key_context} if question else None),
        "evidence": evidence,
        "expert": ({"name": expert.name, "title": expert.title, "is_demo": True} if expert else None),
        "expert_responses": [response.model_dump(mode="json") for response in responses],
        "safety_rules": SAFETY_RULES,
        "disclaimer": DISCLAIMER,
    }


def _sources_for_huddle(session: Session, huddle: Huddle) -> dict[str, dict]:
    by_id = {}
    attached = set(huddle.evidence_ids)
    for source in all_sources(session):
        for source_id in _identity(source):
            if source_id in attached:
                by_id[source_id] = source
    return by_id


def _brief_sources(source_by_id: dict[str, dict], evidence_ids: list[str]) -> list[dict]:
    result = []
    for source_id in evidence_ids:
        source = source_by_id.get(str(source_id))
        if source:
            result.append({"id": str(source_id), "citation": source.get("citation") or "",
                           "url": source.get("url"), "verified": bool(source.get("verified"))})
    return result


def _response_context(session: Session, huddle: Huddle) -> tuple[HCPQuestion, Expert, list[ExpertResponse]]:
    question = session.get(HCPQuestion, huddle.question_id)
    expert = session.get(Expert, huddle.expert_id)
    responses = session.exec(select(ExpertResponse).where(ExpertResponse.huddle_id == huddle.id)
                             .order_by(ExpertResponse.created_at, ExpertResponse.id)).all()
    if question is None or expert is None:
        raise ValueError("Huddle is missing its question or expert")
    return question, expert, responses


def _first_sentence(text: str) -> str:
    snippet = text.strip()
    if not snippet:
        return ""
    return re.split(r"(?<=[.!?])\s+", snippet, maxsplit=1)[0]


def _expert_perspective(expert: Expert, responses: list[ExpertResponse]) -> dict:
    # Preserve the expert text exactly; multiple responses remain separate lines.
    summary = "\n".join(response.text for response in responses)
    return {"summary": summary, "expert_name": expert.name,
            "is_simulated": any(response.is_simulated for response in responses),
            "audio_url": next((response.audio_url for response in responses if response.audio_url), None),
            "label": "EXPERT OPINION"}


def template_brief(session: Session, huddle: Huddle) -> dict:
    question, expert, responses = _response_context(session, huddle)
    source_by_id = _sources_for_huddle(session, huddle)
    snippet_by_id = {item["id"]: item["snippet"] for item in synthesis_input(session, huddle)["evidence"]}
    evidence = []
    for source_id in huddle.evidence_ids:
        source = source_by_id.get(str(source_id))
        if not source:
            continue
        sentence = _first_sentence(snippet_by_id.get(str(source_id), source.get("full_text", "")))
        if sentence:
            evidence.append({"statement": f'"{sentence}" [{source_id}]',
                             "source_ids": [str(source_id)], "label": "EVIDENCE"})
    raw = {
        "question": question.question,
        "evidence": evidence,
        "expert_perspective": _expert_perspective(expert, responses),
        "key_takeaways": [{"point": "No independent clinical conclusions are added in this brief.",
                           "source_ids": [], "label": "AI SYNTHESIS"}],
        "uncertainty": UNCERTAINTY_DEFAULTS,
        "sources": _brief_sources(source_by_id, huddle.evidence_ids),
        "generated_by": "template",
        "disclaimer": BRIEF_DISCLAIMER,
    }
    return ClinicalHuddleBrief.model_validate(raw).model_dump(mode="json")


def _clean_cited_text(text: str, known_ids: set[str]) -> str:
    cleaned = _INLINE_CITATION.sub(lambda match: "" if match.group(1) in known_ids else match.group(0), text)
    return cleaned.strip().strip('"“”\' ')


def _citation_ids(text: str) -> set[str]:
    # [SIMULATED] is a source-title marker, not an inline citation.
    return {value for value in _INLINE_CITATION.findall(text) if value != "SIMULATED"}


def _llm_draft_is_grounded(draft_data: dict,
                           evidence_by_id: dict[str, dict], responses: list[ExpertResponse]) -> SynthesisDraft | None:
    try:
        draft = SynthesisDraft.model_validate(draft_data)
    except Exception:
        return None
    response_texts = [response.text for response in responses]
    for item in draft.evidence:
        if not item.source_ids or any(source_id not in evidence_by_id for source_id in item.source_ids):
            return None
        cited = _citation_ids(item.statement)
        if cited and not cited.issubset(set(item.source_ids)):
            return None
        cleaned = _clean_cited_text(item.statement, set(item.source_ids))
        if not cleaned or any(cleaned not in evidence_by_id[source_id]["snippet"] for source_id in item.source_ids):
            return None
    if not draft.expert_summary or not any(draft.expert_summary in text for text in response_texts):
        return None
    attached_ids = set(evidence_by_id)
    for item in draft.key_takeaways:
        if any(source_id not in attached_ids for source_id in item.source_ids):
            return None
        cited = _citation_ids(item.point)
        if not cited.issubset(attached_ids):
            return None
        cleaned = _clean_cited_text(item.point, set(item.source_ids))
        supporting_texts = [evidence_by_id[source_id]["snippet"] for source_id in item.source_ids]
        if not item.source_ids:
            supporting_texts = response_texts + ["No independent clinical conclusions are added in this brief."]
        if not cleaned or not any(cleaned in text for text in supporting_texts):
            return None
    return draft


def llm_brief(session: Session, huddle: Huddle, draft_data: dict) -> dict | None:
    question, expert, responses = _response_context(session, huddle)
    input_payload = synthesis_input(session, huddle)
    evidence_by_id = {item["id"]: item for item in input_payload["evidence"]}
    draft = _llm_draft_is_grounded(draft_data, evidence_by_id, responses)
    if draft is None:
        return None
    evidence = []
    for item in draft.evidence:
        references = " ".join(f"[{source_id}]" for source_id in item.source_ids)
        evidence.append({"statement": f'"{_clean_cited_text(item.statement, set(item.source_ids))}" {references}',
                         "source_ids": item.source_ids, "label": "EVIDENCE"})
    takeaways = []
    for item in draft.key_takeaways:
        references = " ".join(f"[{source_id}]" for source_id in item.source_ids)
        text = _clean_cited_text(item.point, set(item.source_ids))
        takeaways.append({"point": f"{text} {references}".strip(), "source_ids": item.source_ids,
                          "label": "AI SYNTHESIS"})
    raw = {
        "question": question.question,
        "evidence": evidence,
        "expert_perspective": {**_expert_perspective(expert, responses), "summary": draft.expert_summary},
        "key_takeaways": takeaways,
        "uncertainty": UNCERTAINTY_DEFAULTS,
        "sources": _brief_sources(_sources_for_huddle(session, huddle), huddle.evidence_ids),
        "generated_by": "llm",
        "disclaimer": BRIEF_DISCLAIMER,
    }
    try:
        return ClinicalHuddleBrief.model_validate(raw).model_dump(mode="json")
    except ValueError:
        return None


def generate_brief(session: Session, huddle: Huddle) -> dict:
    draft_data = synthesize_with_llm(synthesis_input(session, huddle))
    if draft_data is not None:
        grounded = llm_brief(session, huddle, draft_data)
        if grounded is not None:
            return grounded
    return template_brief(session, huddle)


def validate_external_brief(session: Session, huddle: Huddle, payload: dict) -> dict:
    try:
        brief = ClinicalHuddleBrief.model_validate(payload)
        question, expert, responses = _response_context(session, huddle)
    except Exception as exc:
        raise ValueError("Invalid Clinical Huddle Brief schema") from exc
    if brief.question != question.question or brief.disclaimer != BRIEF_DISCLAIMER:
        raise ValueError("Brief question or disclaimer does not match the huddle")
    source_by_id = _sources_for_huddle(session, huddle)
    attached_ids = set(source_by_id)
    response_texts = [response.text for response in responses]
    if brief.expert_perspective.expert_name != expert.name:
        raise ValueError("Expert name does not match the huddle expert")
    expected_simulated = any(response.is_simulated for response in responses)
    if brief.expert_perspective.is_simulated != expected_simulated:
        raise ValueError("Expert simulation label does not match stored responses")
    expected_audio = next((response.audio_url for response in responses if response.audio_url), None)
    if brief.expert_perspective.audio_url != expected_audio:
        raise ValueError("Expert audio URL does not match stored responses")
    if not any(brief.expert_perspective.summary in text for text in response_texts):
        raise ValueError("Expert perspective must quote the stored expert response")
    if any(item not in UNCERTAINTY_DEFAULTS for item in brief.uncertainty):
        raise ValueError("Uncertainty entries must use the supported source-limit statements")
    for item in brief.evidence:
        if not item.source_ids or any(source_id not in attached_ids for source_id in item.source_ids):
            raise ValueError("Evidence source id is not attached to this huddle")
        citations = _citation_ids(item.statement)
        if not citations.issubset(set(item.source_ids)) or not set(item.source_ids).issubset(citations):
            raise ValueError("Evidence statement must cite its attached source ids inline")
        text = _clean_cited_text(item.statement, attached_ids)
        if not text or any(text not in source_by_id[source_id].get("full_text", "") for source_id in item.source_ids):
            raise ValueError("Evidence statement must be copied verbatim from an attached source")
    for item in brief.key_takeaways:
        if any(source_id not in attached_ids for source_id in item.source_ids):
            raise ValueError("Takeaway source id is not attached to this huddle")
        citations = _citation_ids(item.point)
        if not citations.issubset(attached_ids) or citations != set(item.source_ids):
            raise ValueError("Takeaway contains an unknown or uncited source id")
        text = _clean_cited_text(item.point, attached_ids)
        supporting = [source_by_id[source_id].get("full_text", "") for source_id in item.source_ids]
        if not item.source_ids:
            supporting = response_texts + ["No independent clinical conclusions are added in this brief."]
        if not text or not any(text in source for source in supporting):
            raise ValueError("Takeaway must be copied from attached evidence or expert response")
    expected_sources = {source_id: source for source_id, source in source_by_id.items()}
    brief_source_ids = {source.id for source in brief.sources}
    referenced_ids = {source_id for item in [*brief.evidence, *brief.key_takeaways] for source_id in item.source_ids}
    if not referenced_ids.issubset(brief_source_ids):
        raise ValueError("Every cited id must have matching source metadata")
    for source in brief.sources:
        actual = expected_sources.get(source.id)
        if actual is None or source.citation != (actual.get("citation") or "") \
                or source.url != actual.get("url") or source.verified != bool(actual.get("verified")):
            raise ValueError("Brief contains source metadata that does not match the attached corpus")
    return brief.model_dump(mode="json")
