from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    rows_imported: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_skipped_non_transaction: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_invalid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_duplicate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_used_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_used_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embeddings_generated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_phase: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="processing", server_default=text("'processing'")
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="upload")
