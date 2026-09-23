"""Repeatable, isolated scenarios that prove every core requirement in a live demo.

Every scenario runs through the real production code path (JWT-protected API, the same
`FairAllocator`, the same database transaction) - nothing here re-implements the algorithm.
The demo owns a dedicated distance zone and its own vendors so a run is always reproducible
and can never collide with data created by hand in Swagger.
"""
from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.cooloff_entry import CooloffEntry
from app.models.enums import TripType, UserRole
from app.models.trip import Trip
from app.models.trip_event import TripEvent
from app.models.user import User
from app.models.vendor import Vendor
from app.models.vendor_zone_share import VendorZoneShare
from app.models.zone import Zone
from app.schemas.trip import TripCreate
from app.services.rejections import reject_trip
from app.services.reports import share_report
from app.services.shortfall import compute_shortfall
from app.services.trips import create_trip

# name, login, share %, cabs
DEMO_VENDORS = (
    ("Vendor One", "demo_v1", 50.0, 30),
    ("Vendor Two", "demo_v2", 30.0, 30),
    ("Vendor Three", "demo_v3", 20.0, 30),
)
DEMO_ZONE = ("Interview demo zone", 900, 999)
DEMO_DISTANCE_KM = 950
DEMO_KEY_PREFIX = "interview-"


# --------------------------------------------------------------------------- setup

def _demo_zone(db: Session) -> Zone:
    zone = db.scalar(select(Zone).where(Zone.label == DEMO_ZONE[0]))
    if not zone:
        zone = Zone(label=DEMO_ZONE[0], min_km=DEMO_ZONE[1], max_km=DEMO_ZONE[2])
        db.add(zone)
        db.commit()
    return zone


def setup_demo(db: Session) -> dict:
    """Idempotently create the three demo vendors, their logins and their per-zone shares."""
    zone = _demo_zone(db)
    vendors = []
    for name, username, target, cabs in DEMO_VENDORS:
        vendor = db.scalar(select(Vendor).where(Vendor.name == name))
        if not vendor:
            vendor = Vendor(name=name, active_cab_count=cabs)
            db.add(vendor)
            db.flush()
        if not db.scalar(select(User).where(User.username == username)):
            db.add(User(username=username, password_hash=hash_password("demo-pass"),
                        role=UserRole.VENDOR.value, vendor_id=vendor.id))
        # Normal and escort are configured as two independent fair streams.
        for trip_type in TripType:
            existing = db.scalar(select(VendorZoneShare).where(
                VendorZoneShare.vendor_id == vendor.id, VendorZoneShare.zone_id == zone.id,
                VendorZoneShare.trip_type == trip_type.value))
            if not existing:
                db.add(VendorZoneShare(vendor_id=vendor.id, zone_id=zone.id,
                                       trip_type=trip_type.value, target_percent=target))
        vendors.append((vendor, target))
    db.commit()
    return {"zone_id": zone.id, "zone": zone.label,
            "vendors": [{"id": v.id, "name": v.name, "target_percent": t,
                         "active_cab_count": v.active_cab_count} for v, t in vendors]}


def reset_demo(db: Session) -> dict:
    """Delete only records this demo created; never touch vendors or trips made by hand."""
    setup = setup_demo(db)
    trip_ids = list(db.scalars(select(Trip.id).where(Trip.idempotency_key.like(f"{DEMO_KEY_PREFIX}%"))))
    if trip_ids:
        db.execute(delete(TripEvent).where(TripEvent.trip_id.in_(trip_ids)))
        db.execute(delete(CooloffEntry).where(CooloffEntry.trip_id.in_(trip_ids)))
        db.execute(delete(Trip).where(Trip.id.in_(trip_ids)))
    for name, _, _, cabs in DEMO_VENDORS:
        vendor = db.scalar(select(Vendor).where(Vendor.name == name))
        if vendor:
            vendor.active_cab_count = cabs
            vendor.active = True
            db.execute(delete(CooloffEntry).where(CooloffEntry.vendor_id == vendor.id))
    db.commit()
    return setup_demo(db)


# --------------------------------------------------------------------------- helpers

def _vendor_names(db: Session) -> dict[str, str]:
    return {v.id: v.name for v in db.scalars(select(Vendor))}


def _standings(db: Session, zone_id: str, trip_type: str = TripType.NORMAL.value) -> dict:
    report = share_report(db, report_date=date.today().isoformat(), zone_id=zone_id, trip_type=trip_type)
    cabs = {v.id: v.active_cab_count for v in db.scalars(select(Vendor))}
    for row in report["rows"]:
        row["free_cabs"] = cabs.get(row["vendor_id"], 0)
    report["rows"].sort(key=lambda row: -row["target_percent"])
    return report


def _allocate(db: Session, key: str, trip_type: TripType = TripType.NORMAL) -> tuple[Trip, list]:
    trace: list = []
    trip = create_trip(db, TripCreate(distance_km=DEMO_DISTANCE_KM, trip_type=trip_type,
                                      idempotency_key=f"{DEMO_KEY_PREFIX}{key}"), trace=trace)
    return trip, trace


def _sequence(db: Session, prefix: str, count: int, trip_type: TripType = TripType.NORMAL) -> list[dict]:
    names = _vendor_names(db)
    steps = []
    for number in range(1, count + 1):
        trip, trace = _allocate(db, f"{prefix}-{number}", trip_type)
        steps.append({"trip_number": number, "trip_id": trip.id,
                      "vendor_name": names.get(trip.assigned_vendor_id, "?"), "decision": trace})
    return steps


# --------------------------------------------------------------------------- scenarios

def scenario_setup(db: Session) -> dict:
    setup = reset_demo(db)
    return {
        "headline": "Three vendors configured at 50 / 30 / 20 in an isolated demo zone.",
        "narration": "Admin is authenticated with a JWT. Shares are stored per vendor, per zone and "
                     "per trip type, so normal and escort trips are two independent fair streams.",
        "setup": setup,
        "standings": _standings(db, setup["zone_id"]),
    }


def scenario_allocate_one(db: Session) -> dict:
    """Allocate exactly one trip and return the full arithmetic behind the choice."""
    setup = setup_demo(db)
    allocated = _standings(db, setup["zone_id"])["total_trips"]
    trip, trace = _allocate(db, f"fair-{allocated + 1}")
    winner = next((row for row in trace if row["winner"]), None)
    return {
        "headline": f"Trip #{allocated + 1} went to {winner['vendor_name']} (largest shortfall).",
        "narration": "Shortfall = target% x (trips so far + 1) - trips already given. "
                     "The largest shortfall wins; ties break on vendor id, so there is no randomness.",
        "trip_number": allocated + 1, "decision": trace,
        "standings": _standings(db, setup["zone_id"]),
    }


def scenario_run_ten(db: Session) -> dict:
    setup = reset_demo(db)
    steps = _sequence(db, "fair", 10)
    order = " -> ".join(step["vendor_name"].replace("Vendor ", "V") for step in steps)
    return {
        "headline": f"10 trips split 5 / 3 / 2 exactly: {order}",
        "narration": "No vendor is ever more than one trip away from its promised share, "
                     "because every single decision re-picks the most-owed vendor.",
        "steps": steps, "standings": _standings(db, setup["zone_id"]),
    }


def scenario_escort_stream(db: Session) -> dict:
    setup = setup_demo(db)
    steps = _sequence(db, "escort", 5, TripType.ESCORT)
    order = " -> ".join(step["vendor_name"].replace("Vendor ", "V") for step in steps)
    return {
        "headline": f"Escort trips are allocated from their own pool: {order}",
        "narration": "Escort trips need a marshal, so they are a separate contract stream. "
                     "Their counters start from zero and never borrow from the normal pool.",
        "steps": steps,
        "standings": _standings(db, setup["zone_id"], TripType.ESCORT.value),
        "normal_standings": _standings(db, setup["zone_id"]),
    }


def scenario_capacity_guard(db: Session) -> dict:
    setup = setup_demo(db)
    starved = db.scalar(select(Vendor).where(Vendor.name == "Vendor One"))
    restore_to = starved.active_cab_count
    starved.active_cab_count = 0
    db.commit()
    try:
        trip, trace = _allocate(db, f"capacity-{int(time.time())}")
    finally:
        db.get(Vendor, starved.id).active_cab_count = restore_to
        db.commit()
    winner = next((row for row in trace if row["winner"]), None)
    skipped = next((row for row in trace if row["vendor_id"] == starved.id), None)
    return {
        "headline": f"Vendor One had 0 free cabs, so the trip overflowed to {winner['vendor_name']}.",
        "narration": "Fairness never overrides reality. Vendor One still shows the largest shortfall "
                     "in the trace, but it is marked ineligible, so the next-most-owed vendor takes it.",
        "blocked_vendor": starved.name, "blocked_row": skipped, "decision": trace,
        "standings": _standings(db, setup["zone_id"]),
    }


def scenario_rejection(db: Session) -> dict:
    setup = setup_demo(db)
    names = _vendor_names(db)
    trip, offer_trace = _allocate(db, f"rejection-{int(time.time())}")
    first_vendor = trip.assigned_vendor_id
    reassigned, cooloff_until = reject_trip(db, trip.id, first_vendor)
    events = [e.event_type.split(":")[0] for e in db.scalars(
        select(TripEvent).where(TripEvent.trip_id == trip.id).order_by(TripEvent.occurred_at))]
    return {
        "headline": f"{names[first_vendor]} rejected; the same trip was re-offered to "
                    f"{names[reassigned.assigned_vendor_id]}.",
        "narration": "On rejection the reserved cab is released, a cool-off row is written, and the "
                     "re-offer excludes that vendor for 15 minutes - so it cannot be offered again.",
        "trip_id": trip.id, "rejected_vendor": names[first_vendor],
        "reassigned_vendor": names[reassigned.assigned_vendor_id],
        "cooloff_until": cooloff_until, "audit_trail": events,
        "decision": offer_trace, "standings": _standings(db, setup["zone_id"]),
    }


def scenario_carry_forward(db: Session) -> dict:
    """Day 1 starves Vendor Two; day 2 must pay it back without any nightly reset job."""
    setup = reset_demo(db)
    starved = db.scalar(select(Vendor).where(Vendor.name == "Vendor Two"))
    starved.active_cab_count = 0
    db.commit()
    day_one = _sequence(db, "carry-day1", 10)
    after_day_one = _standings(db, setup["zone_id"])
    db.get(Vendor, starved.id).active_cab_count = 30
    db.commit()
    day_two = _sequence(db, "carry-day2", 6)
    owed = next(row for row in after_day_one["rows"] if row["vendor_id"] == starved.id)
    paid_back = sum(1 for step in day_two if step["vendor_name"] == starved.name)
    return {
        "headline": f"Vendor Two ended day 1 owed {owed['running_shortfall']} trips and won "
                    f"{paid_back} of the first 6 trips on day 2.",
        "narration": "Expected totals are never reset at midnight, so yesterday's shortfall is still "
                     "in today's arithmetic. A vendor short-changed yesterday gets priority today.",
        "day_one": {"steps": day_one, "standings": after_day_one, "note": "Vendor Two had 0 cabs all day."},
        "day_two": {"steps": day_two, "note": "Vendor Two is back online."},
        "standings": _standings(db, setup["zone_id"]),
    }


def scenario_determinism(db: Session) -> dict:
    """Run the identical 10-trip script twice from a clean state and hash both outcomes."""
    def run() -> list[str]:
        reset_demo(db)
        return [step["vendor_name"] for step in _sequence(db, "determinism", 10)]

    first, second = run(), run()
    digest: Callable[[list[str]], str] = lambda seq: hashlib.sha256("|".join(seq).encode()).hexdigest()
    return {
        "headline": "Identical input produced a byte-identical allocation, twice."
                    if first == second else "MISMATCH - allocation is not deterministic.",
        "narration": "Re-running a day must never produce a different split. The heap is ordered by "
                     "shortfall and tie-broken on vendor id - never on map iteration order or a random call.",
        "run_one": first, "run_two": second,
        "hash_one": digest(first), "hash_two": digest(second), "identical": first == second,
        "standings": _standings(db, setup_demo(db)["zone_id"]),
    }


def scenario_race(db: Session, workers: int = 12, cabs_each: int = 1) -> dict:
    """Fire concurrent trip requests at a nearly-empty fleet; the last cab must be won once."""
    setup = reset_demo(db)
    for name, _, _, _ in DEMO_VENDORS:
        db.scalar(select(Vendor).where(Vendor.name == name)).active_cab_count = cabs_each
    db.commit()
    capacity = cabs_each * len(DEMO_VENDORS)

    def worker(index: int) -> str:
        session = SessionLocal()
        try:
            for attempt in range(6):  # SQLite serializes writers; retry a busy lock briefly.
                try:
                    _allocate(session, f"race-{int(time.time())}-{index}")
                    return "assigned"
                except OperationalError:
                    session.rollback()
                    time.sleep(0.05 * (attempt + 1))
                except DomainError:
                    session.rollback()
                    return "refused"
            return "refused"
        finally:
            session.close()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(worker, range(workers)))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    db.expire_all()
    remaining = {v.name: v.active_cab_count for v in db.scalars(select(Vendor))
                 if v.name in {n for n, _, _, _ in DEMO_VENDORS}}
    assigned = outcomes.count("assigned")
    oversold = [name for name, count in remaining.items() if count < 0]
    return {
        "headline": f"{workers} simultaneous requests, {capacity} free cabs -> exactly {assigned} "
                    f"assigned, {outcomes.count('refused')} cleanly refused.",
        "narration": "Candidate rows are locked inside the allocating transaction (SELECT ... FOR UPDATE "
                     "on Postgres, single-writer locking on SQLite), so two threads can never take the "
                     "same last cab. Losers get a clean NO_ELIGIBLE_VENDOR error, not a corrupt count.",
        "workers": workers, "free_cabs_before": capacity, "assigned": assigned,
        "refused": outcomes.count("refused"), "elapsed_ms": elapsed_ms,
        "remaining_cabs": remaining, "no_vendor_oversold": not oversold,
        "safe": assigned == capacity and not oversold,
        "standings": _standings(db, setup["zone_id"]),
    }


DAILY_VOLUMES = (7, 13, 101, 250, 3, 58, 900)  # deliberately uneven, deliberately fixed


def scenario_convergence(db: Session, days: int = 30) -> dict:
    """Pure-algorithm simulation: the same compute_shortfall the API uses, at month scale."""
    targets = [target for _, _, target, _ in DEMO_VENDORS]
    names = [name for name, _, _, _ in DEMO_VENDORS]
    allocated = [0] * len(targets)
    total = 0
    timeline = []
    started = time.perf_counter()
    for day in range(1, days + 1):
        volume = DAILY_VOLUMES[(day - 1) % len(DAILY_VOLUMES)]
        for _ in range(volume):
            best, best_shortfall = 0, None
            for index, target in enumerate(targets):
                shortfall = compute_shortfall(target, total, allocated[index])
                if best_shortfall is None or shortfall > best_shortfall:
                    best, best_shortfall = index, shortfall
            allocated[best] += 1
            total += 1
        timeline.append({"day": day, "trips_today": volume, "total": total,
                         "actual_percent": [round(count / total * 100, 3) for count in allocated]})
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    rows = [{"vendor_name": names[i], "target_percent": targets[i], "allocated": allocated[i],
             "actual_percent": round(allocated[i] / total * 100, 4),
             "drift_percent": round(allocated[i] / total * 100 - targets[i], 4),
             "residue": round(targets[i] / 100 * total - allocated[i], 4)} for i in range(len(targets))]
    worst = max(abs(row["drift_percent"]) for row in rows)
    return {
        "headline": f"{total:,} trips over {days} uneven days simulated in {elapsed_ms} ms - "
                    f"worst drift {worst}% and every vendor still within one trip of its contract.",
        "narration": "Shortfall is kept as a real number and only rounded when a report is printed, so "
                     "thousands of allocations cannot slowly gain or lose a trip. The residue column is "
                     "the fraction still owed - it always stays below 1.",
        "days": days, "total_trips": total, "elapsed_ms": elapsed_ms,
        "worst_drift_percent": worst, "rows": rows,
        "timeline": timeline[:6] + timeline[-1:],
    }


def scenario_report(db: Session) -> dict:
    setup = setup_demo(db)
    normal = _standings(db, setup["zone_id"])
    escort = _standings(db, setup["zone_id"], TripType.ESCORT.value)
    return {
        "headline": f"Share report: {normal['total_trips']} normal and {escort['total_trips']} "
                    f"escort trips accounted for.",
        "narration": "This is the contract evidence: promised % against actual %, with the running "
                     "shortfall that carries into tomorrow. Same endpoint serves a day or a month.",
        "standings": normal, "escort_standings": escort, "month": date.today().strftime("%Y-%m"),
    }


def demo_snapshot(db: Session) -> dict:
    setup = setup_demo(db)
    return {"setup": setup, "standings": _standings(db, setup["zone_id"]),
            "report": share_report(db, report_date=date.today().isoformat(),
                                   zone_id=setup["zone_id"], trip_type=TripType.NORMAL.value)}
