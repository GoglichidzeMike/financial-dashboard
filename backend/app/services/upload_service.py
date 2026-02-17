from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.services.categorizer import resolve_merchants_for_transactions
from app.services.embeddings import generate_embeddings_for_transactions
from app.services.parser import ParserError, parse_statement_xlsx


class UploadValidationError(ValueError):
    pass


@dataclass(slots=True)
class UploadAccepted:
    upload_id: int
    filename: str
    status: str


@dataclass(slots=True)
class UploadStatus:
    upload_id: int
    filename: str
    status: str
    processing_phase: str
    progress_percent: int
    rows_total: int
    rows_processed: int
    rows_skipped_non_transaction: int
    rows_invalid: int
    rows_duplicate: int
    rows_inserted: int
    llm_used_count: int
    fallback_used_count: int
    embeddings_generated: int
    error_message: str | None


INSERT_CHUNK_SIZE = 500


def _chunked_rows(rows: list[dict], chunk_size: int) -> Iterable[list[dict]]:
    for idx in range(0, len(rows), chunk_size):
        yield rows[idx : idx + chunk_size]


async def create_upload_job(db: AsyncSession, filename: str) -> UploadAccepted:
    upload = Upload(filename=filename, status="processing", processing_phase="queued", rows_processed=0)
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return UploadAccepted(upload_id=upload.id, filename=upload.filename, status=upload.status)


async def get_upload_status(db: AsyncSession, upload_id: int) -> UploadStatus | None:
    upload = await db.get(Upload, upload_id)
    if upload is None:
        return None

    rows_total = upload.rows_total or 0
    rows_processed = upload.rows_processed or 0
    phase = upload.processing_phase or "queued"
    if upload.status == "done":
        progress_percent = 100
    elif phase == "queued":
        progress_percent = 1
    elif phase == "parsing":
        progress_percent = 5
    elif phase == "categorizing":
        progress_percent = 20
    elif phase == "inserting":
        base = int((rows_processed / max(rows_total, 1)) * 60) if rows_total > 0 else 0
        progress_percent = min(80, 20 + base)
    elif phase == "embedding":
        denom = max(upload.rows_imported or 0, 1)
        emb = upload.embeddings_generated or 0
        progress_percent = min(99, 80 + int((emb / denom) * 20))
    else:
        progress_percent = 10

    return UploadStatus(
        upload_id=upload.id,
        filename=upload.filename,
        status=upload.status,
        processing_phase=phase,
        progress_percent=progress_percent,
        rows_total=rows_total,
        rows_processed=rows_processed,
        rows_skipped_non_transaction=upload.rows_skipped_non_transaction or 0,
        rows_invalid=upload.rows_invalid or 0,
        rows_duplicate=upload.rows_duplicate or 0,
        rows_inserted=upload.rows_imported or 0,
        llm_used_count=upload.llm_used_count or 0,
        fallback_used_count=upload.fallback_used_count or 0,
        embeddings_generated=upload.embeddings_generated or 0,
        error_message=upload.error_message,
    )


async def process_upload_job(
    upload_id: int,
    filename: str,
    file_bytes: bytes,
    generate_embeddings: bool,
) -> None:
    async with async_session() as db:
        upload = await db.get(Upload, upload_id)
        if upload is None:
            return

        try:
            upload.processing_phase = "parsing"
            upload.rows_processed = 0
            upload.error_message = None
            await db.commit()

            parse_result = parse_statement_xlsx(file_bytes)

            if not parse_result.transactions:
                raise UploadValidationError("No valid transaction rows found in the uploaded file")

            upload.rows_total = parse_result.rows_total
            upload.rows_skipped_non_transaction = parse_result.rows_skipped_non_transaction
            upload.rows_invalid = parse_result.rows_invalid
            upload.rows_processed = (
                parse_result.rows_skipped_non_transaction + parse_result.rows_invalid
            )
            upload.processing_phase = "categorizing"
            await db.commit()

            merchant_resolution = await resolve_merchants_for_transactions(
                db, parse_result.transactions
            )

            upload.processing_phase = "inserting"
            await db.commit()

            rows = [
                {
                    "date": tx.date,
                    "posted_date": tx.posted_date,
                    "description_raw": tx.description_raw,
                    "merchant_id": merchant_resolution.merchant_ids[idx],
                    "direction": tx.direction,
                    "amount_original": tx.amount_original,
                    "currency_original": tx.currency_original,
                    "amount_gel": tx.amount_gel,
                    "conversion_rate": tx.conversion_rate,
                    "card_last4": tx.card_last4,
                    "mcc_code": tx.mcc_code,
                    "embedding": None,
                    "upload_id": upload.id,
                    "dedup_key": tx.dedup_key,
                }
                for idx, tx in enumerate(parse_result.transactions)
            ]

            inserted = 0
            inserted_for_embedding: list[tuple[int, str]] = []

            for batch in _chunked_rows(rows, INSERT_CHUNK_SIZE):
                stmt = (
                    insert(Transaction)
                    .values(batch)
                    .on_conflict_do_nothing(index_elements=["dedup_key"])
                    .returning(Transaction.id, Transaction.description_raw)
                )
                result = await db.execute(stmt)
                returned = result.all()
                inserted += len(returned)
                inserted_for_embedding.extend([(row.id, row.description_raw) for row in returned])
                upload.rows_processed = (upload.rows_processed or 0) + len(batch)
                await db.commit()

            embeddings_generated = 0
            embedding_error: str | None = None
            if generate_embeddings and inserted_for_embedding:
                upload.processing_phase = "embedding"
                upload.embeddings_generated = 0
                await db.commit()
                try:
                    async def _on_embedding_progress(count: int) -> None:
                        upload.embeddings_generated = count
                        await db.commit()

                    embeddings_generated = await generate_embeddings_for_transactions(
                        db, inserted_for_embedding, progress_callback=_on_embedding_progress
                    )
                except Exception as exc:  # noqa: BLE001
                    embedding_error = str(exc)

            valid_rows = len(parse_result.transactions)
            duplicates = max(valid_rows - inserted, 0)

            upload.status = "done"
            upload.processing_phase = "done"
            upload.rows_imported = inserted
            upload.rows_duplicate = duplicates
            upload.llm_used_count = merchant_resolution.llm_used_count
            upload.fallback_used_count = merchant_resolution.fallback_used_count
            upload.embeddings_generated = embeddings_generated
            upload.error_message = embedding_error
            await db.commit()
        except UploadValidationError as exc:
            upload.status = "error"
            upload.processing_phase = "error"
            upload.error_message = str(exc)
            upload.rows_imported = 0
            await db.commit()
        except ParserError as exc:
            upload.status = "error"
            upload.processing_phase = "error"
            upload.error_message = str(exc)
            upload.rows_imported = 0
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            upload.status = "error"
            upload.processing_phase = "error"
            upload.error_message = str(exc)
            upload.rows_imported = 0
            await db.commit()
