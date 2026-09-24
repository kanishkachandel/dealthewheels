from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ShareRow(BaseModel):
    vendor_id: str
    vendor_name: str
    zone_id: str
    zone_label: str
    trip_type: str
    target_percent: float
    actual_percent: float
    allocated_trips: int
    expected_trips: float
    running_shortfall: float


class ShareReport(BaseModel):
    date: str
    zone_id: Optional[str]
    trip_type: Optional[str]
    total_trips: int
    rows: list[ShareRow]
