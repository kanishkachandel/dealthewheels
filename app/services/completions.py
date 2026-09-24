from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import NoEligibleVendorException
from app.models.trip import Trip
from app.models.trip_event import TripEvent
from app.models.vendor import Vendor


def complete_trip(db: Session, trip_id: str) -> Trip:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id).with_for_update())
    if not trip or trip.status != "ASSIGNED":
        raise NoEligibleVendorException("Trip is not currently in progress")
    vendor = db.scalar(select(Vendor).where(Vendor.id == trip.assigned_vendor_id).with_for_update())
    if not vendor:
        raise NoEligibleVendorException("The assigned vendor no longer exists")
    vendor.active_cab_count += 1
    trip.status = "COMPLETED"
    db.add(TripEvent(trip_id=trip.id, event_type=f"COMPLETED:{vendor.id}"))
    db.commit()
    db.refresh(trip)
    return trip
