from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HCPQuestion(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    raw_text: str
    question: str
    specialty: str
    condition: str
    topic: str
    intent: str
    key_context: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    extraction_method: str
    confidence: float = Field(ge=0, le=1)
    phi_detected: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceSource(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    title: str
    source_type: str
    date: str | None = None
    url: str | None = None
    citation: str
    publisher: str
    specialty: str
    condition: str
    topics: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    verified: bool = False
    full_text: str


class EvidenceChunk(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    source_id: str = Field(foreign_key="evidencesource.id", index=True)
    chunk_index: int
    text: str


class Expert(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    title: str
    specialty: str
    conditions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    topics: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    expertise: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    availability: str
    bio: str
    is_demo: bool = True


class Huddle(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    question_id: str = Field(foreign_key="hcpquestion.id", index=True)
    expert_id: str = Field(foreign_key="expert.id", index=True)
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = "awaiting_expert"
    brief: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ExpertResponse(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    huddle_id: str = Field(foreign_key="huddle.id", index=True)
    expert_id: str = Field(foreign_key="expert.id", index=True)
    mode: str
    text: str
    transcript: str | None = None
    audio_url: str | None = None
    duration_seconds: float | None = None
    is_simulated: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class QuestionSignal(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    specialty: str
    condition: str
    topic: str
    intent: str
    answered: bool = False
    is_seeded: bool = False
    timestamp: datetime = Field(default_factory=utc_now)
