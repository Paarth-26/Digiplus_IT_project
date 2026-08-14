import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import ENV_PATH, GROQ_API_KEY
from app.constants import configure_console
from app.database import get_db, init_db
from app.routers import incidents, kb

configure_console()  # emoji-safe stdout/stderr before any logging happens

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("triage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 Starting Support Incident Triage Assistant ...")
    init_db()
    log.info("🗄️  Database ready (tables created if missing)")
    log.info("🔑 GROQ_API_KEY %s", "loaded ✅" if GROQ_API_KEY else "missing ⚠️")
    yield
    log.info("👋 Shutting down")


app = FastAPI(
    title="🎫 Support Incident Triage Assistant",
    description="Triage support incidents and link them to knowledge base articles.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — wide open by design, for local development only.
#
# Set CORS_ORIGINS to a comma-separated list to lock this down before exposing the
# API anywhere shared. allow_credentials stays False deliberately: the CORS spec
# forbids pairing "*" with credentials, and browsers reject the combination
# outright. Nothing here uses cookies or auth headers, so this costs nothing --
# but if auth is added later, the origins must be listed explicitly at that point.
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router)
app.include_router(kb.router)


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict:
    """💚 Liveness + database reachability."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # surfaced rather than raised so the probe still answers
        db_status = f"error: {exc}"

    healthy = db_status == "ok"
    return {
        "status": "ok" if healthy else "degraded",
        "status_emoji": "💚" if healthy else "💔",
        "database": db_status,
        "service": "support-incident-triage-assistant",
        # Presence only — never echo the key itself.
        "groq_api_key_loaded": bool(GROQ_API_KEY),
        "env_file": str(ENV_PATH) if ENV_PATH.exists() else None,
    }
