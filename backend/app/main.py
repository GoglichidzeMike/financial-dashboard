from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import engine
from app.routers.categories import router as categories_router
from app.routers.llm import router as llm_router
from app.routers.merchants import router as merchants_router
from app.routers.transactions import router as transactions_router
from app.routers.upload import router as upload_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Enable pgvector extension on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    yield
    await engine.dispose()


app = FastAPI(title="Finance Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(upload_router)
app.include_router(transactions_router)
app.include_router(merchants_router)
app.include_router(categories_router)
app.include_router(llm_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready"}
