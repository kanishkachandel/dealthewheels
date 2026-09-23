from pydantic import BaseModel, Field
from app.models.enums import TripType


class ShareInput(BaseModel):
    zone_id: str
    trip_type: TripType
    target_percent: float = Field(gt=0, le=100)


class VendorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    active_cab_count: int = Field(ge=0)
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=72)
    shares: list[ShareInput] = Field(min_length=1)


class VendorResponse(BaseModel):
    id: str
    name: str
    active_cab_count: int
    active: bool
