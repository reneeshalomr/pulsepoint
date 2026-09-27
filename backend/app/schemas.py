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
