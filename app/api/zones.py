from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import current_user
from app.db.session import get_db
from app.models.zone import Zone
from app.schemas.zone import ZoneResponse

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("", response_model=list[ZoneResponse])
def list_zones(db: Session = Depends(get_db), _=Depends(current_user)):
    return list(db.scalars(select(Zone).order_by(Zone.min_km)))
