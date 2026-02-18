from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_profile import ChatProfile
from app.models.chat_thread import ChatThread
from app.schemas.chat import ChatHistoryTurn, ChatSource

DEFAULT_PROFILE_SLUG = "default"
DEFAULT_THREAD_TITLE = "New Chat"
MAX_CONTEXT_TURNS = 12
MAX_CONTEXT_CHARS = 16000


@dataclass
class ContextWindow:
    turns: list[ChatHistoryTurn]
    char_count: int
    truncated: bool


async def ensure_default_profile(db: AsyncSession) -> ChatProfile:
    stmt = select(ChatProfile).where(ChatProfile.slug == DEFAULT_PROFILE_SLUG)
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if profile is not None:
        return profile

    profile = ChatProfile(slug=DEFAULT_PROFILE_SLUG, display_name="Local User")
    db.add(profile)
    await db.flush()
    return profile


async def create_thread(db: AsyncSession, *, title: str | None = None) -> ChatThread:
    profile = await ensure_default_profile(db)
    thread = ChatThread(
        profile_id=profile.id,
        title=(title or DEFAULT_THREAD_TITLE).strip() or DEFAULT_THREAD_TITLE,
        status="active",
    )
    db.add(thread)
    await db.flush()
    return thread


async def get_thread(db: AsyncSession, thread_id: UUID) -> ChatThread | None:
    stmt = select(ChatThread).where(ChatThread.id == thread_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_threads(db: AsyncSession, status: str | None = None) -> list[tuple[ChatThread, int]]:
    profile = await ensure_default_profile(db)
    count_expr = func.count(ChatMessage.id).label("message_count")
    stmt = (
        select(ChatThread, count_expr)
        .outerjoin(ChatMessage, ChatMessage.thread_id == ChatThread.id)
        .where(ChatThread.profile_id == profile.id)
        .group_by(ChatThread.id)
        .order_by(ChatThread.updated_at.desc())
    )
    if status:
        stmt = stmt.where(ChatThread.status == status)
    return list((await db.execute(stmt)).all())


async def update_thread(
    db: AsyncSession, thread: ChatThread, *, title: str | None = None, status: str | None = None
) -> ChatThread:
    if title is not None:
        thread.title = title.strip() or DEFAULT_THREAD_TITLE
    if status is not None:
        thread.status = status
    thread.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return thread


async def delete_thread(db: AsyncSession, thread_id: UUID) -> bool:
    stmt = delete(ChatThread).where(ChatThread.id == thread_id)
    result = await db.execute(stmt)
    return (result.rowcount or 0) > 0


async def list_messages(
    db: AsyncSession,
    thread_id: UUID,
    limit: int = 100,
    before: datetime | None = None,
) -> list[ChatMessage]:
    stmt = select(ChatMessage).where(ChatMessage.thread_id == thread_id)
    if before is not None:
        stmt = stmt.where(ChatMessage.created_at < before)
    stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(limit)
    messages = list((await db.execute(stmt)).scalars().all())
    messages.reverse()
    return messages


def _pair_turns_from_messages(messages: list[ChatMessage]) -> list[ChatHistoryTurn]:
    turns: list[ChatHistoryTurn] = []
    pending_question: str | None = None
    for message in messages:
        if message.role == "user":
            pending_question = message.question_text or message.answer_text or ""
            continue
        if message.role == "assistant":
            question = message.question_text or pending_question or ""
            answer = message.answer_text or ""
            if question and answer:
                turns.append(ChatHistoryTurn(question=question, answer=answer))
            pending_question = None
    return turns


def build_context_window(messages: list[ChatMessage]) -> ContextWindow:
    turns = _pair_turns_from_messages(messages)
    if not turns:
        return ContextWindow(turns=[], char_count=0, truncated=False)

    selected: list[ChatHistoryTurn] = []
    char_count = 0
    truncated = False
    for turn in reversed(turns):
        turn_chars = len(turn.question) + len(turn.answer)
        if selected and (len(selected) >= MAX_CONTEXT_TURNS or char_count + turn_chars > MAX_CONTEXT_CHARS):
            truncated = True
            break
        selected.append(turn)
        char_count += turn_chars
    selected.reverse()
    return ContextWindow(turns=selected, char_count=char_count, truncated=truncated)


async def append_user_message(
    db: AsyncSession,
    *,
    thread: ChatThread,
    question_text: str,
    filters_json: dict | None,
    meta_json: dict | None,
) -> ChatMessage:
    message = ChatMessage(
        thread_id=thread.id,
        role="user",
        question_text=question_text,
        answer_text=None,
        mode=None,
        sources_json=None,
        filters_json=filters_json,
        meta_json=meta_json,
    )
    db.add(message)
    thread.updated_at = datetime.now(timezone.utc)
    thread.last_message_at = thread.updated_at
    await db.flush()
    return message


async def append_assistant_message(
    db: AsyncSession,
    *,
    thread: ChatThread,
    question_text: str,
    answer_text: str,
    mode: str,
    sources: list[ChatSource],
    filters_json: dict | None,
    meta_json: dict | None,
) -> ChatMessage:
    message = ChatMessage(
        thread_id=thread.id,
        role="assistant",
        question_text=question_text,
        answer_text=answer_text,
        mode=mode,
        sources_json=[source.model_dump() for source in sources],
        filters_json=filters_json,
        meta_json=meta_json,
    )
    db.add(message)
    thread.updated_at = datetime.now(timezone.utc)
    thread.last_message_at = thread.updated_at
    await db.flush()
    return message


async def maybe_autotitle_thread(db: AsyncSession, thread: ChatThread, first_question: str) -> None:
    if thread.title != DEFAULT_THREAD_TITLE:
        return
    thread.title = (first_question.strip()[:48] or DEFAULT_THREAD_TITLE)
    await db.flush()
