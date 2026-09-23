import uuid
from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class VendorZoneShare(Base):
    __tablename__ = "vendor_zone_shares"
    __table_args__ = (UniqueConstraint("vendor_id", "zone_id", "trip_type", name="uq_vendor_zone_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"), nullable=False)
    target_percent: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    trip_type: Mapped[str] = mapped_column(String(20), nullable=False)
    vendor = relationship("Vendor", back_populates="shares")
