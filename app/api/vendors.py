from fastapi import APIRouter, Depends, HTTPException, status
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
from app.schemas.vendor import VendorCreate, VendorDetail, VendorResponse, VendorUpdate

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


def _validate_shares(db: Session, shares, exclude_vendor_id: str | None = None) -> None:
    if not any(share.target_percent > 0 for share in shares):
        raise InvalidConfigurationException("At least one vendor share must be greater than 0%.")
    keys = [(share.zone_id, share.trip_type.value) for share in shares]
    if len(keys) != len(set(keys)):
        raise InvalidConfigurationException("A vendor can have only one share for each zone and trip type.")
    requested_zone_ids = {share.zone_id for share in shares}
    known_zone_ids = set(db.scalars(select(Zone.id).where(Zone.id.in_(requested_zone_ids))))
    if requested_zone_ids != known_zone_ids:
        raise InvalidConfigurationException("One or more zones do not exist. Refresh the zone list and try again.")
    for zone_id, trip_type in keys:
        query = select(VendorZoneShare.target_percent).where(
            VendorZoneShare.zone_id == zone_id,
            VendorZoneShare.trip_type == trip_type,
        )
        if exclude_vendor_id:
            query = query.where(VendorZoneShare.vendor_id != exclude_vendor_id)
        existing_total = sum(float(value) for value in db.scalars(query))
        requested_total = sum(s.target_percent for s in shares if s.zone_id == zone_id and s.trip_type.value == trip_type)
        if existing_total + requested_total > 100.0001:
            raise InvalidConfigurationException(f"Shares for {trip_type} in this zone would exceed 100%.")


def _vendor_detail(db: Session, vendor: Vendor) -> dict:
    rows = db.execute(
        select(VendorZoneShare, Zone)
        .join(Zone, Zone.id == VendorZoneShare.zone_id)
        .where(VendorZoneShare.vendor_id == vendor.id)
        .order_by(Zone.min_km, VendorZoneShare.trip_type)
    )
    return {
        "id": vendor.id,
        "name": vendor.name,
        "active_cab_count": vendor.active_cab_count,
        "active": vendor.active,
        "shares": [
            {"zone_id": share.zone_id, "zone_label": zone.label,
             "trip_type": share.trip_type, "target_percent": float(share.target_percent)}
            for share, zone in rows
        ],
    }


@router.get("", response_model=list[VendorDetail])
def list_vendors(db: Session = Depends(get_db), _=Depends(require_admin)):
    vendors = db.scalars(select(Vendor).order_by(Vendor.name)).all()
    return [_vendor_detail(db, vendor) for vendor in vendors]


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    _validate_shares(db, payload.shares)
    if db.scalar(select(Vendor.id).where(Vendor.name == payload.name)):
        raise InvalidConfigurationException("A vendor with that name already exists.")
    if db.scalar(select(User.id).where(User.username == payload.username)):
        raise InvalidConfigurationException("That vendor login username is already in use.")
    vendor = Vendor(name=payload.name, active_cab_count=payload.active_cab_count)
    db.add(vendor)
    db.flush()
    db.add_all([VendorZoneShare(vendor_id=vendor.id, zone_id=share.zone_id, trip_type=share.trip_type.value, target_percent=share.target_percent) for share in payload.shares])
    db.add(User(username=payload.username, password_hash=hash_password(payload.password), role="VENDOR", vendor_id=vendor.id))
    db.commit()
    db.refresh(vendor)
    return vendor


@router.put("/{vendor_id}", response_model=VendorDetail)
def update_vendor(vendor_id: str, payload: VendorUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    name_taken = db.scalar(select(Vendor.id).where(Vendor.name == payload.name, Vendor.id != vendor_id))
    if name_taken:
        raise InvalidConfigurationException("A vendor with that name already exists.")
    _validate_shares(db, payload.shares, exclude_vendor_id=vendor_id)
    vendor.name = payload.name
    vendor.active_cab_count = payload.active_cab_count
    vendor.active = payload.active
    for share in list(db.scalars(select(VendorZoneShare).where(VendorZoneShare.vendor_id == vendor_id))):
        db.delete(share)
    db.flush()
    db.add_all([
        VendorZoneShare(vendor_id=vendor.id, zone_id=share.zone_id,
                        trip_type=share.trip_type.value, target_percent=share.target_percent)
        for share in payload.shares
    ])
    db.commit()
    db.refresh(vendor)
    return _vendor_detail(db, vendor)
