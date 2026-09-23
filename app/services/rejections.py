from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import NoEligibleVendorException
from app.models.trip import Trip
from app.models.trip_event import TripEvent
from app.models.vendor import Vendor
from app.services.allocator import allocator_for
from app.services.cooloff import add_cooloff
from app.services.metrics import REJECTIONS


def reject_trip(db: Session, trip_id: str, vendor_id: str) -> tuple[Trip, str]:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id).with_for_update())
    if not trip or trip.status != "ASSIGNED" or trip.assigned_vendor_id != vendor_id:
        raise NoEligibleVendorException("Trip is not currently assigned to this vendor")
    previous_vendor = db.scalar(select(Vendor).where(Vendor.id == vendor_id).with_for_update())
    previous_vendor.active_cab_count += 1  # cab was reserved at offer time; rejection releases it.
    cooloff_until = add_cooloff(db, vendor_id, trip.id)
    trip.assigned_vendor_id = None
    # The allocator queries the same transaction; flush the new exclusion and
    # released assignment before it builds its eligible priority heap.
    db.flush()
    # Reallocation uses the same fair stream but the rejecting vendor is now filtered by cool-off.
    allocator_for(trip.trip_type).allocate(db, trip)
    db.add_all([TripEvent(trip_id=trip.id, event_type=f"REJECTED:{vendor_id}"), TripEvent(trip_id=trip.id, event_type=f"REASSIGNED:{trip.assigned_vendor_id}")])
    REJECTIONS.inc()
    db.commit()
    db.refresh(trip)
    return trip, cooloff_until.isoformat()
