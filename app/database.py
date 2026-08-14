import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Side-effect import: populates os.environ from .env before the getenv call below.
from app.config import BASE_DIR
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'incidents.db'}")

engine = create_engine(
    DATABASE_URL,
    # SQLite only: FastAPI serves requests from a thread pool, so a connection
    # may be handed to a different thread than the one that opened it.
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

if DATABASE_URL.startswith("sqlite"):
    # SQLite ignores FOREIGN KEY clauses unless this pragma is set per connection.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any tables that don't exist yet."""
    from app import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
