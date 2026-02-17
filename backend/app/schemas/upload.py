from pydantic import BaseModel


class UploadAcceptedResponse(BaseModel):
    upload_id: int
    filename: str
    status: str


class UploadStatusResponse(BaseModel):
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
