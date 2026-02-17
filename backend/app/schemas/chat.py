from datetime import date

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    date_from: date | None = None
    date_to: date | None = None
    top_k: int = Field(default=20, ge=1, le=100)


class ChatSource(BaseModel):
    source_type: str
    title: str
    content: str


class ChatResponse(BaseModel):
    mode: str
    answer: str
    sources: list[ChatSource]
