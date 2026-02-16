from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.upload import Upload
from app.services.categorizer import resolve_merchants_for_transactions
from app.services.parser import ParserError, parse_statement_xlsx


class UploadValidationError(ValueError):
    pass


@dataclass(slots=True)
class UploadSummary:
    upload_id: int
    filename: str
    status: str
    rows_total: int
    rows_skipped_non_transaction: int
    rows_invalid: int
    rows_duplicate: int
    rows_inserted: int
    llm_used_count: int
    fallback_used_count: int


INSERT_CHUNK_SIZE = 500


def _chunked_rows(rows: list[dict], chunk_size: int) -> list[list[dict]]:
    return [rows[idx : idx + chunk_size] for idx in range(0, len(rows), chunk_size)]


async def import_statement_file(
    db: AsyncSession, filename: str, file_bytes: bytes
) -> UploadSummary:
    upload = Upload(filename=filename, status="processing")
    db.add(upload)
    await db.flush()

    try:
        parse_result = parse_statement_xlsx(file_bytes)

        if not parse_result.transactions:
            upload.status = "error"
            upload.rows_imported = 0
            await db.commit()
            raise UploadValidationError("No valid transaction rows found in the uploaded file")

        merchant_resolution = await resolve_merchants_for_transactions(
            db, parse_result.transactions
        )

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
        for batch in _chunked_rows(rows, INSERT_CHUNK_SIZE):
            stmt = insert(Transaction).values(batch).on_conflict_do_nothing(
                index_elements=["dedup_key"]
            )
            result = await db.execute(stmt)
            inserted += result.rowcount or 0

        valid_rows = len(parse_result.transactions)
        duplicates = max(valid_rows - inserted, 0)

        upload.status = "done"
        upload.rows_imported = inserted
        await db.commit()

        return UploadSummary(
            upload_id=upload.id,
            filename=upload.filename,
            status=upload.status,
            rows_total=parse_result.rows_total,
            rows_skipped_non_transaction=parse_result.rows_skipped_non_transaction,
            rows_invalid=parse_result.rows_invalid,
            rows_duplicate=duplicates,
            rows_inserted=inserted,
            llm_used_count=merchant_resolution.llm_used_count,
            fallback_used_count=merchant_resolution.fallback_used_count,
        )
    except UploadValidationError:
        raise
    except ParserError as exc:
        upload.status = "error"
        upload.rows_imported = 0
        await db.commit()
        raise UploadValidationError(str(exc)) from exc
    except Exception:
        await db.rollback()
        db.add(Upload(filename=filename, status="error", rows_imported=0))
        await db.commit()
        raise
