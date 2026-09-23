from __future__ import annotations
import uuid
from typing import Optional
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    label: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    min_km: Mapped[int] = mapped_column(Integer, nullable=False)
    max_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
