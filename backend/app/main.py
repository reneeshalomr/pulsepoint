from contextlib import asynccontextmanager
import json
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, SQLModel, select

from app.config import settings
from app.db import engine, get_session, init_db
from app.models import EvidenceSource, Expert
from app.routers.questions import router as questions_router
from app.routers.evidence import router as evidence_router
from app.routers.experts import router as experts_router
from app.routers.huddles import router as huddles_router
from app.routers.audio import AUDIO_DIR, router as audio_router
from app.services.matching import ensure_demo_experts


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    from sqlmodel import Session
    with Session(engine) as session:
        ensure_demo_experts(session)
    yield


app = FastAPI(title="PULSEPOINT API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(questions_router)
app.include_router(evidence_router)
app.include_router(experts_router)
app.include_router(huddles_router)
app.include_router(audio_router)
app.mount("/static/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


@app.get("/api/health")
def health(session: Session = Depends(get_session)) -> dict[str, object]:
    # Counts are based on persisted records; corpus_size can be reported from the
    # committed corpus file when it exists, before the later seeding phase.
    corpus_path = Path(__file__).resolve().parents[2] / "data" / "corpus.json"
    corpus_size = 0
    if corpus_path.exists():
        try:
            payload = json.loads(corpus_path.read_text(encoding="utf-8"))
            corpus_size = len(payload) if isinstance(payload, list) else 0
        except (OSError, json.JSONDecodeError):
            corpus_size = 0
    experts_count = len(session.exec(select(Expert.id)).all())
    # Ensure the source table is part of health's DB readiness check.
    session.exec(select(EvidenceSource.id).limit(1)).all()
    return {"status": "ok", "db": "ok", "llm_provider": settings.llm_provider,
            "corpus_size": corpus_size, "experts_count": experts_count}
