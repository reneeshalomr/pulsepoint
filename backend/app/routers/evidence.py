from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import EvidenceSource
from app.schemas import EvidenceImport
from app.services.retrieval import load_corpus, retrieve_for_question_with_method, search_sources_with_method

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/search")
def search_evidence(
    q: str = "",
    query: str | None = None,
    condition: str | None = None,
    topic: str | None = None,
    specialty: str | None = None,
    limit: int = Query(default=5, ge=1, le=12),
    session: Session = Depends(get_session),
) -> dict:
    search_query = (query if query is not None else q).strip()
    sources, method = search_sources_with_method(session, search_query, condition=condition, topic=topic,
                                                 specialty=specialty, limit=limit)
    return {"query": search_query, "retrieval_method": method, "count": len(sources),
            "limit": limit, "sources": sources}


@router.get("/{question_id}")
def question_evidence(question_id: str, session: Session = Depends(get_session)) -> dict:
    try:
        sources, method = retrieve_for_question_with_method(session, question_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"question_id": question_id, "retrieval_method": method, "sources": sources}


@router.post("", status_code=201)
def import_evidence(payload: EvidenceImport, session: Session = Depends(get_session)) -> dict:
    # Only corpus-backed records are importable. This keeps arbitrary request
    # bodies from becoming invented citations or sources.
    record = next((item for item in load_corpus() if item.get("external_id") == payload.external_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence source not found in committed corpus")
    existing = session.exec(select(EvidenceSource).where(EvidenceSource.external_id == payload.external_id)).first()
    if existing is not None:
        source = existing
    else:
        source = EvidenceSource(
            external_id=record["external_id"], title=record["title"], source_type=record["source_type"],
            date=record.get("date"), url=record.get("url"), citation=record["citation"],
            publisher=record["publisher"], specialty=record["specialty"], condition=record["condition"],
            topics=record.get("topics", []), verified=bool(record.get("verified", False)),
            full_text=record["full_text"],
        )
        session.add(source)
        session.commit()
        session.refresh(source)
    return {"id": source.id, "external_id": source.external_id, "title": source.title,
            "source_type": source.source_type, "date": source.date, "url": source.url,
            "citation": source.citation, "publisher": source.publisher, "specialty": source.specialty,
            "condition": source.condition, "topics": source.topics, "verified": source.verified,
            "full_text": source.full_text}
