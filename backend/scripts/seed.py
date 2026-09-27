"""Generate and seed deterministic, anonymous demo Question Graph signals."""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import Session, delete, select

from app.db import engine, init_db
from app.models import EvidenceChunk, EvidenceSource, QuestionSignal
from app.services.matching import ensure_demo_experts
from app.services.retrieval import load_corpus, split_chunks
from app.taxonomy import CONDITIONS_BY_SPECIALTY, INTENTS, TOPICS

ROOT = Path(__file__).resolve().parents[2]
SIGNALS_PATH = ROOT / "data" / "demo_signals.json"
RANDOM_SEED = 713
SIGNAL_COUNT = 80


def make_demo_signals(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    rng = random.Random(RANDOM_SEED)
    specialties = ["Oncology", "Oncology", "Oncology", "Cardiology", "Endocrinology"]
    records = []
    for index in range(SIGNAL_COUNT):
        specialty = rng.choice(specialties)
        conditions = CONDITIONS_BY_SPECIALTY[specialty]
        if specialty == "Oncology":
            condition = rng.choices(conditions, weights=[0.82, 0.18])[0]
        else:
            condition = rng.choice(conditions)
        topic = rng.choices(TOPICS, weights=[0.45, 0.12, 0.12, 0.08, 0.09, 0.07, 0.07])[0]
        # Keep generated rows within the current 30-day analytics window even
        # when generation happens late in the day.
        day_offset = rng.randrange(29)
        timestamp = now - timedelta(days=day_offset, hours=rng.randrange(24), minutes=rng.randrange(60))
        records.append({
            "id": f"demo-signal-{index + 1:03d}",
            "specialty": specialty,
            "condition": condition,
            "topic": topic,
            "intent": rng.choice(INTENTS),
            "answered": rng.random() < 0.58,
            "is_seeded": True,
            "timestamp": timestamp.isoformat(),
        })
    return records


def write_demo_signals(now: datetime | None = None) -> list[dict]:
    records = make_demo_signals(now)
    SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SIGNALS_PATH.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return records


def ensure_demo_signals(session: Session, records: list[dict] | None = None) -> None:
    if session.exec(select(QuestionSignal.id).where(QuestionSignal.is_seeded.is_(True)).limit(1)).first():
        return
    if records is None:
        try:
            records = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            records = write_demo_signals()
    for record in records:
        values = {**record, "timestamp": datetime.fromisoformat(record["timestamp"])}
        session.add(QuestionSignal(**values))
    session.commit()


def ensure_corpus_sources(session: Session) -> None:
    """Seed the committed corpus and drop only simulated placeholders it replaced."""
    records = list(load_corpus())
    corpus_ids = {record.get("external_id") for record in records if record.get("external_id")}
    has_verified_live_records = any(
        record.get("verified") is True
        and record.get("source_type") in {"PubMed abstract", "Clinical trial registry"}
        and record.get("external_id")
        and record.get("url")
        for record in records
    )

    # Old corpus rows remain in SQLite across refreshes. Remove only clearly
    # labeled simulated placeholders absent from a successfully fetched corpus;
    # preserve imported and other legitimate evidence rows.
    if has_verified_live_records:
        replaced = [source for source in session.exec(select(EvidenceSource)).all()
                    if source.source_type.startswith("Simulated")
                    and source.title.startswith("[SIMULATED]")
                    and not source.verified
                    and source.url is None
                    and source.external_id not in corpus_ids]
        replaced_ids = [source.id for source in replaced]
        if replaced_ids:
            session.exec(delete(EvidenceChunk).where(EvidenceChunk.source_id.in_(replaced_ids)))
            session.exec(delete(EvidenceSource).where(EvidenceSource.id.in_(replaced_ids)))

    for record in records:
        external_id = record.get("external_id")
        if not external_id or session.exec(select(EvidenceSource.id).where(
                EvidenceSource.external_id == external_id)).first():
            continue
        source = EvidenceSource(
            external_id=external_id, title=record["title"], source_type=record["source_type"],
            date=record.get("date"), url=record.get("url"), citation=record["citation"],
            publisher=record.get("publisher", ""), specialty=record.get("specialty", "Other"),
            condition=record.get("condition", "Other"), topics=record.get("topics", []),
            verified=bool(record.get("verified", False)), full_text=record.get("full_text", ""),
        )
        session.add(source)
        session.flush()
        for index, text in enumerate(split_chunks(source.full_text)):
            session.add(EvidenceChunk(source_id=source.id, chunk_index=index, text=text))
    session.commit()


def main() -> None:
    records = write_demo_signals()
    init_db()
    with Session(engine) as session:
        ensure_demo_experts(session)
        ensure_corpus_sources(session)
        ensure_demo_signals(session, records)


if __name__ == "__main__":
    main()
