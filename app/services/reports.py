from __future__ import annotations
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.trip import Trip
from app.models.vendor import Vendor
from app.models.vendor_zone_share import VendorZoneShare


def share_report(db: Session, report_date: Optional[str] = None, month: Optional[str] = None, zone_id: Optional[str] = None, trip_type: Optional[str] = None) -> dict:
    if month:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        period = month
    else:
        day = datetime.fromisoformat(report_date).date()
        start = datetime.combine(day, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        period = report_date
    trip_query = select(Trip).where(Trip.created_at >= start, Trip.created_at < end, Trip.status == "ASSIGNED")
    if zone_id:
        trip_query = trip_query.where(Trip.zone_id == zone_id)
    if trip_type:
        trip_query = trip_query.where(Trip.trip_type == trip_type)
    trips = list(db.scalars(trip_query))
    counts = Counter(trip.assigned_vendor_id for trip in trips if trip.assigned_vendor_id)
    share_query = select(VendorZoneShare, Vendor).join(Vendor)
    if zone_id:
        share_query = share_query.where(VendorZoneShare.zone_id == zone_id)
    if trip_type:
        share_query = share_query.where(VendorZoneShare.trip_type == trip_type)
    rows = []
    total = len(trips)
    for share, vendor in db.execute(share_query):
        allocated = counts[vendor.id]
        expected = total * float(share.target_percent) / 100
        rows.append({"vendor_id": vendor.id, "vendor_name": vendor.name, "target_percent": float(share.target_percent), "actual_percent": round((allocated / total * 100) if total else 0, 2), "allocated_trips": allocated, "expected_trips": round(expected, 4), "running_shortfall": round(expected - allocated, 4)})
    return {"date": period, "zone_id": zone_id, "trip_type": trip_type, "total_trips": total, "rows": rows}
