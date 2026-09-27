"""Demo-only reset and stable golden-path discovery endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlmodel import Session, select

from app.config import settings
from app.db import get_session
from app.models import ExpertResponse, HCPQuestion, Huddle, QuestionSignal
from app.services.matching import ensure_demo_experts
from scripts.seed import ensure_demo_signals

router = APIRouter(prefix="/api/demo", tags=["demo"])
DEMO_QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "data" / "demo_questions.json"


def load_golden_path() -> list[dict]:
    try:
        payload = json.loads(DEMO_QUESTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    result = []
    for entry in payload:
        structure = entry.get("structure") if isinstance(entry, dict) else None
        if not isinstance(structure, dict):
            continue
        result.append({
            "text": entry.get("text", ""),
            "specialty": structure.get("specialty"),
            "condition": structure.get("condition"),
            "topic": structure.get("topic"),
            "intent": structure.get("intent"),
            "question": structure.get("question"),
            "key_context": structure.get("key_context", []),
            "is_synthetic": True,
        })
    return result


@router.get("/golden-path")
def golden_path() -> dict:
    return {"questions": load_golden_path()}


@router.post("/reset")
def reset_demo(session: Session = Depends(get_session)) -> dict:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="Not found")

    # Respect FK dependencies and keep evidence/expert corpora intact.
    session.exec(delete(ExpertResponse))
    session.exec(delete(Huddle))
    session.exec(delete(HCPQuestion))
    session.exec(delete(QuestionSignal).where(QuestionSignal.is_seeded.is_(False)))
    session.commit()
    ensure_demo_experts(session)
    ensure_demo_signals(session)
    return {"status": "reset", "questions": 0, "huddles": 0,
            "seeded_signals": len(session.exec(select(QuestionSignal.id).where(
                QuestionSignal.is_seeded.is_(True))).all())}
