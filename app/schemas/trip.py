from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import TripType, TripStatus


class TripCreate(BaseModel):
    distance_km: int = Field(gt=0)
    trip_type: TripType
    idempotency_key: str = Field(min_length=4, max_length=120)


class TripResponse(BaseModel):
    id: str
    zone_id: str
    assigned_vendor_id: Optional[str]
    trip_type: TripType
    status: TripStatus
    idempotency_key: str
    created_at: datetime


class TripHistoryItem(TripResponse):
    vendor_name: Optional[str]
    zone_label: str


class RejectionResponse(BaseModel):
    trip_id: str
    previous_vendor_id: str
    assigned_vendor_id: str
    cooloff_until: datetime
