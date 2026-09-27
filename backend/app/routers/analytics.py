from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.db import get_session
from app.schemas import QuestionGraphResponse
from app.services.analytics import question_graph
from scripts.seed import ensure_demo_signals

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/questions", response_model=QuestionGraphResponse)
def get_question_graph(days: int = Query(default=30, ge=1, le=365),
                       specialty: str | None = Query(default=None, min_length=1, max_length=80),
                       session: Session = Depends(get_session)) -> dict:
    ensure_demo_signals(session)
    return question_graph(session, days=days, specialty=specialty)
