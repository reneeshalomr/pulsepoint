from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Expert
from app.services.matching import DISCLAIMER, SCORE_NOTE, ensure_demo_experts, match_question

router = APIRouter(prefix="/api/experts", tags=["experts"])


def serialize_expert(expert: Expert) -> dict:
    return {"id": expert.id, "name": expert.name, "title": expert.title,
            "specialty": expert.specialty, "conditions": expert.conditions,
            "topics": expert.topics, "expertise": expert.expertise,
            "availability": expert.availability, "bio": expert.bio, "is_demo": True}


@router.get("")
def list_experts(specialty: str | None = None, session: Session = Depends(get_session)) -> dict:
    ensure_demo_experts(session)
    statement = select(Expert)
    if specialty:
        statement = statement.where(Expert.specialty == specialty)
    experts = session.exec(statement).all()
    experts.sort(key=lambda expert: (expert.specialty, expert.id))
    return {"experts": [serialize_expert(expert) for expert in experts], "disclaimer": DISCLAIMER}


@router.get("/match/{question_id}")
def get_matches(question_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        experts = match_question(session, question_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"experts": experts, "disclaimer": DISCLAIMER, "score_note": SCORE_NOTE}


@router.get("/{expert_id}")
def get_expert(expert_id: str, session: Session = Depends(get_session)) -> dict:
    ensure_demo_experts(session)
    expert = session.get(Expert, expert_id)
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert not found")
    return {"expert": serialize_expert(expert), "disclaimer": DISCLAIMER}
