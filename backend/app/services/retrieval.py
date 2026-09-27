"""Deterministic BM25 evidence search over the committed corpus and stored sources."""

import json
import re
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi
from sqlmodel import Session, select

from app.models import EvidenceSource, HCPQuestion
from app.taxonomy import KEYWORDS

CORPUS_PATH = Path(__file__).resolve().parents[3] / "data" / "corpus.json"
STOPWORDS = set("a an and are as at be been but by for from has have how in is it of on or that the this to was were what when where which with should about into over under".split())


@lru_cache(maxsize=1)
def load_corpus() -> tuple[dict, ...]:
    """Load only the committed JSON corpus; runtime never fetches network data."""
    try:
        raw = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(record for record in raw if isinstance(record, dict)) if isinstance(raw, list) else ()


def tokenize(text: str) -> list[str]:
    # Preserve clinically meaningful tokens such as HER2, CDK4/6, and SGLT2.
    tokens = re.findall(r"[a-z0-9]+(?:[+/.-][a-z0-9]+)*", text.casefold())
    return [token for token in tokens if token not in STOPWORDS]


def split_chunks(text: str, max_sentences: int = 4) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+", text)
    sentences: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for piece in pieces:
        start = text.find(piece, cursor)
        if start < 0:
            continue
        end = start + len(piece)
        if piece.strip():
            sentences.append(piece.strip())
            offsets.append((start, end))
        cursor = end
    if not sentences:
        return [text] if text.strip() else []
    if len(sentences) <= 2:
        return [text[offsets[0][0]:offsets[-1][1]]]
    chunks = []
    start = 0
    while start < len(sentences):
        end = start
        word_count = 0
        while end < len(sentences) and end - start < max_sentences and (end - start < 2 or word_count < 80):
            word_count += len(sentences[end].split())
            end += 1
        chunks.append(text[offsets[start][0]:offsets[end - 1][1]])
        if end == len(sentences):
            break
        start = end - 1  # 1 sentence overlap preserves context between windows.
    return chunks


def _source_from_model(source: EvidenceSource) -> dict:
    return {"id": source.id, "external_id": source.external_id, "title": source.title,
            "source_type": source.source_type, "date": source.date, "url": source.url,
            "citation": source.citation, "publisher": source.publisher, "specialty": source.specialty,
            "condition": source.condition, "topics": source.topics, "verified": source.verified,
            "full_text": source.full_text}


def all_sources(session: Session | None = None) -> list[dict]:
    records = [dict(record) for record in load_corpus()]
    if session is not None:
        known = {record.get("external_id") for record in records}
        known.update(record.get("id") for record in records)
        for source in session.exec(select(EvidenceSource)).all():
            if source.id not in known and (not source.external_id or source.external_id not in known):
                records.append(_source_from_model(source))
    return records


def _expand_query(question: str, condition: str | None, topic: str | None, specialty: str | None) -> str:
    parts = [question, condition or "", topic or "", specialty or ""]
    for category, value in (("conditions", condition), ("topics", topic), ("specialties", specialty)):
        if value:
            parts.extend(KEYWORDS.get(category, {}).get(value, []))
    return " ".join(part for part in parts if part)


def search_sources_with_method(session: Session | None, query: str, *, condition: str | None = None,
                               topic: str | None = None, specialty: str | None = None,
                               limit: int = 5) -> tuple[list[dict], str]:
    sources = all_sources(session)
    if condition:
        sources = [source for source in sources if source.get("condition") == condition]
    if topic:
        requested_topic = topic.casefold()
        sources = [source for source in sources
                   if any(isinstance(value, str) and value.casefold() == requested_topic
                          for value in (source.get("topics") or []))]
    if specialty:
        sources = [source for source in sources if source.get("specialty") == specialty]
    chunks: list[tuple[dict, int, str]] = []
    for source in sources:
        for chunk_index, chunk in enumerate(split_chunks(source.get("full_text", ""))):
            chunks.append((source, chunk_index, chunk))
    if not chunks:
        return [], "bm25"
    tokens = [tokenize(chunk) for _, _, chunk in chunks]
    bm25 = BM25Okapi(tokens)
    expanded = _expand_query(query, condition, topic, specialty)
    query_tokens = tokenize(expanded)
    raw_scores = bm25.get_scores(query_tokens)
    max_score = max(raw_scores, default=0.0)
    ranked: dict[str, tuple[float, dict, str]] = {}
    for (source, _, chunk), raw_score in zip(chunks, raw_scores):
        score = float(raw_score)
        if condition and source.get("condition") == condition:
            score *= 1.5
        if topic and any(isinstance(value, str) and value.casefold() == topic.casefold()
                         for value in (source.get("topics") or [])):
            score *= 1.2
        if specialty and source.get("specialty") not in (None, specialty):
            score *= 0.5
        identity = str(source.get("external_id") or source.get("id") or "")
        current = ranked.get(identity)
        if current is None or score > current[0]:
            ranked[identity] = (score, source, chunk)

    # If no useful BM25 match, use same-condition records in deterministic date/id order.
    useful = sum(1 for score, _, _ in ranked.values() if score > 0)
    fallback = useful < 2 and condition is not None
    candidates = list(ranked.values())
    if fallback:
        candidates = [(score, source, chunk) for score, source, chunk in candidates
                      if source.get("condition") == condition]
        candidates.sort(key=lambda item: (item[1].get("date") or "", str(item[1].get("external_id") or item[1].get("id") or "")), reverse=True)
    else:
        candidates.sort(key=lambda item: (-item[0], str(item[1].get("external_id") or item[1].get("id") or "")))
    result = []
    for score, source, snippet in candidates[:limit]:
        relevance = min(1.0, score / max_score) if max_score > 0 and not fallback else (0.5 if fallback else 0.0)
        result.append({"id": source.get("external_id") or source.get("id"), "title": source.get("title"),
                       "type": source.get("source_type"), "date": source.get("date"), "snippet": snippet,
                       "url": source.get("url"), "citation": source.get("citation"),
                       "relevance": round(relevance, 4), "verified": bool(source.get("verified")),
                       "source_type": source.get("source_type"), "publisher": source.get("publisher"),
                       "specialty": source.get("specialty"), "condition": source.get("condition"),
                       "topics": source.get("topics") or [], "external_id": source.get("external_id")})
    return result, "fallback_condition_match" if fallback else "bm25"


def search_sources(session: Session | None, query: str, *, condition: str | None = None,
                   topic: str | None = None, specialty: str | None = None, limit: int = 5) -> list[dict]:
    return search_sources_with_method(session, query, condition=condition, topic=topic,
                                      specialty=specialty, limit=limit)[0]


def label_question_relevance(question: str, sources: list[dict], *, condition: str | None,
                             topic: str | None) -> list[dict]:
    """Add direct/contextual labels only when a result matches question anchors.

    A direct label requires the condition, a distinctive topic term, and any
    explicit progression context in the question to appear in source text.
    Other returned sources are contextual only when a direct match exists.
    """
    if not sources or not condition or not topic:
        return sources
    question_tokens = set(tokenize(question))
    condition_tokens = set(tokenize(condition))
    topic_tokens = set(tokenize(topic))
    topic_anchors = {token for token in topic_tokens if len(token) > 5}
    if not question_tokens & topic_anchors:
        return sources

    progression_anchors = {"progression", "progressed", "relapse", "refractory"}
    progression_requested = bool(question_tokens & progression_anchors)
    direct_indexes: set[int] = set()
    for index, source in enumerate(sources):
        text = f"{source.get('title', '')} {source.get('snippet', '')}".casefold()
        source_tokens = set(tokenize(text))
        if not condition_tokens.issubset(source_tokens):
            continue
        if not source_tokens & topic_anchors:
            continue
        if progression_requested and not source_tokens & progression_anchors:
            continue
        direct_indexes.add(index)

    if not direct_indexes:
        return sources
    return [
        {**source, "relevance_type": "direct" if index in direct_indexes else "contextual"}
        for index, source in enumerate(sources)
    ]


@lru_cache(maxsize=512)
def _cached_question_results(question_id: str, question_text: str, condition: str,
                             topic: str, specialty: str, limit: int) -> tuple[dict, ...]:
    # Questions and the committed corpus are stable during a demo; cache by
    # question identity and its taxonomy/query fields for repeatable huddles.
    return tuple(search_sources(None, question_text, condition=condition, topic=topic,
                                specialty=specialty, limit=limit))


def retrieve_for_question(session: Session, question_id: str, limit: int = 5) -> list[dict]:
    question = session.get(HCPQuestion, question_id)
    if question is None:
        raise LookupError("Question not found")
    results = _cached_question_results(question.id, question.question, question.condition,
                                       question.topic, question.specialty, limit)
    return [dict(result) for result in results]


def retrieve_for_question_with_method(session: Session, question_id: str,
                                      limit: int = 5) -> tuple[list[dict], str]:
    """Return the deterministic question results and the retrieval path used."""
    question = session.get(HCPQuestion, question_id)
    if question is None:
        raise LookupError("Question not found")
    return search_sources_with_method(session, question.question, condition=question.condition,
                                      topic=question.topic, specialty=question.specialty, limit=limit)
