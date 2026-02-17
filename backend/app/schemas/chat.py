from datetime import date

from pydantic import BaseModel, Field


class ChatHistoryTurn(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    date_from: date | None = None
    date_to: date | None = None
    top_k: int = Field(default=20, ge=1, le=100)
    history: list[ChatHistoryTurn] = Field(default_factory=list, max_length=20)


class ChatSource(BaseModel):
    source_type: str
    title: str
    content: str
    table_columns: list[str] | None = None
    table_rows: list[list[str]] | None = None


class ChatResponse(BaseModel):
    mode: str
    answer: str
    sources: list[ChatSource]
