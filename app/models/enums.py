from enum import Enum


class TripType(str, Enum):
    NORMAL = "NORMAL"
    ESCORT = "ESCORT"


class TripStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    VENDOR = "VENDOR"
