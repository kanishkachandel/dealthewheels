from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import current_user, require_admin
from app.db.session import get_db
from app.models.trip import Trip
from app.models.vendor import Vendor
from app.models.zone import Zone
from app.schemas.trip import RejectionResponse, TripCreate, TripHistoryItem, TripResponse
from app.services.rejections import reject_trip
from app.services.completions import complete_trip
from app.services.trips import create_trip

router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.get("", response_model=list[TripHistoryItem])
def list_trips(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), _=Depends(require_admin)):
    rows = db.execute(
        select(Trip, Vendor.name, Zone.label)
        .outerjoin(Vendor, Vendor.id == Trip.assigned_vendor_id)
        .join(Zone, Zone.id == Trip.zone_id)
        .order_by(Trip.created_at.desc())
        .limit(limit)
    )
    return [
        {"id": trip.id, "zone_id": trip.zone_id, "zone_label": zone_label,
         "vendor_name": vendor_name, "assigned_vendor_id": trip.assigned_vendor_id,
         "trip_type": trip.trip_type, "status": trip.status,
         "idempotency_key": trip.idempotency_key, "created_at": trip.created_at}
        for trip, vendor_name, zone_label in rows
    ]


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def allocate_trip(payload: TripCreate, db: Session = Depends(get_db), _=Depends(current_user)):
    return create_trip(db, payload)


@router.post("/{trip_id}/reject", response_model=RejectionResponse)
def reject_assigned_trip(trip_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    trip, cooloff_until = reject_trip(db, trip_id, user.vendor_id)
    return RejectionResponse(trip_id=trip.id, previous_vendor_id=user.vendor_id, assigned_vendor_id=trip.assigned_vendor_id, cooloff_until=cooloff_until)


@router.post("/{trip_id}/complete", response_model=TripResponse)
def complete_assigned_trip(trip_id: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    return complete_trip(db, trip_id)


@router.post("/{trip_id}/reject-by-dispatch", response_model=RejectionResponse)
def record_vendor_rejection(trip_id: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    trip = db.get(Trip, trip_id)
    if not trip or not trip.assigned_vendor_id:
        raise HTTPException(status_code=404, detail="Assigned trip not found")
    previous_vendor_id = trip.assigned_vendor_id
    updated_trip, cooloff_until = reject_trip(db, trip_id, previous_vendor_id)
    return RejectionResponse(trip_id=updated_trip.id, previous_vendor_id=previous_vendor_id,
                             assigned_vendor_id=updated_trip.assigned_vendor_id,
                             cooloff_until=cooloff_until)
