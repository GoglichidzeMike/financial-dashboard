from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description_raw: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("merchants.id"), nullable=True
    )
    direction: Mapped[str] = mapped_column(String, nullable=False)  # 'expense' | 'income' | 'transfer'
    amount_original: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency_original: Mapped[str] = mapped_column(String, nullable=False)
    amount_gel: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    conversion_rate: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    card_last4: Mapped[str | None] = mapped_column(String, nullable=True)
    mcc_code: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)
    upload_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("uploads.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    merchant: Mapped["Merchant | None"] = relationship(back_populates="transactions")
    upload: Mapped["Upload | None"] = relationship(back_populates="transactions")