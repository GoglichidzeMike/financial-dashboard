from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import answer_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    return await answer_chat(
        db=db,
        question=payload.question,
        date_from=payload.date_from,
        date_to=payload.date_to,
        top_k=payload.top_k,
    )
