from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.cooloff_entry import CooloffEntry


def is_in_cooloff(db: Session, vendor_id: str, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    # SQLite drops timezone offsets while Postgres retains them; normalize on read
    # so demo and production databases use identical cool-off semantics.
    expiries = db.scalars(select(CooloffEntry.expires_at).where(CooloffEntry.vendor_id == vendor_id))
    return any((expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry) > now for expiry in expiries)


def add_cooloff(db: Session, vendor_id: str, trip_id: str) -> datetime:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=get_settings().cooloff_minutes)
    db.add(CooloffEntry(vendor_id=vendor_id, trip_id=trip_id, expires_at=expires_at))
    return expires_at
