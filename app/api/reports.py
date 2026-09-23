from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin
from app.db.session import get_db
from app.schemas.report import ShareReport
from app.services.reports import share_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/share", response_model=ShareReport)
def get_share_report(date: Optional[str] = Query(None), month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"), zone_id: Optional[str] = None, trip_type: Optional[str] = None, db: Session = Depends(get_db), _=Depends(require_admin)):
    if bool(date) == bool(month):
        raise HTTPException(status_code=422, detail="Pass exactly one of date=YYYY-MM-DD or month=YYYY-MM")
    return share_report(db, date, month, zone_id, trip_type)
