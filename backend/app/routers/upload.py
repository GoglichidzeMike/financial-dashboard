from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.upload import UploadResponse
from app.services.upload_service import UploadValidationError, import_statement_file

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=UploadResponse)
async def upload_statement(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required"
        )

    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
        )

    try:
        summary = await import_statement_file(db, filename=file.filename, file_bytes=file_bytes)
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return UploadResponse(
        upload_id=summary.upload_id,
        filename=summary.filename,
        status=summary.status,
        rows_total=summary.rows_total,
        rows_skipped_non_transaction=summary.rows_skipped_non_transaction,
        rows_invalid=summary.rows_invalid,
        rows_duplicate=summary.rows_duplicate,
        rows_inserted=summary.rows_inserted,
        llm_used_count=summary.llm_used_count,
        fallback_used_count=summary.fallback_used_count,
    )
