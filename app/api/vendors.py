from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin
from app.core.exceptions import InvalidConfigurationException
from app.core.security import hash_password
from app.db.session import get_db
from app.models.vendor import Vendor
from app.models.vendor_zone_share import VendorZoneShare
from app.models.user import User
from app.models.zone import Zone
from app.schemas.vendor import VendorCreate, VendorResponse

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    requested_zone_ids = {share.zone_id for share in payload.shares}
    known_zone_ids = set(db.scalars(select(Zone.id).where(Zone.id.in_(requested_zone_ids))))
    if requested_zone_ids != known_zone_ids:
        raise InvalidConfigurationException("One or more zone_id values do not exist. Call GET /api/zones and use a returned id.")
    vendor = Vendor(name=payload.name, active_cab_count=payload.active_cab_count)
    db.add(vendor)
    db.flush()
    db.add_all([VendorZoneShare(vendor_id=vendor.id, zone_id=share.zone_id, trip_type=share.trip_type.value, target_percent=share.target_percent) for share in payload.shares])
    db.add(User(username=payload.username, password_hash=hash_password(payload.password), role="VENDOR", vendor_id=vendor.id))
    db.commit()
    db.refresh(vendor)
    return vendor
