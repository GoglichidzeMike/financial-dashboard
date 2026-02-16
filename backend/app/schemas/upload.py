from pydantic import BaseModel


class UploadResponse(BaseModel):
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
