from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.dependencies import current_user
from app.db.session import get_db
from app.schemas.trip import RejectionResponse, TripCreate, TripResponse
from app.services.rejections import reject_trip
from app.services.trips import create_trip

router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def allocate_trip(payload: TripCreate, db: Session = Depends(get_db), _=Depends(current_user)):
    return create_trip(db, payload)


@router.post("/{trip_id}/reject", response_model=RejectionResponse)
def reject_assigned_trip(trip_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    trip, cooloff_until = reject_trip(db, trip_id, user.vendor_id)
    return RejectionResponse(trip_id=trip.id, previous_vendor_id=user.vendor_id, assigned_vendor_id=trip.assigned_vendor_id, cooloff_until=cooloff_until)
