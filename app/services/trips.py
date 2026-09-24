from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import DuplicateTripException, InvalidConfigurationException
from app.models.trip import Trip
from app.models.trip_event import TripEvent
from app.schemas.trip import TripCreate
from app.services.allocator import allocator_for
from app.services.metrics import ALLOCATIONS
from app.services.zones import resolve_zone
from app.models.vendor_zone_share import VendorZoneShare


def create_trip(db: Session, payload: TripCreate, trace: Optional[list] = None) -> Trip:
    """Allocate one trip. `trace` collects the allocator's per-vendor decision rows for demos."""
    existing = db.scalar(select(Trip).where(Trip.idempotency_key == payload.idempotency_key))
    if existing:
        return existing  # An idempotent retry returns the original assignment safely.
    zone = resolve_zone(db, payload.distance_km)
    configured_shares = list(db.scalars(select(VendorZoneShare.target_percent).where(
        VendorZoneShare.zone_id == zone.id,
        VendorZoneShare.trip_type == payload.trip_type.value,
    ).with_for_update()))
    configured_total = sum(float(value) for value in configured_shares)
    if not configured_shares or abs(configured_total - 100.0) > 0.01:
        raise InvalidConfigurationException(
            f"Vendor shares for {zone.label} / {payload.trip_type.value} must total 100% before allocating trips (currently {configured_total:g}%)."
        )
    trip = Trip(zone_id=zone.id, distance_km=payload.distance_km, trip_type=payload.trip_type.value, status="ASSIGNED", idempotency_key=payload.idempotency_key)
    db.add(trip)
    db.flush()
    allocator = allocator_for(trip.trip_type)
    vendor = allocator.allocate(db, trip)
    if trace is not None:
        trace.extend(row.as_dict() for row in allocator.last_decision)
    db.add(TripEvent(trip_id=trip.id, event_type=f"ASSIGNED:{vendor.id}"))
    ALLOCATIONS.labels(trip.trip_type).inc()
    db.commit()
    db.refresh(trip)
    return trip
