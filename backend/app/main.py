from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlmodel import Session, SQLModel, select

from app.config import settings
from app.db import engine, get_session, init_db
from app.models import EvidenceSource, Expert
from app.routers.questions import router as questions_router
from app.routers.evidence import router as evidence_router
from app.routers.experts import router as experts_router
from app.routers.huddles import router as huddles_router
from app.routers.audio import AUDIO_DIR, router as audio_router
from app.routers.analytics import router as analytics_router
from app.routers.demo import router as demo_router
from app.services.matching import ensure_demo_experts
from scripts.seed import ensure_corpus_sources, ensure_demo_signals

logger = logging.getLogger("pulsepoint.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    from sqlmodel import Session
    with Session(engine) as session:
        ensure_demo_experts(session)
        ensure_corpus_sources(session)
        ensure_demo_signals(session)
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
app.include_router(analytics_router)
app.include_router(demo_router)
app.mount("/static/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


@app.middleware("http")
async def log_request_timing(request: Request, call_next):
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        logger.info("request method=%s path=%s status=%d duration_ms=%.2f",
                    request.method, request.url.path, status_code, elapsed_ms)


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Validation errors can contain the original request value (including PHI).
    logger.info("request validation failed error_count=%d", len(exc.errors()))
    return JSONResponse(status_code=422,
                        content={"detail": "Request validation failed", "code": "validation_error"})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": exc.detail, "code": f"http_{exc.status_code}"},
                        headers=exc.headers)


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled API error", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=500,
                        content={"detail": "Internal server error", "code": "internal_error"})


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
