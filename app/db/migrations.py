"""Small, idempotent schema upgrades for the Docker demo database."""
from sqlalchemy import text
from app.db.session import engine


def upgrade_schema() -> None:
    # create_all does not alter existing columns. Audit labels include an event
    # prefix plus a UUID, so Postgres needs more than the original 40 chars.
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE trip_events ALTER COLUMN event_type TYPE VARCHAR(80)"))
