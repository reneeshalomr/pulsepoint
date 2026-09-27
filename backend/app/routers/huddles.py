from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import Expert, ExpertResponse, HCPQuestion, Huddle, QuestionSignal
from app.routers.experts import serialize_expert
from app.schemas import ClinicalHuddleBrief, ExpertResponseCreate, HuddleCreate
from app.services.matching import DISCLAIMER, ensure_demo_experts
from app.services.retrieval import all_sources, retrieve_for_question
from app.services.synthesis import generate_brief, synthesis_input, validate_external_brief

router = APIRouter(prefix="/api/huddles", tags=["huddles"])
ALLOWED_STATUSES = {"awaiting_expert", "responded", "synthesized"}
DEMO_QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "data" / "demo_questions.json"


def _source_identity(source: dict) -> set[str]:
    return {value for value in (source.get("external_id"), source.get("id")) if value}


def _expert_for_huddle(session: Session, expert_id: str) -> Expert:
    ensure_demo_experts(session)
    expert = session.get(Expert, expert_id)
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert not found")
    return expert


def _set_question_answered(session: Session, question: HCPQuestion) -> None:
    statement = select(QuestionSignal).where(
        QuestionSignal.specialty == question.specialty,
        QuestionSignal.condition == question.condition,
        QuestionSignal.topic == question.topic,
        QuestionSignal.intent == question.intent,
        QuestionSignal.answered.is_(False),
        QuestionSignal.is_seeded.is_(False),
    ).order_by(QuestionSignal.timestamp.desc())
    signal = session.exec(statement).first()
    if signal is not None:
        signal.answered = True
        session.add(signal)


def _huddle_detail(session: Session, huddle: Huddle) -> dict:
    question = session.get(HCPQuestion, huddle.question_id)
    expert = session.get(Expert, huddle.expert_id)
    sources = all_sources(session)
    evidence = [source for source in sources if set(huddle.evidence_ids) & _source_identity(source)]
    responses = session.exec(select(ExpertResponse).where(ExpertResponse.huddle_id == huddle.id)
                             .order_by(ExpertResponse.created_at, ExpertResponse.id)).all()
    return {
        "huddle": huddle.model_dump(mode="json"),
        "question": question.model_dump(mode="json") if question else None,
        "evidence": evidence,
        "expert": serialize_expert(expert) if expert else None,
        "responses": [response.model_dump(mode="json") for response in responses],
        "brief": huddle.brief,
        "disclaimer": DISCLAIMER,
    }


def _create_response(session: Session, huddle: Huddle, question: HCPQuestion,
                     expert_id: str, mode: str, text: str, *, transcript: str | None = None,
                     audio_url: str | None = None, duration_seconds: float | None = None,
                     is_simulated: bool) -> ExpertResponse:
    if huddle.status != "awaiting_expert":
        raise HTTPException(status_code=409, detail="Huddle is not awaiting an expert response")
    if expert_id != huddle.expert_id:
        raise HTTPException(status_code=422, detail="Response expert does not match the huddle expert")
    _expert_for_huddle(session, expert_id)
    response = ExpertResponse(
        huddle_id=huddle.id, expert_id=expert_id, mode=mode, text=text,
        transcript=transcript, audio_url=audio_url, duration_seconds=duration_seconds,
        is_simulated=is_simulated,
    )
    huddle.status = "responded"
    huddle.updated_at = datetime.now(timezone.utc)
    session.add(response)
    session.add(huddle)
    _set_question_answered(session, question)
    session.commit()
    session.refresh(response)
    return response


def _require_stored_response(session: Session, huddle: Huddle) -> None:
    response_id = session.exec(select(ExpertResponse.id).where(ExpertResponse.huddle_id == huddle.id)).first()
    if response_id is None:
        raise HTTPException(status_code=409, detail="Huddle must have an expert response before synthesis")


def _golden_path_response(question: HCPQuestion, evidence_ids: list[str]) -> str | None:
    if question.extraction_method != "demo_cache":
        return None
    try:
        entries = json.loads(DEMO_QUESTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for entry in entries if isinstance(entries, list) else []:
        structure = entry.get("structure", {})
        if structure.get("question") == question.question and entry.get("simulated_response"):
            return entry["simulated_response"].format(evidence_refs=", ".join(f"[{item}]" for item in evidence_ids) or "none")
    return None


@router.post("", status_code=201)
def create_huddle(payload: HuddleCreate, session: Session = Depends(get_session)) -> dict:
    question = session.get(HCPQuestion, payload.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    _expert_for_huddle(session, payload.expert_id)
    sources = all_sources(session)
    by_identity = {identity: source for source in sources for identity in _source_identity(source)}
    evidence_ids = list(dict.fromkeys(payload.evidence_ids))
    if not evidence_ids:
        evidence_ids = [source["id"] for source in retrieve_for_question(session, question.id)]
    missing = [source_id for source_id in evidence_ids if source_id not in by_identity]
    if missing:
        raise HTTPException(status_code=404, detail="Evidence source not found")
    huddle = Huddle(question_id=question.id, expert_id=payload.expert_id, evidence_ids=evidence_ids,
                    status="awaiting_expert")
    session.add(huddle)
    session.commit()
    session.refresh(huddle)
    return _huddle_detail(session, huddle)


@router.get("")
def list_huddles(
    expert_id: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    statement = select(Huddle)
    if expert_id:
        statement = statement.where(Huddle.expert_id == expert_id)
    if status:
        if status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid huddle status")
        statement = statement.where(Huddle.status == status)
    huddles = session.exec(statement.order_by(Huddle.created_at, Huddle.id)).all()
    return {"huddles": [_huddle_detail(session, huddle) for huddle in huddles], "disclaimer": DISCLAIMER}


@router.get("/{huddle_id}")
def get_huddle(huddle_id: str, session: Session = Depends(get_session)) -> dict:
    huddle = session.get(Huddle, huddle_id)
    if huddle is None:
        raise HTTPException(status_code=404, detail="Huddle not found")
    return _huddle_detail(session, huddle)


@router.get("/{huddle_id}/synthesis-input")
def get_synthesis_input(huddle_id: str, session: Session = Depends(get_session)) -> dict:
    huddle = session.get(Huddle, huddle_id)
    if huddle is None:
        raise HTTPException(status_code=404, detail="Huddle not found")
    return synthesis_input(session, huddle)


@router.post("/{huddle_id}/response", status_code=201)
def submit_response(huddle_id: str, payload: ExpertResponseCreate,
                    session: Session = Depends(get_session)) -> dict:
    huddle = session.get(Huddle, huddle_id)
    if huddle is None:
        raise HTTPException(status_code=404, detail="Huddle not found")
    question = session.get(HCPQuestion, huddle.question_id)
    response = _create_response(session, huddle, question, payload.expert_id, payload.mode, payload.text,
                                transcript=payload.transcript, audio_url=payload.audio_url,
                                duration_seconds=payload.duration_seconds, is_simulated=False)
    return {"huddle_id": huddle.id, "status": huddle.status,
            "response": response.model_dump(mode="json"), "expert_disclaimer": DISCLAIMER,
            "disclaimer": DISCLAIMER}


@router.post("/{huddle_id}/simulate-response", status_code=201)
def simulate_response(huddle_id: str, session: Session = Depends(get_session)) -> dict:
    huddle = session.get(Huddle, huddle_id)
    if huddle is None:
        raise HTTPException(status_code=404, detail="Huddle not found")
    question = session.get(HCPQuestion, huddle.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    text = _golden_path_response(question, huddle.evidence_ids)
    if text is None:
        references = ", ".join(f"[{source_id}]" for source_id in huddle.evidence_ids)
        text = ("Simulated neutral response from a fictional demo profile. This response adds no clinical evidence. "
                f"Please review only the attached retrieved source IDs: {references or 'none'}. ")
    response = _create_response(session, huddle, question, huddle.expert_id, "text", text,
                                is_simulated=True)
    return {"huddle_id": huddle.id, "status": huddle.status,
            "response": response.model_dump(mode="json"), "expert_disclaimer": DISCLAIMER,
            "disclaimer": DISCLAIMER}


@router.post("/{huddle_id}/synthesize")
def synthesize_huddle(huddle_id: str, session: Session = Depends(get_session)) -> dict:
    huddle = session.get(Huddle, huddle_id)
    if huddle is None:
        raise HTTPException(status_code=404, detail="Huddle not found")
    if huddle.status == "synthesized" and huddle.brief is not None:
        return {"huddle_id": huddle.id, "status": huddle.status, "brief": huddle.brief}
    if huddle.status != "responded":
        raise HTTPException(status_code=409, detail="Huddle must have an expert response before synthesis")
    _require_stored_response(session, huddle)
    brief = generate_brief(session, huddle)
    try:
        # Apply the same citation and content checks to generated output before storage.
        brief = validate_external_brief(session, huddle, brief)
    except ValueError:
        brief = generate_brief(session, huddle)
    huddle.brief = brief
    huddle.status = "synthesized"
    huddle.updated_at = datetime.now(timezone.utc)
    session.add(huddle)
    session.commit()
    session.refresh(huddle)
    return {"huddle_id": huddle.id, "status": huddle.status, "brief": huddle.brief}


@router.put("/{huddle_id}/brief")
def store_external_brief(huddle_id: str, payload: ClinicalHuddleBrief,
                         session: Session = Depends(get_session)) -> dict:
    huddle = session.get(Huddle, huddle_id)
    if huddle is None:
        raise HTTPException(status_code=404, detail="Huddle not found")
    if huddle.status not in {"responded", "synthesized"}:
        raise HTTPException(status_code=409, detail="Huddle must have an expert response before storing a brief")
    _require_stored_response(session, huddle)
    try:
        brief = validate_external_brief(session, huddle, payload.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    huddle.brief = brief
    huddle.status = "synthesized"
    huddle.updated_at = datetime.now(timezone.utc)
    session.add(huddle)
    session.commit()
    session.refresh(huddle)
    return {"huddle_id": huddle.id, "status": huddle.status, "brief": huddle.brief}
