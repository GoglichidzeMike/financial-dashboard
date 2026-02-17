from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.upload import UploadAcceptedResponse, UploadStatusResponse
from app.services.upload_service import create_upload_job, get_upload_status, process_upload_job

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=UploadAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_statement(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    generate_embeddings: bool = True,
    db: AsyncSession = Depends(get_db),
) -> UploadAcceptedResponse:
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

    accepted = await create_upload_job(db, filename=file.filename)
    background_tasks.add_task(
        process_upload_job,
        accepted.upload_id,
        accepted.filename,
        file_bytes,
        generate_embeddings,
    )

    return UploadAcceptedResponse(
        upload_id=accepted.upload_id,
        filename=accepted.filename,
        status=accepted.status,
    )


@router.get("/{upload_id}", response_model=UploadStatusResponse)
async def upload_status(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
) -> UploadStatusResponse:
    upload = await get_upload_status(db, upload_id)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    return UploadStatusResponse(
        upload_id=upload.upload_id,
        filename=upload.filename,
        status=upload.status,
        processing_phase=upload.processing_phase,
        progress_percent=upload.progress_percent,
        rows_total=upload.rows_total,
        rows_processed=upload.rows_processed,
        rows_skipped_non_transaction=upload.rows_skipped_non_transaction,
        rows_invalid=upload.rows_invalid,
        rows_duplicate=upload.rows_duplicate,
        rows_inserted=upload.rows_inserted,
        llm_used_count=upload.llm_used_count,
        fallback_used_count=upload.fallback_used_count,
        embeddings_generated=upload.embeddings_generated,
        error_message=upload.error_message,
    )
