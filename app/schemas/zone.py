from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class ZoneResponse(BaseModel):
    id: str
    label: str
    min_km: int
    max_km: Optional[int]
