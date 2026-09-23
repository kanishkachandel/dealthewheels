"""One endpoint per live-demo scenario. Admin-only, like every other write path."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin
from app.db.session import get_db
from app.services import interview_demo as scenarios

router = APIRouter(prefix="/api/demo", tags=["interview demo"])


@router.post("/setup", summary="Reset and seed the isolated 50/30/20 demo")
def setup(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_setup(db)


@router.post("/allocate-one", summary="Allocate a single trip and show the shortfall maths")
def allocate_one(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_allocate_one(db)


@router.post("/run-ten", summary="Allocate ten trips and prove the 5/3/2 split")
def run_ten(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_run_ten(db)


@router.post("/escort-stream", summary="Prove escort trips are an independent fair stream")
def escort_stream(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_escort_stream(db)


@router.post("/capacity-guard", summary="Prove a vendor with no free cab is skipped safely")
def capacity_guard(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_capacity_guard(db)


@router.post("/rejection", summary="Prove rejection re-allocates and starts a cool-off")
def rejection(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_rejection(db)


@router.post("/carry-forward", summary="Prove yesterday's shortfall is paid back today")
def carry_forward(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_carry_forward(db)


@router.post("/determinism", summary="Run the same day twice and compare hashes")
def determinism(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_determinism(db)


@router.post("/race", summary="Fire concurrent requests at the last free cabs")
def race(workers: int = Query(12, ge=2, le=32), db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_race(db, workers=workers)


@router.post("/convergence", summary="Simulate a month of uneven volume in memory")
def convergence(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_convergence(db, days=days)


@router.post("/report", summary="Promised vs actual vs running shortfall")
def report(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.scenario_report(db)


@router.get("/snapshot", summary="Current demo standings without changing anything")
def snapshot(db: Session = Depends(get_db), _=Depends(require_admin)):
    return scenarios.demo_snapshot(db)
