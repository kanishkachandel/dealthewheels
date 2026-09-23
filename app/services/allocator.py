import heapq
from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import NoEligibleVendorException
from app.models.trip import Trip
from app.models.vendor import Vendor
from app.models.vendor_zone_share import VendorZoneShare
from app.services.cache import running_totals_cache
from app.services.cooloff import is_in_cooloff
from app.services.metrics import DRIFT
from app.services.shortfall import compute_shortfall, running_totals


@dataclass(order=True)
class HeapCandidate:
    priority: float
    vendor_id: str
    vendor: Vendor = field(compare=False)
    shortfall: float = field(compare=False)


@dataclass
class DecisionRow:
    """One vendor's side of a single allocation decision, kept for explainability."""
    vendor_id: str
    vendor_name: str
    target_percent: float
    expected_so_far: float
    allocated: int
    shortfall: float
    eligible: bool
    reason: str
    winner: bool = False

    def as_dict(self) -> dict:
        return {
            "vendor_id": self.vendor_id, "vendor_name": self.vendor_name,
            "target_percent": self.target_percent, "expected_so_far": round(self.expected_so_far, 4),
            "allocated": self.allocated, "shortfall": round(self.shortfall, 4),
            "eligible": self.eligible, "reason": self.reason, "winner": self.winner,
        }


class FairAllocator:
    """Deterministic most-owed-first allocation for one independent trip stream."""
    trip_type: str

    def __init__(self) -> None:
        self.last_decision: list[DecisionRow] = []

    def _eligibility(self, db: Session, vendor: Vendor, now: datetime) -> tuple[bool, str]:
        if not vendor.active:
            return False, "vendor inactive"
        if vendor.active_cab_count <= 0:
            return False, "no free cab"
        if is_in_cooloff(db, vendor.id, now):
            return False, "in cool-off"
        return True, "eligible"

    def allocate(self, db: Session, trip: Trip) -> Vendor:
        # Every vendor configured for this pool is loaded — not only the eligible ones — so a
        # rejected decision can still be explained afterwards. Lock rows on Postgres; SQLite
        # ignores FOR UPDATE but serializes writers, so neither database over-allocates a cab.
        shares = db.execute(select(VendorZoneShare, Vendor).join(Vendor).where(
            VendorZoneShare.zone_id == trip.zone_id,
            VendorZoneShare.trip_type == self.trip_type,
        ).with_for_update()).all()
        total_before, actual = running_totals(db, trip.zone_id, self.trip_type)
        heap: list[HeapCandidate] = []
        rows: list[DecisionRow] = []
        now = datetime.now(timezone.utc)
        for share, vendor in shares:
            target = float(share.target_percent)
            shortfall = compute_shortfall(target, total_before, actual[vendor.id])
            eligible, reason = self._eligibility(db, vendor, now)
            rows.append(DecisionRow(vendor.id, vendor.name, target, target / 100 * (total_before + 1),
                                    actual[vendor.id], shortfall, eligible, reason))
            DRIFT.labels(vendor.id, trip.zone_id, self.trip_type).set(shortfall)
            if eligible:
                # negative creates a max heap, vendor_id makes tied decisions deterministic.
                heapq.heappush(heap, HeapCandidate(-shortfall, vendor.id, vendor, shortfall))
        # Sorted purely for human reading; the winner always comes from the heap.
        rows.sort(key=lambda row: (-row.shortfall, row.vendor_id))
        self.last_decision = rows
        if not heap:
            raise NoEligibleVendorException("No active, capacitated vendor is eligible for this zone and trip type")
        selected = heapq.heappop(heap).vendor
        for row in rows:
            row.winner = row.vendor_id == selected.id
        selected.active_cab_count -= 1
        trip.assigned_vendor_id = selected.id
        actual[selected.id] += 1
        running_totals_cache.put(trip.zone_id, self.trip_type, dict(actual))
        return selected


class NormalTripAllocator(FairAllocator):
    trip_type = "NORMAL"


class EscortTripAllocator(FairAllocator):
    trip_type = "ESCORT"


def allocator_for(trip_type: str) -> FairAllocator:
    return EscortTripAllocator() if trip_type == "ESCORT" else NormalTripAllocator()
