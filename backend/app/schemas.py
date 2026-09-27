from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuestionCreate(BaseModel):
    text: str = Field(max_length=2000)

    @field_validator("text")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be empty")
        return value


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    specialty: str
    condition: str
    topic: str
    intent: str
    question: str
    key_context: list[str]
    extraction_method: str
    confidence: float
    phi_detected: bool


class EvidenceImport(BaseModel):
    """Request to persist a record that already exists in the committed corpus."""

    external_id: str = Field(min_length=1, max_length=80)


class HuddleCreate(BaseModel):
    question_id: str = Field(min_length=1)
    expert_id: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)


class ExpertResponseCreate(BaseModel):
    expert_id: str = Field(min_length=1)
    mode: Literal["text", "voice"]
    text: str = Field(min_length=1, max_length=10000)
    transcript: str | None = Field(default=None, max_length=10000)
    audio_url: str | None = Field(default=None, max_length=500)
    duration_seconds: float | None = Field(default=None, ge=0, le=3600)

    @field_validator("text")
    @classmethod
    def response_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value.strip()

    @field_validator("transcript")
    @classmethod
    def normalize_transcript(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class BriefEvidenceItem(BaseModel):
    statement: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    label: Literal["EVIDENCE"]


class BriefExpertPerspective(BaseModel):
    summary: str = Field(min_length=1)
    expert_name: str = Field(min_length=1)
    is_simulated: bool
    audio_url: str | None = None
    label: Literal["EXPERT OPINION"]


class BriefTakeaway(BaseModel):
    point: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    label: Literal["AI SYNTHESIS"]


class BriefSource(BaseModel):
    id: str = Field(min_length=1)
    citation: str
    url: str | None = None
    verified: bool


class ClinicalHuddleBrief(BaseModel):
    question: str = Field(min_length=1)
    evidence: list[BriefEvidenceItem]
    expert_perspective: BriefExpertPerspective
    key_takeaways: list[BriefTakeaway] = Field(min_length=1)
    uncertainty: list[str] = Field(min_length=1)
    sources: list[BriefSource]
    generated_by: Literal["llm", "template", "external"]
    disclaimer: str = Field(min_length=1)


class SynthesisDraft(BaseModel):
    """Fields an LLM may draft; citation/source metadata is assembled by the app."""

    evidence: list[BriefEvidenceItem]
    expert_summary: str = Field(min_length=1)
    key_takeaways: list[BriefTakeaway]
    uncertainty: list[str] = Field(default_factory=list)


class AnalyticsCount(BaseModel):
    name: str
    count: int


class UnansweredSignalCount(BaseModel):
    topic: str
    condition: str
    count: int


class EmergingTopic(BaseModel):
    topic: str
    last_7d: int
    prior_7d: int
    growth: float


class AnalyticsDateCount(BaseModel):
    date: str
    count: int


class QuestionGraphResponse(BaseModel):
    total: int
    by_specialty: list[AnalyticsCount]
    by_condition: list[AnalyticsCount]
    by_topic: list[AnalyticsCount]
    by_intent: list[AnalyticsCount]
    unanswered: list[UnansweredSignalCount]
    emerging: list[EmergingTopic]
    timeseries: list[AnalyticsDateCount]
    includes_seeded_data: bool
