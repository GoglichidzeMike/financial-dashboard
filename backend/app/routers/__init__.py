from app.routers.categories import router as categories_router
from app.routers.chat import router as chat_router
from app.routers.dashboard import router as dashboard_router
from app.routers.llm import router as llm_router
from app.routers.merchants import router as merchants_router
from app.routers.transactions import router as transactions_router
from app.routers.upload import router as upload_router

__all__ = [
    "upload_router",
    "transactions_router",
    "merchants_router",
    "categories_router",
    "chat_router",
    "llm_router",
    "dashboard_router",
]
