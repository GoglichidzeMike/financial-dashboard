from fastapi import APIRouter

from app.services.categorizer import check_llm_connection

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/check")
async def llm_check() -> dict:
    return await check_llm_connection()
