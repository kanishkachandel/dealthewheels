from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.api import auth, interview_demo, ops, reports, trips, vendors, zones
from app.core.exceptions import DomainError
from app.core.security import hash_password
from app.db.base import Base
from app.db.migrations import upgrade_schema
from app.db.session import SessionLocal, engine
from app.models import User  # registers all SQLAlchemy models before create_all
from app.models.enums import UserRole
from app.services.zones import ensure_default_zones


def bootstrap() -> None:
    Base.metadata.create_all(bind=engine)
    upgrade_schema()
    db = SessionLocal()
    try:
        ensure_default_zones(db)
        if not db.query(User).filter(User.username == "admin").first():
            db.add(User(username="admin", password_hash=hash_password("admin123"), role=UserRole.ADMIN.value))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap()
    yield


app = FastAPI(title="DEALTHEWHEELS", version="1.0.0", lifespan=lifespan)
app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Opening the host lands straight on the guided demo - nothing to remember on demo day."""
    return RedirectResponse("/dashboard/")


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, error: DomainError):
    return JSONResponse(status_code=error.status_code, content={"code": error.code, "message": error.message})


app.include_router(auth.router)
app.include_router(vendors.router)
app.include_router(zones.router)
app.include_router(interview_demo.router)
app.include_router(trips.router)
app.include_router(reports.router)
app.include_router(ops.router)
