from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.models import HCPQuestion, QuestionSignal
from app.schemas import QuestionCreate, QuestionResponse
from app.services.extraction import extract_question
from app.services.phi import scrub_phi

router = APIRouter(prefix="/api/questions", tags=["questions"])


def serialize_question(question: HCPQuestion) -> QuestionResponse:
    return QuestionResponse(
        question_id=question.id,
        specialty=question.specialty,
        condition=question.condition,
        topic=question.topic,
        intent=question.intent,
        question=question.question,
        key_context=question.key_context,
        extraction_method=question.extraction_method,
        confidence=question.confidence,
        phi_detected=question.phi_detected,
    )


@router.post("", response_model=QuestionResponse, status_code=201)
def create_question(payload: QuestionCreate, session: Session = Depends(get_session)) -> QuestionResponse:
    scrubbed_text, phi_detected = scrub_phi(payload.text)
    structure = extract_question(scrubbed_text)
    question = HCPQuestion(
        raw_text=scrubbed_text,
        question=structure["question"],
        specialty=structure["specialty"],
        condition=structure["condition"],
        topic=structure["topic"],
        intent=structure["intent"],
        key_context=structure["key_context"],
        extraction_method=structure["extraction_method"],
        confidence=structure["confidence"],
        phi_detected=phi_detected,
    )
    session.add(question)
    session.add(QuestionSignal(specialty=question.specialty, condition=question.condition,
                               topic=question.topic, intent=question.intent, answered=False))
    session.commit()
    session.refresh(question)
    return serialize_question(question)


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(question_id: str, session: Session = Depends(get_session)) -> QuestionResponse:
    question = session.get(HCPQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return serialize_question(question)
