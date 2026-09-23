from __future__ import annotations
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.zone import Zone


DEFAULT_ZONES: tuple = (("0-15 km", 0, 15), ("15-25 km", 15, 25), ("25+ km", 25, None))


def ensure_default_zones(db: Session) -> None:
    if db.scalar(select(Zone.id).limit(1)):
        return
    db.add_all([Zone(label=label, min_km=min_km, max_km=max_km) for label, min_km, max_km in DEFAULT_ZONES])
    db.commit()


def resolve_zone(db: Session, distance_km: int) -> Zone:
    query = select(Zone).where(Zone.min_km <= distance_km).where((Zone.max_km.is_(None)) | (Zone.max_km >= distance_km)).order_by(Zone.min_km.desc())
    zone = db.scalar(query)
    if not zone:
        raise ValueError(f"No zone configured for {distance_km} km")
    return zone
