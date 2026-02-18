from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatHistoryTurn(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class ChatRequest(BaseModel):
    thread_id: UUID
    question: str = Field(min_length=1)
    date_from: date | None = None
    date_to: date | None = None
    top_k: int = Field(default=20, ge=1, le=100)


class ChatSource(BaseModel):
    source_type: str
    title: str
    content: str
    table_columns: list[str] | None = None
    table_rows: list[list[str]] | None = None


class ChatResponse(BaseModel):
    thread_id: UUID
    message_id: UUID
    mode: str
    answer: str
    sources: list[ChatSource]


class ChatThreadListItem(BaseModel):
    id: UUID
    title: str
    status: str
    message_count: int
    updated_at: datetime
    last_message_at: datetime | None


class ChatThreadListResponse(BaseModel):
    items: list[ChatThreadListItem]


class ChatThreadCreateRequest(BaseModel):
    title: str | None = None


class ChatThreadUpdateRequest(BaseModel):
    title: str | None = None
    status: str | None = None


class ChatThreadResponse(BaseModel):
    id: UUID
    title: str
    status: str
    updated_at: datetime
    last_message_at: datetime | None


class ChatMessageItem(BaseModel):
    id: UUID
    role: str
    question_text: str | None = None
    answer_text: str | None = None
    mode: str | None = None
    sources: list[ChatSource] | None = None
    created_at: datetime


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageItem]
