from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.pet import Pet
    from app.models.job import Job


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("pet_id", "file_hash", name="uq_pet_document_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    pet: Mapped["Pet"] = relationship(
        "Pet",
        back_populates="documents",
    )
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
