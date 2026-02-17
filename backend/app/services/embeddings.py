from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from openai import AsyncOpenAI
from sqlalchemy import bindparam, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.transaction import Transaction

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 100


def _embeddings_available() -> bool:
    key = settings.OPENAI_API_KEY.strip()
    return bool(key and key != "sk-your-key-here")


async def generate_embeddings_for_transactions(
    db: AsyncSession,
    transaction_rows: Sequence[tuple[int, str]],
    progress_callback: Callable[[int], Awaitable[None]] | None = None,
) -> int:
    if not transaction_rows or not _embeddings_available():
        return 0

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    updated = 0

    for start in range(0, len(transaction_rows), EMBEDDING_BATCH_SIZE):
        batch = transaction_rows[start : start + EMBEDDING_BATCH_SIZE]
        ids = [row[0] for row in batch]
        texts = [row[1] for row in batch]

        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        vectors = [item.embedding for item in response.data]

        params = [
            {"b_id": tx_id, "b_embedding": vector}
            for tx_id, vector in zip(ids, vectors, strict=True)
        ]

        stmt = (
            update(Transaction.__table__)
            .where(Transaction.__table__.c.id == bindparam("b_id"))
            .values(embedding=bindparam("b_embedding"))
            .execution_options(synchronize_session=False)
        )
        await db.execute(stmt, params)
        updated += len(params)
        if progress_callback is not None:
            await progress_callback(updated)

    return updated
