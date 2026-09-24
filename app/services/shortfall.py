from __future__ import annotations
from collections import Counter
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.trip import Trip
from app.models.vendor_zone_share import VendorZoneShare


def running_totals(db: Session, zone_id: str, trip_type: str, up_to: Optional[datetime] = None) -> Tuple[int, Counter[str]]:
    query = select(Trip.assigned_vendor_id).where(Trip.zone_id == zone_id, Trip.trip_type == trip_type, Trip.status.in_(("ASSIGNED", "COMPLETED")))
    if up_to:
        query = query.where(Trip.created_at <= up_to)
    ids = [vendor_id for vendor_id in db.scalars(query) if vendor_id]
    return len(ids), Counter(ids)


def carry_forward_residue(db: Session, vendor_id: str, zone_id: str, trip_type: str, before: datetime) -> float:
    """All pre-day demand is the baseline that keeps fractional drift alive across days."""
    total, actual = running_totals(db, zone_id, trip_type, before)
    share = db.scalar(select(VendorZoneShare.target_percent).where(VendorZoneShare.vendor_id == vendor_id, VendorZoneShare.zone_id == zone_id, VendorZoneShare.trip_type == trip_type))
    return (float(share or 0) / 100 * total) - actual[vendor_id]


def compute_shortfall(target_percent: float, total_before: int, allocated: int) -> float:
    """Global expected demand is never reset at midnight, so residue persists naturally."""
    return (target_percent / 100 * (total_before + 1)) - allocated
