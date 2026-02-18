from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.chat import (
    ChatMessageItem,
    ChatMessageListResponse,
    ChatRequest,
    ChatResponse,
    ChatSource,
    ChatThreadCreateRequest,
    ChatThreadListItem,
    ChatThreadListResponse,
    ChatThreadResponse,
    ChatThreadUpdateRequest,
)
from app.services.chat import answer_chat
from app.services.chat_store import (
    append_assistant_message,
    append_user_message,
    build_context_window,
    create_thread,
    delete_thread,
    get_thread,
    list_messages,
    list_threads,
    maybe_autotitle_thread,
    update_thread,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/threads", response_model=ChatThreadListResponse)
async def get_threads(
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ChatThreadListResponse:
    if status is not None and status not in {"active", "archived"}:
        raise HTTPException(status_code=422, detail="status must be 'active' or 'archived'")
    rows = await list_threads(db, status=status)
    return ChatThreadListResponse(
        items=[
            ChatThreadListItem(
                id=thread.id,
                title=thread.title,
                status=thread.status,
                message_count=int(message_count or 0),
                updated_at=thread.updated_at,
                last_message_at=thread.last_message_at,
            )
            for thread, message_count in rows
        ]
    )


@router.post("/threads", response_model=ChatThreadResponse)
async def create_chat_thread(
    payload: ChatThreadCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatThreadResponse:
    thread = await create_thread(db, title=payload.title)
    await db.commit()
    return ChatThreadResponse(
        id=thread.id,
        title=thread.title,
        status=thread.status,
        updated_at=thread.updated_at,
        last_message_at=thread.last_message_at,
    )


@router.patch("/threads/{thread_id}", response_model=ChatThreadResponse)
async def patch_chat_thread(
    thread_id: UUID,
    payload: ChatThreadUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatThreadResponse:
    thread = await get_thread(db, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if payload.status is not None and payload.status not in {"active", "archived"}:
        raise HTTPException(status_code=422, detail="status must be 'active' or 'archived'")
    thread = await update_thread(db, thread, title=payload.title, status=payload.status)
    await db.commit()
    return ChatThreadResponse(
        id=thread.id,
        title=thread.title,
        status=thread.status,
        updated_at=thread.updated_at,
        last_message_at=thread.last_message_at,
    )


@router.delete("/threads/{thread_id}")
async def remove_chat_thread(thread_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    deleted = await delete_thread(db, thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    await db.commit()
    return {"status": "deleted"}


@router.get("/threads/{thread_id}/messages", response_model=ChatMessageListResponse)
async def get_thread_messages(
    thread_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    before: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageListResponse:
    thread = await get_thread(db, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    messages = await list_messages(db, thread_id, limit=limit, before=before)
    return ChatMessageListResponse(
        items=[
            ChatMessageItem(
                id=message.id,
                role=message.role,
                question_text=message.question_text,
                answer_text=message.answer_text,
                mode=message.mode,
                sources=(
                    [ChatSource.model_validate(item) for item in (message.sources_json or [])]
                    if message.sources_json
                    else None
                ),
                created_at=message.created_at,
            )
            for message in messages
        ]
    )


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    thread = await get_thread(db, payload.thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    recent_messages = await list_messages(db, payload.thread_id, limit=200)
    context_window = build_context_window(recent_messages)

    filters_json = {
        "date_from": payload.date_from.isoformat() if payload.date_from else None,
        "date_to": payload.date_to.isoformat() if payload.date_to else None,
        "top_k": payload.top_k,
    }
    user_message = await append_user_message(
        db,
        thread=thread,
        question_text=payload.question,
        filters_json=filters_json,
        meta_json={
            "context_turns_used": len(context_window.turns),
            "context_char_count": context_window.char_count,
            "context_truncated": context_window.truncated,
        },
    )

    mode, answer, sources = await answer_chat(
        db=db,
        question=payload.question,
        date_from=payload.date_from,
        date_to=payload.date_to,
        top_k=payload.top_k,
        history=context_window.turns,
    )

    assistant_message = await append_assistant_message(
        db,
        thread=thread,
        question_text=payload.question,
        answer_text=answer,
        mode=mode,
        sources=sources,
        filters_json=filters_json,
        meta_json={
            "context_turns_used": len(context_window.turns),
            "context_char_count": context_window.char_count,
            "context_truncated": context_window.truncated,
            "answered_at": datetime.now(timezone.utc).isoformat(),
            "user_message_id": str(user_message.id),
        },
    )
    await maybe_autotitle_thread(db, thread, payload.question)
    await db.commit()

    return ChatResponse(
        thread_id=thread.id,
        message_id=assistant_message.id,
        mode=mode,
        answer=answer,
        sources=sources,
    )
