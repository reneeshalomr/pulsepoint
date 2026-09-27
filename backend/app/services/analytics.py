"""Deterministic, category-only Question Graph aggregation."""

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import Session, select

from app.models import QuestionSignal


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _ranked(counter: Counter) -> list[dict]:
    return [{"name": name, "count": count} for name, count in
            sorted(counter.items(), key=lambda item: (-item[1], item[0].casefold()))]


def question_graph(session: Session, *, days: int = 30, specialty: str | None = None,
                   today: date | None = None) -> dict:
    """Aggregate persisted signals without exposing ids or free text."""
    end_date = today or datetime.now(timezone.utc).date()
    start = datetime.combine(end_date - timedelta(days=days - 1), time.min, tzinfo=timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    signals = session.exec(select(QuestionSignal).where(
        QuestionSignal.timestamp >= start, QuestionSignal.timestamp < end
    )).all()
    if specialty:
        signals = [signal for signal in signals if signal.specialty.casefold() == specialty.casefold()]

    unanswered_counts = Counter((signal.topic, signal.condition) for signal in signals if not signal.answered)
    unanswered = [{"topic": topic, "condition": condition, "count": count}
                  for (topic, condition), count in unanswered_counts.items()]
    unanswered.sort(key=lambda item: (-item["count"], item["topic"].casefold(), item["condition"].casefold()))

    last_start = datetime.combine(end_date - timedelta(days=6), time.min, tzinfo=timezone.utc)
    prior_start = last_start - timedelta(days=7)
    topic_recent = Counter()
    topic_prior = Counter()
    daily_counts = Counter()
    for signal in signals:
        ts = _utc(signal.timestamp)
        if ts >= last_start and ts < end:
            topic_recent[signal.topic] += 1
        elif ts >= prior_start and ts < last_start:
            topic_prior[signal.topic] += 1
        daily_counts[ts.date().isoformat()] += 1
    topics = set(topic_recent) | set(topic_prior)
    emerging = []
    for topic in topics:
        recent, prior = topic_recent[topic], topic_prior[topic]
        if recent <= prior:
            continue
        # Growth is relative increase ((current - previous) / previous), so
        # 9 versus 3 is 2.0, matching the API's fractional-growth convention.
        growth = round((recent - prior) / prior, 2) if prior else float(recent)
        emerging.append({"topic": topic, "last_7d": recent, "prior_7d": prior, "growth": growth})
    emerging.sort(key=lambda item: (-item["last_7d"], -item["growth"], item["topic"].casefold()))
    timeseries = [{"date": (end_date - timedelta(days=offset)).isoformat(),
                   "count": daily_counts[(end_date - timedelta(days=offset)).isoformat()]}
                  for offset in range(days - 1, -1, -1)]
    return {
        "total": len(signals),
        "by_specialty": _ranked(Counter(signal.specialty for signal in signals)),
        "by_condition": _ranked(Counter(signal.condition for signal in signals)),
        "by_topic": _ranked(Counter(signal.topic for signal in signals)),
        "by_intent": _ranked(Counter(signal.intent for signal in signals)),
        "unanswered": unanswered,
        "emerging": emerging,
        "timeseries": timeseries,
        "includes_seeded_data": any(signal.is_seeded for signal in signals),
    }
