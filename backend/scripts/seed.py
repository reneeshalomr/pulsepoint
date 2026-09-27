"""Generate and seed deterministic, anonymous demo Question Graph signals."""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import QuestionSignal
from app.taxonomy import CONDITIONS_BY_SPECIALTY, INTENTS, SPECIALTIES, TOPICS

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


def main() -> None:
    records = write_demo_signals()
    init_db()
    with Session(engine) as session:
        ensure_demo_signals(session, records)


if __name__ == "__main__":
    main()
